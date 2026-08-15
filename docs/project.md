# Project Spec — Wikipedia QA Agent + Eval Suite

Living document. Decisions land here as they're made; open questions stay
visible until closed. Written to be self-contained — someone picking this up
cold should need nothing but this file and the code.

Last updated: 2026-08-15 (end of Phase 2)

---

## 1. Goal

Build a system that answers questions using Claude + Wikipedia, and an eval
suite that measures how well it works. Assignment details in `assignment.md`;
methodology pointers in `references.md`.

Deliverables: runnable prototype, code, design rationale (video + doc).

---

## 2. Guiding principles

1. **Simplest thing that works e2e first.** Observe real failure modes before
   adding structure.
2. **Maximize determinism.** Every signal that can be computed exactly, is.
   LLM judgment is a last resort, kept to the smallest possible surface.
3. **Debuggability is a build requirement.** If a run's behaviour can't be
   reconstructed from its trace, the trace is incomplete.
4. **Evals are instruments and can themselves be wrong.** A bad grader gets
   fixed before the agent does.
5. **The funnel is a hypothesis.** Stage definitions are a starting lens,
   expected to change once traces are open-coded. Not hard-coded in the harness.
6. **Guard against silent corruption, not just crashes.** A run that fails
   costs an hour; a run that is quietly wrong costs a phase of false
   conclusions. This drives both the trace design and the test suite.

---

## 3. Decisions made

### 3.1 Retrieval

| Decision | Choice | Why |
|---|---|---|
| Data source | Live MediaWiki API | No dump/index infra; assignment says don't build a search system |
| Tool surface | Single `search_wikipedia(query)` | Assignment specifies it; simplest e2e |
| Result shape | Title + first ~1500 chars of intro, per result | Enough for most questions, bounded token cost |
| Results shown | `top_k`, default 3 | The one tunable knob (`--top-k`) |
| Results fetched | `max(OVERFETCH=5, top_k)` | See below |
| Caching | On-disk, keyed by `sha256(fetch_count:query)` | **Required for measurable iteration** |

**Fetch more than we show.** The surplus costs nothing — cached, never rendered
into the prompt — but it makes "would showing more have retrieved the gold
article?" answerable from traces we already have, with zero extra agent calls.
Raising `top_k` becomes evidence-backed rather than a guess.

`OVERFETCH` is deliberately *not* a parameter: it's the width of a diagnostic
margin, not a behaviour to tune, and pinning it keeps the cache key stable so
changing `top_k` reuses cached results instead of refetching.

**Why cache at all:** live Wikipedia changes underneath repeated eval runs, so
without it a score delta can't be attributed to a prompt change. Failures are
never cached — one network blip would otherwise poison that query forever.

### 3.2 Models and cost

| Role | Model | Notes |
|---|---|---|
| Agent | `claude-haiku-4-5` (default) | Chosen for cost; `--model` overrides |
| Judge | A *different* model from the agent, pinned | Not yet built |

Estimated sweep cost (40 cases × 3 runs = 120 runs, ~6K in / ~1K out each):
Haiku ~$1.30, Sonnet 5 ~$2.60, Opus 5 ~$6.60.

**Open trade-off, to be resolved with data.** Haiku is cheapest but some of its
failures will be plain capability limits, which teach nothing about prompt or
tool design — the actual subject of the assignment. **Planned:** once the
harness and case set exist, run one baseline sweep on Haiku and one on Sonnet 5
over identical cases, and decide from the measured gap rather than argument. If
Haiku's error taxonomy is dominated by "model wasn't strong enough," switch.
This is a `--model` flag, not a code change.

**Judge must differ from the agent** — same-model judging carries a documented
self-preference bias. Judge model *and* judge prompt version get recorded in
every result file so drift is detectable rather than silent; changing either
forces re-validation against the human labels.

