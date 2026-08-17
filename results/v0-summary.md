# V0 baseline

`claude-haiku-4-5` · prompt `v0` · top_k 3 · 3x per case

| Metric | Curated | Holdout |
|---|---|---|
| Runs | 54 | 30 |
| Correct (deterministic) | 31/42 (74%) | 23/30 (77%) |
| Evidence retrieved | 27/39 (69%) | 24/30 (80%) |
| Answer completeness (mean) | 75% | 77% |
| Searched at all | 51/54 (94%) | 30/30 (100%) |
| Searches per run | 1.5 | 1.2 |
| Articles named per answer | 1.6 | 1.2 |
| Answer length (chars) | 496 | 399 |
| Output tokens | 223 | 194 |
| Latency (median s) | 3.4 | 3.1 |
| Judge/matcher disagreements | 0/39 | 0/23 |
| Errors | 0 | 0 |

## Answer × evidence

| Cell | Meaning | Curated | Holdout |
|---|---|---|---|
| grounded | right, and the evidence was there | 25 | 23 |
| from memory | **right without the evidence — not grounded** | 3 | 0 |
| evidence unused | **had the evidence, still wrong** | 2 | 1 |
| neither | never had the evidence | 9 | 6 |

## Funnel

Computed from `answer_match`, `evidence_match` and `searched` — the same attribution the read pass needed a human to make.

| Stage | Curated | Holdout |
|---|---|---|
| correct, grounded | 25 | 23 |
| correct, evidence not checkable | 3 | 0 |
| 5 grounding: answered from memory | 3 | 0 |
| 4 synthesis: had the evidence, answered wrong | 2 | 1 |
| 3 evidence: right article, fact not in the retrieved text | 9 | 3 |
| 2 retrieval: the answer-bearing article never surfaced | 0 | 3 |
| 1 query: did not search at all | 0 | 0 |
| not scorable (abstention cases) | 12 | 0 |

## Curated, by case

| case | correct | bucket |
|---|---|---|
| head-of-class-eric | 0/3 | systematic |
| home-alone-toy-store | 0/3 | systematic |
| lets-make-a-deal-location | 0/3 | systematic |
| arpanet-first-message | 2/3 | flaky |
| tesla-origin | 2/3 | flaky |
| bologna-oxford-older | 3/3 | solid |
| eiffel-height | 3/3 | solid |
| einstein-nobel-control | 3/3 | solid |
| einstein-nobel-premise | 3/3 | solid |
| rosetta-year | 3/3 | solid |
| straw-doll-village | 3/3 | solid |
| switzerland-borders | 3/3 | solid |
| tosca-nationality | 3/3 | solid |
| turing-nobel | 3/3 | solid |

## Holdout

**Aggregate values only, deliberately.** No case ids, answers or judge rationales appear here. A named failing holdout case is a lead, and following it turns the holdout into training data with nothing downstream able to detect it. Read the numbers in the table above; open nothing else until the V0 → V1 comparison this arm exists to make has been made.

- 30 runs, 0 errors
- judge/matcher disagreements: 0/23 (count only — the cases are not listed)
