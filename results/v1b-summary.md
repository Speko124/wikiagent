# Sweep report — prompt `v1`

`claude-haiku-4-5` · prompt `v1` · top_k 3 · 3x per case

| Metric | Curated | Holdout |
|---|---|---|
| Runs | 54 | 30 |
| **Correct** (judge, primary) | 47/53 (89%) | 24/26 (92%) |
| Correct (contains, guardrail) | 39/45 (87%) | 26/30 (87%) |
| Guardrail disagrees with judge | 0 | 1 |
| **pass^k** (correct on every repeat) | 15/18 (83%) | 8/9 (89%) |
|   of which | 15 solid (k/k) · 0 flaky · 2 systematic (0/k) · 1 incomplete | 8 solid (k/k) · 0 flaky · 0 systematic (0/k) · 1 incomplete |
| Evidence retrieved | 36/42 (86%) | 30/30 (100%) |
| Answer completeness (mean) | 87% | 87% |
| Searched at all | 51/54 (94%) | 30/30 (100%) |
| Searches per run | 1.5 | 1.4 |
| Turns | 2.8 mean, 10 max | 2.7 mean, 9 max |
| Runs that opened an article | 19/54 (35%) | 8/30 (27%) |
| Fetches per run | 0.41 | 0.30 |
| Fetches per run (spread) | 0x35 · 1x16 · 2x3 | 0x22 · 1x7 · 2x1 |
| Turns by fetch count | 0 fetch: 2.1t · 1 fetch: 3.1t · 2 fetch: 9.3t | 0 fetch: 2.1t · 1 fetch: 3.7t · 2 fetch: 9.0t |
| Failed fetches | 0 | 0 |
| Fetches with no prior search | 0 | 0 |
| Articles named per answer | 1.4 | 1.2 |
| Answer length (chars) | 460 | 418 |
| Output tokens | 247 | 250 |
| Latency (median s) | 3.2 | 3.2 |
| Judge/matcher disagreements | 0/40 | 0/25 |
| Judge unclear, matcher confident | 0 | 4 |
| Errors | 0 | 0 |

## Answer × evidence

| Cell | Meaning | Curated | Holdout |
|---|---|---|---|
| grounded | right, and the evidence was there | 36 | 26 |
| from memory | **right without the evidence — not grounded** | 0 | 0 |
| evidence unused | **had the evidence, still wrong** | 0 | 4 |
| neither | never had the evidence | 6 | 0 |

## Funnel

Computed from `answer_match`, `evidence_match` and `searched` — the same attribution the read pass needed a human to make.

| Stage | Curated | Holdout |
|---|---|---|
| 1 query: did not search at all | 0 | 0 |
| 2 retrieval: the answer-bearing article never surfaced | 0 | 0 |
| 3 evidence: right article, fact not in the retrieved text | 6 | 0 |
| 4 synthesis: had the evidence, answered wrong | 0 | 2 |
| 5 grounding: answered from memory | 0 | 0 |
| correct, grounded | 36 | 24 |
| correct, evidence not checkable | 11 | 0 |
| not scorable (abstention cases) | 1 | 4 |

## Curated, by case

| case | correct | bucket |
|---|---|---|
| arpanet-first-message | 0/3 | systematic |
| lets-make-a-deal-location | 0/3 | systematic |
| am-i-all-alone-writer | 2/2 | solid |
| beat-bobby-flay-wins | 3/3 | solid |
| beethoven-premiere-attendance | 3/3 | solid |
| bologna-oxford-older | 3/3 | solid |
| eiffel-height | 3/3 | solid |
| einstein-nobel-control | 3/3 | solid |
| einstein-nobel-premise | 3/3 | solid |
| head-of-class-eric | 3/3 | solid |
| home-alone-toy-store | 3/3 | solid |
| paris-weather | 3/3 | solid |
| rosetta-year | 3/3 | solid |
| straw-doll-village | 3/3 | solid |
| switzerland-borders | 3/3 | solid |
| tesla-origin | 3/3 | solid |
| tosca-nationality | 3/3 | solid |
| turing-nobel | 3/3 | solid |

## Holdout

**Aggregate values only, deliberately.** No case ids, answers or judge rationales appear here. A named failing holdout case is a lead, and following it turns the holdout into training data with nothing downstream able to detect it. Read the numbers in the table above; open nothing else until the V0 → V1 comparison this arm exists to make has been made.

- 30 runs, 0 errors
- judge/matcher disagreements: 0/25; judge unclear while matcher confident: 4 (counts only — the cases are not listed)