**Model capability gating is real.** Adaptive thinking and `output_config.effort`
are Opus/Sonnet-5-family parameters; Haiku 4.5 returns a 400 for both. The
request is built per-model (`agent._supports_adaptive_thinking`), and `--effort`
on Haiku raises a clear error instead. Consequence: **no thinking text in Haiku
traces**, so debugging leans on tool calls and answers.

### 3.3 Agent

- Anthropic Messages API, explicit tool-use loop (not the SDK tool runner —
  we need per-turn visibility, and an explicit loop puts it in one place).
- `MAX_TURNS = 10` is a guard, not a design parameter. Hitting it is recorded
  as an error so a runaway loop can't look like success.
- **Abstention is a v0 prompt requirement**, measured in *both* directions —
  confabulation and over-abstention are both failures.
- **Source attribution is split by who actually knows what:**
  - *What was searched and retrieved* → the harness knows this deterministically
    from the tool-call log, and builds the provenance record.
  - *What the answer was grounded on* → only the agent knows, so it names its
    sources in prose.
  - Fabricated-citation check falls out: `agent-named titles ⊆ retrieved titles`.
  - Starting with prose mentions + fuzzy title matching; add explicit markers
    only if matching proves unreliable in Phase 5.
- Provenance shows in the **user-facing answer**, labelled "Searched/Retrieved"
  — never "sources used", which only the model can know.

### 3.4 Rejected: running the agent through `claude -p`

Considered to avoid API spend by using a Claude plan. **Rejected.** It required
wrapping the tool as an MCP server, actively suppressing Claude Code's built-in
WebSearch/WebFetch (which the assignment forbids), neutralising ambient
`CLAUDE.md`/skills/hooks contamination, and it made the CLI version part of the
system under test. Cost saving didn't justify the added confounds on the
project's central deliverable. Removed the MCP server and dependency.

### 3.5 Debuggability

Two modes: normal (answer + provenance) and verbose (everything).

A single `Trace` object is the source of truth — both `--verbose` and the eval
harness read it, so what's seen while debugging can't drift from what's scored.

The trace stores **full raw tool results, never summaries.** That's what makes
it possible to tell "the right article was retrieved but the intro didn't
contain the fact" apart from "the model ignored the evidence" — two failures
with opposite fixes. It also keeps results past `top_k` that the model never
saw (`retrieved_titles` vs `shown_titles`).

Contents: prompt version · model · every query · full raw results per query ·
every assistant turn (thinking where available) · final answer · turn count ·
token counts · latency · cache hit/miss.

### 3.6 Failure funnel (provisional)

1. **Query formulation** — did it search at all; was the query sensible?
2. **Retrieval** — did a gold article come back?
3. **Evidence** — was the answer-bearing fact actually *inside* the returned text?
4. **Synthesis** — all ingredients present, wrong join (multi-hop, date maths).
5. **Grounding** — asserts things in no snippet. Invented ingredients.
6. **Answer** — correct, and correctly formed (abstains when it should).

Stages 4 and 5 are distinct on purpose: synthesis is *right ingredients, wrong
combination*; grounding is *invented ingredients*.

**Applied post-hoc during analysis, not encoded in grader code.** Graders emit
raw signals; staging happens over traces. An unanticipated stage means
relabelling, not rewriting the harness.

### 3.7 Eval measurement

**Deterministic — no LLM:** did it search · number of calls · titles retrieved ·
gold article retrieved · cited ⊆ retrieved · turns · tokens · latency

**LLM-judged — categorical only, no numeric scales:**

| Dimension | Categories |
|---|---|
| Correctness | `correct` / `incorrect` (binary) |
| Posture | `confident` / `hedged` / `abstained` |
| Faithfulness | `supported` / `contains unsupported claim` |

Binary correctness over partial credit: partial credit invites judge drift, and
genuinely borderline cases surface as flakiness across repeats instead.

> **Open — revisit after Phase 5 traces.** These three are a starting point.
> The intent is to double down on *answer quality* and it's not yet clear these
> capture it.

