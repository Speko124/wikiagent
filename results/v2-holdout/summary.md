# Sweep summary

> **HOLDOUT — metrics only.** Do not open the traces for error analysis until the comparison this set exists to make has been made. Reading them turns the holdout into training data, and nothing downstream can detect that it happened.

**Model** `claude-haiku-4-5` · **prompt** `v2` · **top_k** 3 · **tools** on · **repeats** 3 · **effort** —

**Runs** 30 total, 0 errored (errors are excluded from every rate below).

## Deterministic signals

- Searched at all: 30/30 (100%)
- Gold article shown to the model: 27/30 (90%) — denominator is runs whose case has a gold article
- Gold fetched but past top_k (raising top_k would have helped): 1
- Named a retrieved article: 21/30 (70%)
- Turns: median 2, max 8
- Tokens: 213,669 in / 7,455 out
- Latency: median 2.4s

## Retrieval by case

| case | gold shown | bucket |
|---|---|---|
| hd-006 | 1/3 | flaky |
| hd-010 | 2/3 | flaky |
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
