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

### 3.3b The prompt surface (the main lever)

There are three things the model reads, and all three are prompt engineering:

| Surface | Where | What it controls |
|---|---|---|
| System prompt | `prompts.py` | when to search, how to answer, when to refuse |
| Tool description | `prompts.py` | when to reach for the tool, how to phrase a query |
| Rendered result | `wikipedia.render()` | what evidence looks like, incl. the cut-off marker |

**A version pins all of them.** The tool description lives in `prompts.py`
beside the system prompt because they're one surface, and versioning them apart
would let a tool-description edit silently invalidate a previous sweep while
`prompt_version` in the trace still claimed the runs were comparable.

**Old versions are frozen** — a hash canary in `test_prompts.py` fails if one is
edited, because results scored against `v0` stop meaning anything if `v0` moves.

**v1 (default)** is a defect fix plus structure, not new behaviour:

1. v0 hardcoded "the three best-matching articles" while `top_k` is a knob, so
   `--top-k 5` shipped a prompt that lied. The count now appears only in the
   tool description, which is built from the real value.
2. v0 said "name the article" without saying how, and the model paraphrased
   (*"articles on penicillin discovery"* for *Discovery of penicillin*). v1 asks
   for exact titles as shown — which is what makes `cited_titles` mean anything,
   and it's why the deterministic fabrication check had to be dropped.
3. Extracts are cut short and marked `[...]`, but nothing told the model what
   the marker meant, so *"the article doesn't say"* and *"the text stopped
   here"* looked identical — one leads to false abstention, the other to a
   guess. The tool description now names the marker, and a test asserts it's
   the same string `_truncate` actually emits.

Structure is three labelled blocks — *Searching* / *Answering* / *When Wikipedia
doesn't answer it* — mapping onto funnel stages, so a failure at a stage points
at one block to edit. Kept deliberately short: **~130 words leaves room to
hill-climb where the evals say it's needed**, and a long prompt makes it
impossible to attribute a delta to any one line.

The one behavioural addition is *"one subject per search; if the answer needs
two facts, search for each"* — the single multi-hop failure seen so far.

**Deliberately not added yet** (candidate levers, to be spent where evals point):
few-shot examples · explicit citation markers · guidance to issue parallel
searches in one turn · retry guidance duplicated into the tool description ·
telling the model it may ask for more results.

v0 stays available (`--prompt v0`), so "is v1 actually better?" is a cheap
first experiment rather than an assumption.

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

**Two-stage protocol.** Repeats are for scoring, not for looking:

1. **Read pass — 31 questions (11 core + 20 explore), 1 run each.** Purpose is
   error analysis, not measurement: read `review.md` end to end, record verdicts
   in `labels.jsonl`, open-code the failures into a taxonomy. Repeating a run
   you're about to read by hand buys nothing and costs 3×.
2. **Score pass — 3× per question**, bucketed `3/3` (solid) · `1-2/3` (flaky) ·
   `0/3` (systematic — prioritise). Gives both a variance floor and a
   prioritisation signal, and flakiness is itself a finding: a case that flips
   between runs is a different problem from one that fails every time.

Cheap by construction: the Wikipedia cache is warm after the read pass, so the
score pass re-pays only for model calls.

### 3.8 Eval dataset

**Two sets with opposite purposes.**

| | `core.jsonl` | `explore.jsonl` |
|---|---|---|
| Written by | hand, one case per mode | random draw, real user queries |
| Source | us + benchmark taxonomies | Natural Questions (`nq_open`), CC BY-SA 3.0 |
| Size | 11 | 20 |
| Runs | 3× + flakiness buckets | once |
| Purpose | test what we decided matters | find what we didn't think of |
| `gold_articles` | yes, where one exists | none, deliberately |
| Tagged | one dimension per mode | `explore` only |

**Why a random set at all.** A hand-written set is stratified sampling from our
own hypothesis space — it can only confirm the taxonomy that produced it. The
random set is drawn from a distribution we don't control. Evidence it's a
different distribution: AmbigQA found **over half of Natural Questions are
ambiguous**; nobody hand-writes a set like that.

The first five rows drawn showed it immediately — a query that isn't a question
(`the first railway train in india ran in 1853 from mumbai to`), an
ungrammatical one (`beat bobby flay how many times has he won`), present-tense
questions with past answers, and multi-answer questions. Two of those modes
were not in our taxonomy.

**Sampling discipline** — the part that's easy to lose:
- Fixed seed (`20260816`) and drawn row indices recorded in
  `explore.provenance.json`.
- **Every drawn row kept.** Dropping the awkward ones restores our taxonomy;
  the boring ones give the base rate.
- Questions stored verbatim — the missing capitals are the signal.
- Frozen by a digest in `test_dataset.py`, because "nobody curated this" is
  the set's entire value and is invisible in a later diff review.
- Untagged beyond `explore`: the taxonomy comes *out* of reading these.

**NQ reference answers are references, not ground truth** — the dataset is
c.2018 and some answers are wrong (its "original Broadway cast" Hamilton answer
names the alternate, not Lin-Manuel Miranda). The read pass judges against
Wikipedia, not against the reference.

