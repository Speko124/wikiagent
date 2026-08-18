# Sweep summary

> **HOLDOUT — metrics only.** Do not open the traces for error analysis until the comparison this set exists to make has been made. Reading them turns the holdout into training data, and nothing downstream can detect that it happened.

**Model** `claude-haiku-4-5` · **prompt** `v1` · **top_k** 3 · **tools** on · **repeats** 3 · **effort** —

**Runs** 30 total, 0 errored (errors are excluded from every rate below).

## Deterministic signals

- Searched at all: 30/30 (100%)
- Gold article shown to the model: 25/30 (83%) — denominator is runs whose case has a gold article
- Gold fetched but past top_k (raising top_k would have helped): 0
- Named a retrieved article: 23/30 (77%)
- Turns: median 2, max 9
- Tokens: 212,342 in / 7,508 out
- Latency: median 3.2s

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

Judged by `claude-sonnet-5` rubric `j2`; see `results.jsonl`.
