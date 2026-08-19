# Sweep summary

**Model** `claude-haiku-4-5` · **prompt** `v0` · **top_k** 3 · **tools** on · **repeats** 3 · **effort** —

**Runs** 54 total, 0 errored (errors are excluded from every rate below).

## Deterministic signals

- Searched at all: 51/54 (94%)
- Reference article shown to the model: 43/45 (96%) — a weak proxy kept for cases with no checkable answer string; `evidence_match` in the cross-arm report is the retrieval metric
- Gold fetched but past top_k (raising top_k would have helped): 0
- Named a retrieved article: 51/54 (94%)
- Turns: median 2, max 5
- Tokens: 210,686 in / 12,045 out
- Latency: median 3.4s

## Outcome decomposition

Mutually exclusive and exhaustive; sums to every attempted run.

- confirmed success: 37
- wrong answer: 2
- answerable non-answer: 13
- evaluator unresolved: 2
- execution failure: 0
- *total: 54 of 54 runs*

## What each failure implies

- Retrieval / Evidence — no answer-bearing text reached the model: 15
- Evaluator — judge rubric, reference answer, or ambiguity: 2

## Retrieval by case

| case | gold shown | bucket |
|---|---|---|
| switzerland-borders | 1/3 | flaky |
| rosetta-year | 3/3 | solid |
| eiffel-height | 3/3 | solid |
| tosca-nationality | 3/3 | solid |
| bologna-oxford-older | 3/3 | solid |
| tesla-origin | 3/3 | solid |
| straw-doll-village | 3/3 | solid |
| arpanet-first-message | 3/3 | solid |
| einstein-nobel-premise | 3/3 | solid |
| einstein-nobel-control | 3/3 | solid |
| turing-nobel | 3/3 | solid |
| head-of-class-eric | 3/3 | solid |
| lets-make-a-deal-location | 3/3 | solid |
| home-alone-toy-store | 3/3 | solid |
| beat-bobby-flay-wins | 3/3 | solid |

## Not measured here

Judged by `claude-sonnet-5` rubric `j1`; see `results.jsonl`.
