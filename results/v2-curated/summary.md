# Sweep summary

**Model** `claude-haiku-4-5` · **prompt** `v2` · **top_k** 3 · **tools** on · **repeats** 3 · **effort** —

**Runs** 54 total, 0 errored (errors are excluded from every rate below).

## Deterministic signals

- Searched at all: 51/54 (94%)
- Reference article shown to the model: 42/45 (93%) — a weak proxy kept for cases with no checkable answer string; `evidence_match` in the cross-arm report is the retrieval metric
- Gold fetched but past top_k (raising top_k would have helped): 0
- Named a retrieved article: 45/54 (83%)
- Turns: median 2, max 8
- Tokens: 353,347 in / 13,531 out
- Latency: median 3.2s

## Outcome decomposition

Mutually exclusive and exhaustive; sums to every attempted run.

- confirmed success: 49
- wrong answer: 1
- answerable non-answer: 4
- evaluator unresolved: 0
- execution failure: 0
- *total: 54 of 54 runs*

## What each failure implies

- retrieval / selection / truncation / source format: 4
- synthesis or reasoning: 1

## Retrieval by case

| case | gold shown | bucket |
|---|---|---|
| switzerland-borders | 0/3 | systematic |
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

Judged by `claude-sonnet-5` rubric `j2`; see `results.jsonl`.
