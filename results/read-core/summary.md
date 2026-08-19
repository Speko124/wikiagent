# Sweep summary

**Model** `claude-haiku-4-5` · **prompt** `v0` · **top_k** 3 · **tools** on · **repeats** 1 · **effort** —

**Runs** 11 total, 0 errored (errors are excluded from every rate below).

## Deterministic signals

- Searched at all: 9/11 (82%)
- Reference article shown to the model: 7/9 (78%) — a weak proxy kept for cases with no checkable answer string; `evidence_match` in the cross-arm report is the retrieval metric
- Gold fetched but past top_k (raising top_k would have helped): 0
- Named a retrieved article: 9/11 (82%)
- Turns: median 2, max 3
- Tokens: 28,135 in / 1,710 out
- Latency: median 2.7s

## Outcome decomposition

Mutually exclusive and exhaustive; sums to every attempted run.

- confirmed success: 0
- wrong answer: 0
- answerable non-answer: 0
- evaluator unresolved: 11
- execution failure: 0
- *total: 11 of 11 runs*

## What each failure implies

- Evaluator — judge rubric, reference answer, or ambiguity: 11

## Retrieval by case

| case | gold shown | bucket |
|---|---|---|
| einstein-nobel-premise | 0/1 | systematic |
| switzerland-borders | 0/1 | systematic |
| rosetta-year | 1/1 | solid |
| tosca-nationality | 1/1 | solid |
| opera-house-seats | 1/1 | solid |
| tesla-origin | 1/1 | solid |
| eiffel-height | 1/1 | solid |
| turing-nobel | 1/1 | solid |
| straw-doll-village | 1/1 | solid |

## Not measured here

Correctness, faithfulness and posture are **not measured** — no judge ran for this sweep. Nothing above is an answer-quality score.
