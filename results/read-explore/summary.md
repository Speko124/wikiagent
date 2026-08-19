# Sweep summary

**Model** `claude-haiku-4-5` · **prompt** `v0` · **top_k** 3 · **tools** on · **repeats** 1 · **effort** —

**Runs** 20 total, 0 errored (errors are excluded from every rate below).

## Deterministic signals

- Searched at all: 20/20 (100%)
- Reference article shown to the model: n/a (0 runs) — a weak proxy kept for cases with no checkable answer string; `evidence_match` in the cross-arm report is the retrieval metric
- Gold fetched but past top_k (raising top_k would have helped): 0
- Named a retrieved article: 18/20 (90%)
- Turns: median 2, max 6
- Tokens: 80,575 in / 4,364 out
- Latency: median 3.3s

## Outcome decomposition

Mutually exclusive and exhaustive; sums to every attempted run.

- confirmed success: 0
- wrong answer: 0
- answerable non-answer: 0
- evaluator unresolved: 20
- execution failure: 0
- *total: 20 of 20 runs*

## What each failure implies

- judge rubric / reference answer / ambiguity: 20

## Not measured here

Correctness, faithfulness and posture are **not measured** — no judge ran for this sweep. Nothing above is an answer-quality score.
