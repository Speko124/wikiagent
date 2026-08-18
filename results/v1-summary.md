# V0 baseline

`claude-haiku-4-5` · prompt `v1` · top_k 3 · 3x per case

| Metric | Curated | Holdout |
|---|---|---|
| Runs | 54 | 30 |
| **Correct** (judge, primary) | 44/50 (88%) | 25/27 (93%) |
| Correct (contains, guardrail) | 39/44 (89%) | 27/30 (90%) |
| Guardrail disagrees with judge | 0 | 2 |
| **pass^k** (correct on every repeat) | 14/17 (82%) | 9/10 (90%) |
|   of which | 14 solid (k/k) · 1 flaky · 2 systematic (0/k) | 9 solid (k/k) · 0 flaky · 1 systematic (0/k) |
| Evidence retrieved | 36/41 (88%) | 29/30 (97%) |
| Answer completeness (mean) | 89% | 90% |
| Searched at all | 50/53 (94%) | 30/30 (100%) |
| Searches per run | 1.4 | 1.4 |
| Turns | 2.6 mean, 9 max | 2.7 mean, 10 max |
| Runs that opened an article | 17/53 (32%) | 7/30 (23%) |
| Fetches per run | 0.36 | 0.27 |
| Failed fetches | 0 | 0 |
| Fetches with no prior search | 0 | 0 |
| Articles named per answer | 1.3 | 1.3 |
| Answer length (chars) | 447 | 386 |
| Output tokens | 234 | 240 |
| Latency (median s) | 3.1 | 2.9 |
| Judge/matcher disagreements | 0/37 | 1/25 |
| Judge unclear, matcher confident | 3 | 3 |
| Errors | 1 | 0 |

## Answer × evidence

| Cell | Meaning | Curated | Holdout |
|---|---|---|---|
| grounded | right, and the evidence was there | 36 | 27 |
| from memory | **right without the evidence — not grounded** | 0 | 0 |
| evidence unused | **had the evidence, still wrong** | 0 | 2 |
| neither | never had the evidence | 5 | 1 |

## Funnel

Computed from `answer_match`, `evidence_match` and `searched` — the same attribution the read pass needed a human to make.

| Stage | Curated | Holdout |
|---|---|---|
| 1 query: did not search at all | 0 | 0 |
| 2 retrieval: the answer-bearing article never surfaced | 1 | 0 |
| 3 evidence: right article, fact not in the retrieved text | 5 | 0 |
| 4 synthesis: had the evidence, answered wrong | 0 | 2 |
| 5 grounding: answered from memory | 0 | 0 |
| correct, grounded | 33 | 25 |
| correct, evidence not checkable | 11 | 0 |
| not scorable (abstention cases) | 3 | 3 |

## Curated, by case

| case | correct | bucket |
|---|---|---|
| arpanet-first-message | 0/2 | systematic |
| lets-make-a-deal-location | 0/3 | systematic |
| am-i-all-alone-writer | 2/3 | flaky |
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

## Judge declined, matcher was confident (curated)

The audit's most useful cell. A confident deterministic verdict the judge would not endorse is where an accepted phrasing is matching text that does not answer the question.

- `beat-bobby-flay-wins#0` — matcher `True`, judge `unclear`: The reference states no figure is available without manual counting, while the answer provides a specific record; since it's uncertain if this figure is accurate or verifiable, this falls into a disputed/unclear category rather than a clear correctness judgment.
- `beat-bobby-flay-wins#1` — matcher `True`, judge `unclear`: The reference indicates no single figure is stated, while the answer provides specific numbers not verifiable against the reference, making it impossible to confirm correctness.
- `beat-bobby-flay-wins#2` — matcher `True`, judge `unclear`: The reference claims no figure exists, but the answer provides a specific sourced statistic (330-198 record) which may actually be accurate and answer the question, making this a case where the reference itself appears incomplete or outdated.

## Holdout

**Aggregate values only, deliberately.** No case ids, answers or judge rationales appear here. A named failing holdout case is a lead, and following it turns the holdout into training data with nothing downstream able to detect it. Read the numbers in the table above; open nothing else until the V0 → V1 comparison this arm exists to make has been made.

- 30 runs, 0 errors
- judge/matcher disagreements: 1/25; judge unclear while matcher confident: 3 (counts only — the cases are not listed)
