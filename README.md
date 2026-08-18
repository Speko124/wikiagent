# wikiagent

A Claude agent that answers questions using Wikipedia, and an eval suite that
measures how well it does.

Two tools, an explicit agent loop, and a harness built so that every number can
be traced back to the exact bytes the model saw.

---

## Setup

Needs Python 3.11+ and an Anthropic API key.

```bash
git clone https://github.com/Speko124/wikiagent.git && cd wikiagent
uv sync                                    # or: pip install -e ".[dev]"
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env # or export it
```

No other services, no index to build, no database. Wikipedia is read live from
the MediaWiki API and cached on disk under `cache/`.

## See it work

```bash
uv run python -m wikiagent.cli demo
```

Six questions, chosen so the interesting behaviour is visible in one screen: a
plain lookup, a two-article join, a fact that lives in an article's body rather
than its opening section, an ambiguous entity, a false premise, and a question
Wikipedia cannot answer at all.

Single questions:

```bash
uv run python -m wikiagent.cli ask "How tall is the Eiffel Tower?"
uv run python -m wikiagent.cli ask "name of toy store in home alone 2" -v
```

Every answer prints what was **searched** and what was **retrieved**, kept
separate from what the model claims it used — the harness knows the first two
for certain and only the model knows the third.

`-v` shows everything: each turn, each query, every result including the ones
fetched but never shown to the model, and the exact string handed back as the
tool result.

Useful flags: `--prompt v0` (the pre-`fetch_article` baseline) · `--no-tools`
(answer from memory only) · `--top-k N` · `--json` · `--save PATH` ·
`--model claude-sonnet-5`.

## Tests

```bash
uv run pytest -q                       # 272 tests, no API key, no network, <1s
WIKIAGENT_NETWORK=1 uv run pytest -q   # + 4 live Wikipedia tests
```

The suite runs with a stubbed Anthropic client, so it needs neither a key nor a
network. It is weighted toward invariants whose failure would be **silent**
rather than loud — cache integrity, `None` never being read as `False`, the
control arm being structurally unable to retrieve, frozen prompts and rubrics,
and the holdout being unreadable. Several of these exist because the
corresponding bug actually happened; see [docs/README.md](docs/README.md).

## Running the evals

```bash
# read pass: one run per case, produces a human-readable worksheet
uv run python -m evals.run --cases evals/cases/core.jsonl --repeats 1

# score pass: three runs per case, with the LLM judge
uv run python -m evals.run --cases evals/cases/core.jsonl --repeats 3

# held-out set: metrics only, no worksheet, no label file
uv run python -m evals.run --cases evals/cases/holdout.jsonl --repeats 3 --holdout

# compare the two arms
uv run python -m evals.report results/<curated-dir> results/<holdout-dir>
```

A sweep writes one directory: full traces, a machine-readable `results.jsonl`, a
`review.md` worksheet for reading by hand, a seeded `labels.jsonl` for verdicts,
and `summary.md`. Sweeps resume — pass an existing `--out` and it runs only what
is missing. `evals/regrade.py` re-scores a finished sweep from its saved traces
with no API calls, so a grader fix never costs a re-run.

Committed results: `results/v0-*` (baseline), `results/v1-*` and `results/v1b-*`
(after `fetch_article`, run twice).

---

## How it works

```
wikiagent/
  wikipedia.py   MediaWiki API + on-disk cache
  tools.py       tool schemas + dispatch
  prompts.py     system prompt AND tool descriptions, versioned together
  agent.py       explicit tool-use loop, emits a Trace
  trace.py       everything one run did
  cli.py         ask / demo / --verbose
evals/
  cases/         18 curated + 20 explore + 10 holdout
  graders.py     exact signals only
  judge.py       ambiguity (owned) + correctness (primary), rubric-versioned
  run.py         resumable sweep runner
  report.py      cross-arm report, funnel, pass^k
  regrade.py     re-score from traces, no API calls
```

**Two tools.** `search_wikipedia(query)` returns the opening section of the top
3 matching articles. `fetch_article(title, pageid)` opens one article in full.
The second exists because the evals said so — see below.

**The cache is a correctness requirement, not an optimisation.** Live Wikipedia
changes underneath repeated runs, so without it a score delta can't be
attributed to a prompt change. Errors are never cached: one network blip must
not poison a query forever.

**Fetch more than you show.** Search always retrieves at least 5 results and
renders `top_k` (default 3). The surplus is cached and traced but never enters
the prompt, so "would showing more have helped?" is answerable from traces we
already have, at zero extra cost.

---

## What the evals found

Three iterations. Each number below comes from a committed sweep in `results/`.

| | Curated | Held out | pass^3 | Body-fact failures |
|---|---|---|---|---|
| **Pre-baseline** (never scored) | — | — | — | — |
| **V0** search only | 71% | 81% | 12/18 | 15 |
| **V1** + `fetch_article` | **89%** | **93%** | 15/18 | 5 |
| **V1 repeat** (same prompt digest) | **89%** | 92% | 15/18 | 5 |
| **V2** generalised escalation | **91%** | **93%** | 15/18 | 4 |