**Judge validation is mandatory.** Rubric with per-category definitions and 1–2
boundary examples, validated against hand labels on ~20 traces before any number
is trusted. Judge-vs-human agreement reported. Poor agreement → fix the rubric
before touching the agent.

**Repeats: 3× per question**, bucketed `3/3` (solid) · `1-2/3` (flaky) · `0/3`
(systematic — prioritise). Gives both a variance floor and a prioritisation
signal.

### 3.8 Eval dataset

Mostly hand-written with research, some borrowed. **Start at ~10 cases, grow to
20–25** as failure modes come into view.

Starting small is the point, not a compromise: 10 cases × 3 repeats = 30 runs is
one cheap loop through observe → categorise → fix → re-run, and cases written
*after* seeing real failures are better targeted than cases written up front.
The cost is statistical: at n=10 the headline rates are noise. So the summary is
read as **per-case buckets and traces**, never as a percentage moving by a few
points. Aggregates only become meaningful nearer 25.

Fields: `id` · `question` · `expected` · `gold_articles` (**optional**) ·
`dimension` tags.

`gold_articles` is optional by necessity — unanswerable and false-premise cases
have none by definition, and for those the retrieval stage inverts (success =
confirming absence). Retrieval recall is reported over only the subset that has
them, denominator stated. No inflated denominators.

**No-tool control arm** (`--no-tools`): same cases, retrieval structurally
impossible. Run once in Phase 4 as a *dataset* property check, distinct from the
agent baseline. If the control scores near baseline, the dataset measures
parametric memory and needs rewriting toward obscure/multi-hop/post-cutoff
facts. Also exposes the interesting cell: **control passes, tool-on fails** —
retrieval actively hurting by distraction.

### 3.9 Harness durability

A sweep is real money, so the runner is built around not wasting it and — more
importantly — around never producing results that are quietly wrong:

| Guarantee | Why |
|---|---|
| Row written after **every** run | An interruption at run 90 costs one run, not ninety |
| Re-run resumes, skipping completed runs | Retries are free; no accidental double spend |
| Errored runs are **retried**, not kept | A network blip must not be frozen in as a result |
| One bad case never ends the sweep | Failure is recorded as a row and the sweep continues |
| A failed run's retrieval signals are `None` | An infrastructure error is not a retrieval miss |
| Resume **refuses** a changed config | Two configs merged into one file still look plausible |
| Full config in every row *and* `config.json` | Results outlive the command that produced them |
| Summary rebuilt from the file, not memory | A resumed sweep's summary covers the whole sweep |
| Summary states "correctness not measured" | The dangerous summary is one that reads like a score |

Usage: `python -m evals.run --cases evals/cases --repeats 3 [--no-tools]`.
Output goes to `results/<ts>-<model>-<arm>/`; passing an existing `--out`
resumes it.

---

## 4. Phases

| # | Phase | Status |
|---|---|---|
| 1 | Design the tool | ✅ Tool schema, result format, error/empty shapes, v0 prompt |
| 2 | Build e2e | ✅ CLI works; cache works; 63 tests green |
| 3 | Build eval harness | ✅ Cases → agent → graders → summary + traces; resumable; 120 tests green |
| 4 | Design & build eval set | ⬜ **Next.** ~10 tagged cases → 20–25; no-tool control validates headroom |
| 5 | Run & manually debug | ⬜ Open-code traces into a taxonomy; variance floor; validate judge |
| 6 | Iterate | ⬜ Scored changelog; per-case pass→fail diffs, not just aggregates |

Phase 3 follows TDD per `CLAUDE.md`: harness tests first, then implementation.

---

## 5. Layout

