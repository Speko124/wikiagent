# Sweep summary

> **HOLDOUT — metrics only.** Do not open the traces for error analysis until the comparison this set exists to make has been made. Reading them turns the holdout into training data, and nothing downstream can detect that it happened.

**Model** `claude-haiku-4-5` · **prompt** `v0` · **top_k** 3 · **tools** on · **repeats** 3 · **effort** —

**Runs** 30 total, 0 errored (errors are excluded from every rate below).

## Deterministic signals

- Searched at all: 30/30 (100%)
- Reference article shown to the model: 25/30 (83%) — a weak proxy kept for cases with no checkable answer string; `evidence_match` in the cross-arm report is the retrieval metric
- Gold fetched but past top_k (raising top_k would have helped): 2
- Named a retrieved article: 22/30 (73%)
- Turns: median 2, max 4
- Tokens: 96,815 in / 5,826 out
- Latency: median 3.1s

## Outcome decomposition

Mutually exclusive and exhaustive; sums to every attempted run.

- confirmed success: 21
- wrong answer: 2
- answerable non-answer: 3
- evaluator unresolved: 4
- execution failure: 0
- *total: 30 of 30 runs*

## What each failure implies

- retrieval / selection / truncation / source format: 5
- judge rubric / reference answer / ambiguity: 4

## Retrieval by case

| case | gold shown | bucket |
|---|---|---|
| hd-006 | 0/3 | systematic |
| hd-010 | 1/3 | flaky |
| hd-001 | 3/3 | solid |
| hd-002 | 3/3 | solid |
| hd-003 | 3/3 | solid |
| hd-004 | 3/3 | solid |
| hd-005 | 3/3 | solid |
| hd-007 | 3/3 | solid |
| hd-008 | 3/3 | solid |
| hd-009 | 3/3 | solid |

## Not measured here

Judged by `claude-sonnet-5` rubric `j1`; see `results.jsonl`.
