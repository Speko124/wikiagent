# Sweep report — prompt `v1`

`claude-haiku-4-5` · prompt `v1` · top_k 3 · 3x per case

**Runs** 54 curated, 30 holdout

## Headline

Correctness counts confirmed successes over **every attempted run**: unclear verdicts, errors, wrong answers and declines on answerable questions are all non-successes. pass^k keeps unresolved questions in the denominator. Evidence shows its eligible denominator, since it is only checkable where a case declares what the evidence should contain.

| Metric | Curated | Holdout |
|---|---|---|
| **Correct** (all attempted runs) | 47/54 (87%) | 25/30 (83%) |
| **pass^k** (correct on every repeat) | 15/18 (83%) | 8/10 (80%) |
|   of which | 15 solid (k/k) · 1 flaky · 1 systematic (0/k) · 1 incomplete · 0 unresolved | 8 solid (k/k) · 0 flaky · 0 systematic (0/k) · 2 incomplete · 0 unresolved |
| **Evidence available** (eligible runs) | 36/41 (88%) | 29/30 (97%) |

## Outcome decomposition

Mutually exclusive and exhaustive: these sum to every attempted run. `evaluator unresolved` is deliberately kept apart from `answerable non-answer` - the judge failing to decide is an instrument problem, the agent declining is a behaviour, and merging them would hide which one moved.

| Outcome | Curated | Holdout |
|---|---|---|
| **confirmed success** | 47 | 25 |
| wrong answer | 1 | 0 |
| answerable non-answer | 5 | 2 |
| evaluator unresolved | 0 | 3 |
| execution failure | 1 | 0 |
| *total* | *54* | *30* |

## What each failure implies

Every non-success crossed with whether the answer-bearing evidence reached the model. Not a score: these are five different kinds of work and they do not trade off against each other.

| Failure implies | Curated | Holdout |
|---|---|---|
| retrieval / selection / truncation / source format | 6 | 0 |
| synthesis or reasoning | 0 | 0 |
| escalation or abstention policy | 0 | 2 |
| judge rubric / reference answer / ambiguity | 0 | 3 |
| agent loop or infrastructure | 1 | 0 |
| *total failures* | *7* | *5* |

## Supporting (cost and behaviour)

Used to explain tradeoffs between versions, not to claim one.

| Metric | Curated | Holdout |
|---|---|---|
| Turns (mean / max) | 2.6 / 9 | 2.7 / 10 |
| Input tokens / run | 6,353 | 7,522 |
| Searched at all | 50/53 (94%) | 30/30 (100%) |
| Searches / run | 1.4 | 1.4 |
| Runs that opened an article | 17/53 (32%) | 7/30 (23%) |
| Fetches / run (spread) | 0x36 · 1x15 · 2x2 | 0x23 · 1x6 · 2x1 |
| Turns by fetch count | 0 fetch: 2.1t · 1 fetch: 3.1t · 2 fetch: 9.0t | 0 fetch: 2.1t · 1 fetch: 3.7t · 2 fetch: 10.0t |
| Failed fetches | 0 | 0 |
| Fetches with no prior search | 0 | 0 |
| Latency median (s) | 3.1 | 2.9 |
| Answer length (chars) | 447 | 386 |
| Output tokens | 234 | 240 |

## Appendix (instrument health)

How much the measurement itself can be trusted.

| Metric | Curated | Holdout |
|---|---|---|
| Judge coverage (resolved / attempted) | 54/54 (100%) | 27/30 (90%) |
| Unresolved runs | 0 | 3 |
| Judge/matcher disagreements | 0/40 | 1/25 |
| Judge unclear, matcher confident | 0 | 3 |
| Correct (contains matcher, guardrail) | 39/44 (89%) | 27/30 (90%) |
| Articles named per answer | 1.3 | 1.3 |
| Questions judged ambiguous | 7/17 (41%) | 7/10 (70%) |
|   correct on those | 17/20 (85%) | 16/18 (89%) |
|   flagged as suspect rubric calls | 3 | 0 |
| Multi-fact coverage | 100% (2 multi-fact cases, 6 runs) | 100% (1 multi-fact cases, 3 runs) |
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
| correct, grounded | 36 | 25 |
| correct, evidence not checkable | 11 | 0 |
| not scorable (abstention cases) | 0 | 3 |

## Curated, by case

| case | correct | bucket |
|---|---|---|
| arpanet-first-message | 0/2 | systematic |
| lets-make-a-deal-location | 0/3 | systematic |
| am-i-all-alone-writer | 2/3 | flaky |
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
- judge/matcher disagreements: 1/25; judge unclear while matcher confident: 3 (counts only — the cases are not listed)
