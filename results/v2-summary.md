# Sweep report — prompt `v2`

`claude-haiku-4-5` · prompt `v2` · top_k 3 · 3x per case

| Metric | Curated | Holdout |
|---|---|---|
| Runs | 54 | 30 |
| **Correct** (judge, primary) | 49/54 (91%) | 26/28 (93%) |
| Correct (contains, guardrail) | 41/45 (91%) | 27/30 (90%) |
| Guardrail disagrees with judge | 1 | 0 |
| **pass^k** (correct on every repeat) | 15/18 (83%) | 9/10 (90%) |
|   of which | 15 solid (k/k) · 2 flaky · 1 systematic (0/k) | 9 solid (k/k) · 1 flaky · 0 systematic (0/k) |
| Evidence retrieved | 38/42 (90%) | 30/30 (100%) |
| Answer completeness (mean) | 91% | 90% |
| Searched at all | 51/54 (94%) | 30/30 (100%) |
| Searches per run | 1.4 | 1.3 |
| Turns | 2.7 mean, 8 max | 2.7 mean, 8 max |
| Runs that opened an article | 20/54 (37%) | 8/30 (27%) |
| Fetches per run | 0.43 | 0.37 |
| Fetches per run (spread) | 0x34 · 1x17 · 2x3 | 0x22 · 1x6 · 2x1 · 3x1 |
| Turns by fetch count | 0 fetch: 2.1t · 1 fetch: 3.2t · 2 fetch: 7.0t | 0 fetch: 2.0t · 1 fetch: 3.3t · 2 fetch: 8.0t · 3 fetch: 7.0t |
| Failed fetches | 0 | 0 |
| Fetches with no prior search | 0 | 0 |
| Articles named per answer | 1.3 | 1.1 |
| Answer length (chars) | 498 | 411 |
| Output tokens | 251 | 248 |
| Latency (median s) | 3.2 | 2.4 |
| Judge/matcher disagreements | 1/41 | 0/28 |
| Judge unclear, matcher confident | 0 | 2 |
| Errors | 0 | 0 |

## Answer × evidence

| Cell | Meaning | Curated | Holdout |
|---|---|---|---|
| grounded | right, and the evidence was there | 38 | 27 |
| from memory | **right without the evidence — not grounded** | 0 | 0 |
| evidence unused | **had the evidence, still wrong** | 0 | 3 |
| neither | never had the evidence | 4 | 0 |

## Funnel

Computed from `answer_match`, `evidence_match` and `searched` — the same attribution the read pass needed a human to make.

| Stage | Curated | Holdout |
|---|---|---|
| 1 query: did not search at all | 0 | 0 |
| 2 retrieval: the answer-bearing article never surfaced | 0 | 0 |
| 3 evidence: right article, fact not in the retrieved text | 4 | 0 |
| 4 synthesis: had the evidence, answered wrong | 1 | 2 |
| 5 grounding: answered from memory | 0 | 0 |
| correct, grounded | 37 | 26 |
| correct, evidence not checkable | 12 | 0 |
| not scorable (abstention cases) | 0 | 2 |

## Curated, by case

| case | correct | bucket |
|---|---|---|
| lets-make-a-deal-location | 0/3 | systematic |
| arpanet-first-message | 2/3 | flaky |
| beat-bobby-flay-wins | 2/3 | flaky |
| am-i-all-alone-writer | 3/3 | solid |
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

## Judge/matcher disagreements (curated)

Where the accepted phrasings may be overfitted, or the judge wrong. Adjudicated by hand; the deterministic score stays the headline.

- `beat-bobby-flay-wins#1` — matcher `True`, judge `incorrect`: The answer reverses the figures, claiming Bobby Flay has won 330 times, whereas the reference states Flay's wins are 330 (contestants' losses), meaning the answer misattributes the 330 wins correctly to Flay but mislabels contestants' wins as 198 - actually checking: reference says 330 wins (Flay's) which matches, but answer states contestants won 198 times and Flay won 330, which matches reference; however the question asks how many times Flay has won which is 330 - answer's final figure for Flay is 330, matching reference, but the framing is confusing and contradictory within itself.

## Holdout

**Aggregate values only, deliberately.** No case ids, answers or judge rationales appear here. A named failing holdout case is a lead, and following it turns the holdout into training data with nothing downstream able to detect it. Read the numbers in the table above; open nothing else until the V0 → V1 comparison this arm exists to make has been made.

- 30 runs, 0 errors
- judge/matcher disagreements: 0/28; judge unclear while matcher confident: 2 (counts only — the cases are not listed)
