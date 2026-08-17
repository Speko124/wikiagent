# V0 baseline

`claude-haiku-4-5` · prompt `v0` · top_k 3 · 3x per case

| Metric | Curated | Holdout |
|---|---|---|
| Runs | 54 | 30 |
| Correct (deterministic) | 28/42 (67%) | 23/30 (77%) |
| **pass^k** (correct on every repeat) | 9/14 (64%) | 7/10 (70%) |
|   of which | 9 solid (k/k) · 1 flaky · 4 systematic (0/k) | 7 solid (k/k) · 1 flaky · 2 systematic (0/k) |
| Evidence retrieved | 27/39 (69%) | 24/30 (80%) |
| Answer completeness (mean) | 70% | 77% |
| Searched at all | 51/54 (94%) | 30/30 (100%) |
| Searches per run | 1.5 | 1.2 |
| Articles named per answer | 1.5 | 1.2 |
| Answer length (chars) | 496 | 399 |
| Output tokens | 223 | 194 |
| Latency (median s) | 3.4 | 3.1 |
| Judge/matcher disagreements | 0/39 | 0/23 |
| Judge unclear, matcher confident | 11 | 7 |
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
| 2 retrieval: the answer-bearing article never surfaced | 0 | 3 |
| 3 evidence: right article, fact not in the retrieved text | 12 | 3 |
| 4 synthesis: had the evidence, answered wrong | 2 | 1 |
| 5 grounding: answered from memory | 0 | 0 |
| correct, grounded | 25 | 23 |
| correct, evidence not checkable | 3 | 0 |
| not scorable (abstention cases) | 12 | 0 |

## Curated, by case

| case | correct | bucket |
|---|---|---|
| arpanet-first-message | 0/3 | systematic |
| head-of-class-eric | 0/3 | systematic |
| home-alone-toy-store | 0/3 | systematic |
| lets-make-a-deal-location | 0/3 | systematic |
| tesla-origin | 1/3 | flaky |
| bologna-oxford-older | 3/3 | solid |
| eiffel-height | 3/3 | solid |
| einstein-nobel-control | 3/3 | solid |
| einstein-nobel-premise | 3/3 | solid |
| rosetta-year | 3/3 | solid |
| straw-doll-village | 3/3 | solid |
| switzerland-borders | 3/3 | solid |
| tosca-nationality | 3/3 | solid |
| turing-nobel | 3/3 | solid |

## Judge declined, matcher was confident (curated)

The audit's most useful cell. A confident deterministic verdict the judge would not endorse is where an accepted phrasing is matching text that does not answer the question.

- `tesla-origin#1` — matcher `False`, judge `unclear`: The question is ambiguous between Tesla, Inc. and Nikola Tesla, and the answer only addresses one reading (Tesla, Inc.), correctly noting it is American and headquartered in Austin, Texas, but omits the Nikola Tesla interpretation the reference calls for.
- `tesla-origin#2` — matcher `False`, judge `unclear`: The answer only addresses Nikola Tesla (with a minor error: he was born in the Austrian Empire, not Austro-Hungarian, which formed in 1867) and omits the Tesla, Inc. reading, so it's a partial/ambiguous match to the reference.
- `arpanet-first-message#0` — matcher `False`, judge `unclear`: The answer honestly reports not finding the specific information rather than providing incorrect facts, so it should be marked unclear rather than incorrect.
- `arpanet-first-message#2` — matcher `False`, judge `unclear`: The answer declines to provide the information rather than stating it incorrectly, so it should be treated as unclear/not-found rather than wrong.
- `head-of-class-eric#0` — matcher `False`, judge `unclear`: The answer declines to provide the information rather than giving an incorrect fact, so it should be judged as unclear rather than incorrect.
- `head-of-class-eric#1` — matcher `False`, judge `unclear`: The answer declines to provide the information, honestly stating it could not find it, rather than giving an incorrect answer.
- `head-of-class-eric#2` — matcher `False`, judge `unclear`: The answer declines to provide the information rather than giving an incorrect fact, so it should be judged as unclear rather than incorrect.
- `lets-make-a-deal-location#0` — matcher `False`, judge `unclear`: The answer declines to provide the information rather than giving an incorrect fact, so it should be marked unclear rather than incorrect.
- `lets-make-a-deal-location#1` — matcher `False`, judge `unclear`: The answer declines to provide the specific filming location, honestly reporting it couldn't confirm the information rather than giving an incorrect answer.
- `lets-make-a-deal-location#2` — matcher `False`, judge `unclear`: The answer honestly reports not finding the specific filming location rather than providing incorrect information, so it should be treated as unclear rather than incorrect.
- `home-alone-toy-store#0` — matcher `False`, judge `unclear`: The answer declines to provide the correct name (Duncan's Toy Chest) despite the information being genuinely available, but since it explicitly reports not finding it rather than giving wrong info, this falls into the unclear/honest-non-answer category.

## Holdout

**Aggregate values only, deliberately.** No case ids, answers or judge rationales appear here. A named failing holdout case is a lead, and following it turns the holdout into training data with nothing downstream able to detect it. Read the numbers in the table above; open nothing else until the V0 → V1 comparison this arm exists to make has been made.

- 30 runs, 0 errors
- judge/matcher disagreements: 0/23; judge unclear while matcher confident: 7 (counts only — the cases are not listed)