```
wikiagent/
  wikipedia.py    # MediaWiki API + cache          (~200 lines)
  tools.py        # tool schema + dispatch
  prompts.py      # system prompts, versioned      (v0 only so far)
  agent.py        # explicit tool-use loop, emits a Trace
  trace.py        # Trace object + derived views + JSON dump
  cli.py          # ask / demo / --verbose / .env loader
tests/
  conftest.py       # stub Anthropic client, fake search, isolated cache
  test_wikipedia.py # truncation, cache keying, cache integrity, ranking, live API
  test_tools.py     # schema/description accuracy, dispatch error handling
  test_agent.py     # loop, API contracts, capability gating, control arm, trace
evals/
  cases/*.jsonl   # (Phase 4) strict loading; duplicate/unsafe ids rejected
  cases.py        # Case + loader
  graders.py      # deterministic signals only — no verdict, no semantics
  run.py          # sweep runner -> <out>/{config.json,results.jsonl,summary.md,traces/}
docs/
  project.md      # this file
  error-analysis.md  # (Phase 5 output)
```

Python 3.11 · `anthropic` + `httpx` · `uv` · `pytest`. No framework, no vector
DB, no orchestration layer. API key from `.env` or the environment.

---

## 6. Testing

63 tests: 61 offline (stub Anthropic client, no key, no network) + 2 live-API
behind `WIKIAGENT_NETWORK=1`.

Selected around principle 2.6 — invariants whose failure would be **silent**:
cache integrity (errors never cached; `top_k` changes reuse the cache), control-arm
purity (structurally unable to retrieve, not merely not-asked), trace fidelity
(`shown` vs `retrieved` stay distinct; usage sums correctly), API contracts
(thinking echoed verbatim; all tool results in one user message), graceful
degradation (malformed input, refusals, runaway loops become recorded errors).

Verified by mutation: caching errors, letting the control arm dispatch, and
splitting tool results across messages each fail exactly the test written for
them.

---

## 7. First observations (demo run, Haiku 4.5, prompt v0)

Five questions, one run each. **Anecdotes, not measurements** — n=1, no repeats,
no judge. Recorded because they shape what the eval set must cover.

| Shape | Outcome |
|---|---|
| Single-hop factual | Correct, article named |
| Multi-hop | **Wrong** — see below |
| Unanswerable | Abstained correctly, but never searched |
| False premise | Correctly rejected the premise, article named |
| No search needed | Correct, no search |

**The multi-hop failure is a stage-3 (evidence) failure, confirmed not
inferred.** Asked which university *The Selfish Gene*'s author attended, the
agent ran five searches and did retrieve `Balliol College, Oxford` — the right
article. Checking cached extracts directly: the `Richard Dawkins` intro never
mentions Balliol, and the `Balliol` intro never mentions Dawkins. Retrieval
succeeded; the answer-bearing fact wasn't in the opening sections. It is in the
full article.

Exactly the failure the intro-only design was expected to produce, so the
`fetch_article` question in §8 is now evidence-backed. **Not acting on it yet** —
one case is no basis for a tool redesign; Phase 5 shows how often it occurs.

Three more candidate eval dimensions:

- **Over-searching.** Five searches on the failure vs one on each success. A
  distress signal, not just cost.
- **Verbosity under failure.** The failing answer stated its conclusion twice.
- **Ungrounded abstention.** The unanswerable case abstained *without
  searching*, from priors. Right answer, wrong process — and a prompt that
  abstains from priors will eventually abstain on something Wikipedia covers.
  Argues for scoring abstention and retrieval as separate signals.

---

## 8. Open questions

- Are the three LLM-judged dimensions the right ones? (§3.7) — revisit after
  Phase 5 traces.
- Does intro-only retrieval starve deep-fact questions enough to justify
  `fetch_article`? — evidence-backed by §7, decide from Phase 5 stage-3 rates.
- Haiku vs Sonnet 5 as the agent — decide from the paired baseline sweep (§3.2).
- Is prose-mention source matching reliable enough, or are inline markers
  needed? — decide from Phase 5.

---

## 9. Non-goals

Vector search / embeddings · multi-agent · web UI · production-grade retrieval ·
fine-tuning · running the agent through Claude Code (§3.4). The assignment
directs effort to prompt quality and eval design.
