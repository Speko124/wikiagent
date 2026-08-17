# V0 baseline

`claude-haiku-4-5` · prompt `v0` · top_k 3 · 3x per case

| Metric | Curated | Holdout |
|---|---|---|
| Runs | 54 | 30 |
| **Correct** (judge, primary) | 37/52 (71%) | 21/26 (81%) |
| Correct (contains, guardrail) | 28/42 (67%) | 23/30 (77%) |
| Guardrail disagrees with judge | 0 | 0 |
| **pass^k** (correct on every repeat) | 13/18 (72%) | 7/9 (78%) |
|   of which | 13 solid (k/k) · 0 flaky · 5 systematic (0/k) | 7 solid (k/k) · 0 flaky · 2 systematic (0/k) |
| Evidence retrieved | 27/39 (69%) | 24/30 (80%) |
| Answer completeness (mean) | 70% | 77% |
| Searched at all | 51/54 (94%) | 30/30 (100%) |
| Searches per run | 1.5 | 1.2 |
| Articles named per answer | 1.5 | 1.2 |
| Answer length (chars) | 496 | 399 |
| Output tokens | 223 | 194 |
| Latency (median s) | 3.4 | 3.1 |
| Judge/matcher disagreements | 0/31 | 0/23 |
| Judge unclear, matcher confident | 2 | 4 |
| Errors | 0 | 0 |

## Answer × evidence

| Cell | Meaning | Curated | Holdout |
|---|---|---|---|
| grounded | right, and the evidence was there | 25 | 23 |
| from memory | **right without the evidence — not grounded** | 0 | 0 |
| evidence unused | **had the evidence, still wrong** | 2 | 1 |
| neither | never had the evidence | 12 | 6 |

## Funnel

Computed from `answer_match`, `evidence_match` and `searched` — the same attribution the read pass needed a human to make.

| Stage | Curated | Holdout |
|---|---|---|
| 1 query: did not search at all | 0 | 0 |
| 2 retrieval: the answer-bearing article never surfaced | 0 | 2 |
| 3 evidence: right article, fact not in the retrieved text | 15 | 3 |
| 4 synthesis: had the evidence, answered wrong | 0 | 0 |
| 5 grounding: answered from memory | 0 | 0 |
| correct, grounded | 25 | 21 |
| correct, evidence not checkable | 12 | 0 |
| not scorable (abstention cases) | 2 | 4 |

## Curated, by case

| case | correct | bucket |
|---|---|---|
| arpanet-first-message | 0/3 | systematic |
| beat-bobby-flay-wins | 0/3 | systematic |
| head-of-class-eric | 0/3 | systematic |
| home-alone-toy-store | 0/3 | systematic |
| lets-make-a-deal-location | 0/3 | systematic |
| am-i-all-alone-writer | 3/3 | solid |
| beethoven-premiere-attendance | 3/3 | solid |
| bologna-oxford-older | 3/3 | solid |
| eiffel-height | 3/3 | solid |
| einstein-nobel-control | 3/3 | solid |
| einstein-nobel-premise | 3/3 | solid |
| paris-weather | 3/3 | solid |
| rosetta-year | 3/3 | solid |
| straw-doll-village | 3/3 | solid |
| switzerland-borders | 3/3 | solid |
| tesla-origin | 1/1 | solid |
| tosca-nationality | 3/3 | solid |
| turing-nobel | 3/3 | solid |

## Judge declined, matcher was confident (curated)

The audit's most useful cell. A confident deterministic verdict the judge would not endorse is where an accepted phrasing is matching text that does not answer the question.

- `tesla-origin#1` — matcher `False`, judge `unclear`: The question is ambiguous per the reference, but the answer addresses only the Tesla, Inc. reading correctly without covering Nikola Tesla, matching one valid interpretation.
- `tesla-origin#2` — matcher `False`, judge `unclear`: The question is ambiguous between Tesla Inc. and Nikola Tesla, and the answer only addresses one reading (Nikola Tesla) without acknowledging the ambiguity, and also slightly misstates the political entity (Austrian Empire vs Austro-Hungarian Empire at time of birth).

## Holdout

**Aggregate values only, deliberately.** No case ids, answers or judge rationales appear here. A named failing holdout case is a lead, and following it turns the holdout into training data with nothing downstream able to detect it. Read the numbers in the table above; open nothing else until the V0 → V1 comparison this arm exists to make has been made.

- 30 runs, 0 errors
- judge/matcher disagreements: 0/23; judge unclear while matcher confident: 4 (counts only — the cases are not listed)