**The dominant failure was retrieval depth, and it was found by random
questions rather than by the ones we wrote.** Of six failures in a 20-question
random sample from Natural Questions, five were identical: the right article
was retrieved, and the answer lived in the article body, which the tool never
fetched. Our hand-written set surfaced none of it — real users ask about cast
members, filming locations and counts, and that material sits below the intro.

Adding `fetch_article` moved correctness +18 points on the curated set and +12
on questions never read during development, with zero regressions among cases
that already passed. The tool is used selectively — about a third of runs, only
where the intro genuinely lacked the answer — and costs exactly one extra turn
when used.

**Where it still fails**, and both are now understood precisely:

- The 8,000-character fetch cap is the binding constraint. 19 of 22 fetches came
  back truncated, and the agent then asserts facts are *absent from the article*
  having read only part of it.
- One case's answer sits at offset ~15,650 of a 44,579-character article — in
  the prose, past what we read.

**Grounding was never the problem.** Zero fabricated claims and zero fabricated
citations across 138 runs. Every specific figure spot-checked against the
rendered tool output was present in it.

**Where the failures sat, by funnel stage** — attribution is computed from
exact signals, not hand-labelled:

| Stage | v0 | v1 | v2 |
|---|---|---|---|
| 1 · query — never searched | 0 | 0 | 0 |
| 2 · retrieval — article never surfaced | 0 | 1 | 0 |
| **3 · evidence — fact not in the returned text** | **15** | **5** | **4** |
| 4 · synthesis — had it, joined it wrong | 0 | 0 | 1 |
| 5 · grounding — claimed what wasn't there | **0** | **0** | **0** |
| correct | 37 | 47 | 49 |

*(curated arm, 54 runs each)*

One stage held everything, and the stage everyone expects to dominate —
hallucination — never appeared at all. That is what made the fix obvious, and
the fix moved the stage it targeted while the others stayed flat.

Full analysis: [docs/design-rationale.md](docs/design-rationale.md) ·
[docs/error-analysis.md](docs/error-analysis.md) ·
[docs/v1-trace-review.md](docs/v1-trace-review.md) ·
[docs/v1b-trace-review.md](docs/v1b-trace-review.md)

## How quality is measured

**Deterministic wherever possible.** Correctness is checked against
hand-authored accepted phrasings; retrieval quality against whether the
retrieved text actually carried the evidence, matched per tool call and
accumulated across calls, so a multi-hop question is not blamed on retrieval.
Crossing the two gives the funnel stage exactly:

| | evidence found | not found |
|---|---|---|
| **answer right** | grounded | answered from memory |
| **answer wrong** | had it, didn't use it | never had it |

**An LLM judge where determinism was measured to fail.** Correctness is
judge-primary with the string matcher kept as a guardrail — the matcher
produced three silent false passes on 54 runs and the judge caught all three.
Ambiguity is judged because the obvious deterministic proxy was tested and
misfired in both directions. The judge is Sonnet 5 judging Haiku 4.5, rubric
frozen and digest-tested, calibrated at 51/54 against hand labels with **zero
cases where it said `correct` and a human said `incorrect`**.

**The variance floor is measured, not assumed.** Two identical sweeps agree on
54/54 deterministic verdicts and differ on 2 judged runs — both on the one case
whose answer does not exist in Wikipedia. Variance is concentrated: zero flips
across 39 runs on cases with a reachable answer. An improvement smaller than
about one whole case is not distinguishable from noise on this set.

## Guarantees worth knowing about

- **Frozen artifacts.** Prompts, judge rubrics and the random question sets are
  digest-tested. A calibrated rubric that gets edited detaches from the
  calibration describing it, while every row still names it.
- **The holdout cannot be read.** `--holdout` suppresses the review worksheet
  and label file entirely, and the cross-arm report emits holdout aggregates
  only — no case ids, no answers, no judge rationales. Enforced by tests, since
  a holdout you have analysed is training data.
- **Sweeps are resumable and failure-isolated**, errored runs are retried
  rather than frozen in, and a resume refuses a changed config.
- **Grader bugs cost a re-grade, not a re-run** — `evals/regrade.py` rebuilds
  results from saved traces with no API calls, carrying paid-for judge verdicts
  over untouched.

---

## Where to read more

| Doc | What it holds |
|---|---|
| [design-rationale.md](docs/design-rationale.md) | **Start here.** Why every choice was made, and what three iterations found |
| [error-analysis.md](docs/error-analysis.md) | The failure taxonomy, built from reading traces |
| [eval-plan.md](docs/eval-plan.md) | Case set, rubric, and the backlog of candidate fixes |
| [project.md](docs/project.md) | Living spec — every decision as it was taken |
| [prompt-archive.md](docs/prompt-archive.md) | Replaced prompts and the defects that replaced them |
| v1 / v1b / v2 trace reviews | Per-sweep analysis, including the ones that found bugs in the eval itself |

