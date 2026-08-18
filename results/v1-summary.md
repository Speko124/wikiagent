# V0 baseline

`claude-haiku-4-5` · prompt `v1` · top_k 3 · 3x per case

| Metric | Curated | Holdout |
|---|---|---|
| Runs | 54 | 30 |
| **Correct** (judge, primary) | 44/50 (88%) | 25/27 (93%) |
| Correct (contains, guardrail) | 36/41 (88%) | 27/30 (90%) |
| Guardrail disagrees with judge | 0 | 2 |
| **pass^k** (correct on every repeat) | 14/17 (82%) | 9/10 (90%) |
|   of which | 14 solid (k/k) · 1 flaky · 2 systematic (0/k) | 9 solid (k/k) · 0 flaky · 1 systematic (0/k) |
| Evidence retrieved | 33/38 (87%) | 29/30 (97%) |
| Answer completeness (mean) | 88% | 90% |
| Searched at all | 50/53 (94%) | 30/30 (100%) |
| Searches per run | 1.4 | 1.4 |
| Articles named per answer | 1.3 | 1.3 |
| Answer length (chars) | 447 | 386 |
| Output tokens | 234 | 240 |
| Latency (median s) | 3.1 | 2.9 |
| Judge/matcher disagreements | 0/37 | 1/25 |
| Judge unclear, matcher confident | 0 | 3 |
| Errors | 1 | 0 |


## V0 → V1

| Metric | V0 curated | V1 curated | V0 holdout | V1 holdout |
|---|---|---|---|---|
| Correct (judge) | 71% | **88%** | 81% | **93%** |
| pass^3 | 13/18 (72%) | **14/17 (82%)** | 7/9 (78%) | **9/10 (90%)** |
| Evidence retrieved | 69% | **87%** | 80% | **97%** |
| Completeness | 70% | **88%** | 77% | **90%** |
| Stage-3 body-fact failures | 12 | **5** | 3 | **0** |
| Systematic (0/3) cases | 5 | **2** | 2 | **1** |
| Input tokens/run | 3,902 | 6,353 | — | — |
| Median latency | 3.4s | 3.1s | — | — |

The holdout moved with the curated set — 81% → 93% — on cases never read
during development. That is the check the holdout exists for, and it passed.

**Per-case, V0 → V1.** Three of the five body-fact cases went 0/3 → 3/3
(`head-of-class-eric`, `home-alone-toy-store`) and `tesla-origin` went 1/3 →
3/3. **Zero of the 13 cases that already passed regressed.**

Two cases still fail by design, and that is the fix's boundary behaving as
predicted rather than a shortfall:

- `lets-make-a-deal-location` — the answer is infobox-only, and plaintext
  extracts omit infoboxes. Asserted by a live test *before* this ran.
- `beat-bobby-flay-wins` — needs aggregation across per-season tables.

**Cost: input tokens up 63%** (3,902 → 6,353 per run) for +17 points of
correctness. Latency did not rise; the fetch replaces search rounds rather than
adding to them.

## Answer × evidence

| Cell | Meaning | Curated | Holdout |
|---|---|---|---|
| grounded | right, and the evidence was there | 33 | 27 |
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

## Holdout

**Aggregate values only, deliberately.** No case ids, answers or judge rationales appear here. A named failing holdout case is a lead, and following it turns the holdout into training data with nothing downstream able to detect it. Read the numbers in the table above; open nothing else until the V0 → V1 comparison this arm exists to make has been made.

- 30 runs, 0 errors
- judge/matcher disagreements: 1/25; judge unclear while matcher confident: 3 (counts only — the cases are not listed)