**Cases are verified against real retrieval before being committed**, at zero
model cost. This is not ceremony: the first deep-fact case asked for the step
count of the Leaning Tower of Pisa on the assumption it wasn't in the intro —
it is. Committed unverified, it would have looked like a synthesis failure
whenever the agent answered correctly. It was replaced with the Sydney Opera
House Concert Hall capacity, checked to be present in the article body and
absent from the intro.

**Deferred:** safeguards-flavoured cases (instructions embedded in retrieved
text, over-refusal on encyclopedic-but-sensitive topics). Out of scope for the
main functionality pass; a candidate for one run at the end if time allows.
Also deferred: a matched control for the false-premise case (FalseQA's design),
temporal-arithmetic joins.

Starting small is the point, not a compromise: 11 cases × 3 repeats = 33 runs is
one cheap loop through observe → categorise → fix → re-run, and cases written
*after* seeing real failures are better targeted than cases written up front.
The cost is statistical: at n=11 the headline rates are noise. So the summary is
read as **per-case buckets and traces**, never as a percentage moving by a few
points. Aggregates only become meaningful nearer 25.

**The core 11**, one per mode: single-hop factual (regression floor) ·
multi-hop bridge · deep fact outside the intro · unanswerable · false premise ·
term ambiguity (*Tesla* — company or person) · must-search (a fact the model
certainly knows: does it search anyway?) · negative existence (*did Turing ever
win a Nobel* — "not mentioned" ≠ "didn't happen") · query formulation with no
entity name given · no-search-needed (live weather) · completeness (a
five-country border list, where a partial answer reads as correct).

Fields: `id` · `question` · `expected` · `gold_articles` (**optional**) ·
`dimension` tags.

`gold_articles` is optional by necessity — unanswerable and false-premise cases
have none by definition, and for those the retrieval stage inverts (success =
confirming absence). Retrieval recall is reported over only the subset that has
them, denominator stated. No inflated denominators.

**No-tool control arm** (`--no-tools`) — **built, deferred to a bonus round.**
Same cases with retrieval structurally impossible, as a *dataset* property
check: if the control scores near the agent baseline, the set measures
parametric memory rather than the system. It also exposes the interesting cell,
control passes / tool-on fails — retrieval actively hurting by distraction.

Deferred because the assignment is to improve *the agent*, and the control arm
diagnoses the *dataset*. It answers "is this eval set worth anything?", not
"where is the agent wrong?" — so it earns its cost only once the agent work is
done. The flag, the structural guarantee that the arm cannot retrieve, and its
tests all stay in place, so running it later is one command.

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

### 3.10 Where the output lives

One directory per sweep, `results/<ts>-<set>-<model>-<prompt>/`. Passing an
existing `--out` resumes into it.

| File | For | Notes |
|---|---|---|
| `traces/<case>--r<n>.json` | full fidelity | every raw tool result, per-turn thinking, token counts. The source of truth |
| `results.jsonl` | machine analysis | one row per run: deterministic signals + question + expected + full config |
| `review.md` | **reading** | every run rendered top to bottom: question, expected, queries, titles shown, gold hit/miss, full answer, link to trace |
| `labels.jsonl` | **bucketing** | one seeded row per run — `verdict`, `stage`, `note` — filled in by hand |
| `summary.md` | at a glance | deterministic rates, per-case retrieval buckets, and an explicit "correctness not measured" |
| `config.json` | provenance | what produced this directory |

Three properties that matter more than they look:

- **Rows carry their own question and expected answer.** A row you have to join
  back to the case file by hand doesn't get read.
- **Repeats of a case sit together** in `review.md`, so flakiness is visible
  without cross-referencing anything.
- **Hand labels are never overwritten.** Re-running a sweep reseeds only the
  runs that have no label yet. Human judgement is the expensive artifact here,
  and a reseed would erase an afternoon of it while leaving a perfectly
  well-formed file behind.

`stage` in `labels.jsonl` is **free text**, not an enum. The funnel is a
hypothesis; a dropdown of our six stages would quietly become the answer.

Usage:

```bash
python -m evals.run --cases evals/cases/core.jsonl    --repeats 1   # read pass
python -m evals.run --cases evals/cases/explore.jsonl --repeats 1
python -m evals.run --cases evals/cases/core.jsonl    --repeats 3   # score pass
```

The two sets are run into **separate directories on purpose** — a shared
summary would average a curated set against a random one and mean nothing.

---

## 4. Phases

| # | Phase | Status |
|---|---|---|
| 1 | Design the tool | ✅ Tool schema, result format, error/empty shapes, v0 prompt |
| 2 | Build e2e | ✅ CLI works; cache works; tests green |
| 3 | Build eval harness | ✅ Cases → agent → graders → review + labels + traces; resumable |
| 4 | Design & build eval set | ✅ 11 curated (one per mode) + 20 frozen random NQ; verified against live retrieval |
| 5 | Run & manually debug | ⬜ **Next.** Read pass 1× → open-code `labels.jsonl` into a taxonomy → score pass 3× |
| 6 | Iterate | ⬜ Scored changelog; per-case pass→fail diffs, not just aggregates |
| — | Bonus, if time | No-tool control arm · safeguards cases · Haiku vs Sonnet baseline |

Every phase follows TDD per `CLAUDE.md`: tests first, then implementation.

---

## 5. Layout

```
wikiagent/
  wikipedia.py    # MediaWiki API + cache
  tools.py        # tool schema + dispatch
  prompts.py      # system prompt AND tool description, versioned together
  agent.py        # explicit tool-use loop, emits a Trace
  trace.py        # Trace object + derived views + JSON dump
  cli.py          # ask / demo / --verbose / .env loader
tests/
  conftest.py       # stub Anthropic client, fake search, isolated cache
  test_wikipedia.py # truncation, cache keying, cache integrity, ranking, live API
  test_tools.py     # schema/description accuracy, dispatch error handling
  test_agent.py     # loop, API contracts, capability gating, control arm, trace
  test_prompts.py   # version pins both surfaces; frozen-version canary
  test_cases.py     # strict loading; duplicate and unsafe ids rejected
  test_graders.py   # signals only — no verdict, no semantics
  test_run.py       # resume, failure isolation, config pinning, label safety
  test_dataset.py   # the committed set: mode coverage, frozen random sample
evals/
  cases/core.jsonl      # 11 curated, one per failure mode
  cases/explore.jsonl   # 20 frozen random NQ questions (+ .provenance.json)
  cases.py        # Case + loader
  graders.py      # deterministic signals only — no verdict, no semantics
  sample_nq.py    # one-shot frozen draw; kept for reproducibility
  run.py          # sweep runner (see §3.10 for the output layout)
results/          # one directory per sweep; committed as evidence
docs/
  project.md      # this file
  error-analysis.md  # (Phase 5 output)
```

Python 3.11 · `anthropic` + `httpx` · `uv` · `pytest`. No framework, no vector
DB, no orchestration layer. API key from `.env` or the environment.

---

## 6. Testing

151 tests: 149 offline (stub Anthropic client, no key, no network) + 2 live-API
behind `WIKIAGENT_NETWORK=1`. The whole suite runs in under half a second, so
there's never a reason to skip it.

Selected around principle 2.6 — invariants whose failure would be **silent**:
cache integrity (errors never cached; `top_k` changes reuse the cache),
control-arm purity (structurally unable to retrieve, not merely not-asked),
trace fidelity (`shown` vs `retrieved` stay distinct; usage sums correctly),
API contracts (thinking echoed verbatim; all tool results in one user message),
graceful degradation (malformed input, refusals, runaway loops become recorded
errors), sweep durability (resume, config pinning, failed runs not scored as
retrieval misses), hand-label safety, and two frozen-artifact canaries (prompt
`v0`, the random sample).

Verified by mutation — each of these was introduced deliberately and caught by
exactly the test written for it: caching errors · letting the control arm
dispatch · splitting tool results across messages · dropping the `None`
override on a failed run · keeping errored rows on resume · skipping the config
check · buffering result rows instead of appending · reseeding hand labels ·
building `review.md` from memory instead of from the results file.

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

**Spot-check after v1 (n=1 again, so no conclusions):** asked directly which
Oxford college Dawkins attended, *both* v0 and v1 now abstain correctly, naming
what they did find. So the invented join isn't reproducible on this phrasing —
which is itself the argument for repeats: a single run can't tell a fixed
failure from a flaky one.

Three more candidate eval dimensions:

- **Over-searching.** Five searches on the failure vs one on each success. A
  distress signal, not just cost.
- **Verbosity under failure.** The failing answer stated its conclusion twice.
- **Ungrounded abstention.** The unanswerable case abstained *without
  searching*, from priors. Right answer, wrong process — and a prompt that
  abstains from priors will eventually abstain on something Wikipedia covers.
  Argues for scoring abstention and retrieval as separate signals.
  **Reproduced under v1** during a harness smoke run: `n_searches = 0` on the
  Ada Lovelace case. Still n=1, but it survived a prompt that explicitly says
  to search first, so it's the first thing to look for in the read pass.

---

## 8. Open questions

- Are the three LLM-judged dimensions the right ones? (§3.7) — revisit after
  Phase 5 traces.
- Does intro-only retrieval starve deep-fact questions enough to justify
  `fetch_article`? — evidence-backed by §7, decide from Phase 5 stage-3 rates.
- Haiku vs Sonnet 5 as the agent — decide from the paired baseline sweep (§3.2).
- Is prose-mention source matching reliable enough, or are inline markers
  needed? — decide from Phase 5.
- Does prompt v1 actually beat v0? Both are available and the sweep is
  resumable, so this is a cheap A/B once the case set exists — not an
  assumption baked into the baseline.
- Does the explore set's pop-culture skew (13 of 20 are entertainment or sport)
  exercise retrieval differently from the encyclopedic core set? — read pass
  will show it, and it's a property of real queries, not a flaw in the draw.

---

## 9. Non-goals

Vector search / embeddings · multi-agent · web UI · production-grade retrieval ·
fine-tuning · running the agent through Claude Code (§3.4). The assignment
directs effort to prompt quality and eval design.
