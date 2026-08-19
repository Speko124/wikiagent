# Sweep report — prompt `v1`

`claude-haiku-4-5` · prompt `v1` · top_k 3 · 3x per case

**Runs** 54 curated, 30 holdout

## Headline

Correctness counts confirmed successes over **every attempted run**: unclear verdicts, errors, wrong answers and declines on answerable questions are all non-successes. pass^k keeps unresolved questions in the denominator. Evidence shows its eligible denominator, since it is only checkable where a case declares what the evidence should contain.

| Metric | Curated | Holdout |
|---|---|---|
| **Correct** (all attempted runs) | 47/54 (87%) | 24/30 (80%) |
| **pass^k** (correct on every repeat) | 15/18 (83%) | 8/10 (80%) |
|   of which | 15 solid (k/k) · 0 flaky · 2 systematic (0/k) · 1 incomplete · 0 unresolved | 8 solid (k/k) · 0 flaky · 0 systematic (0/k) · 1 incomplete · 1 unresolved |
| **Evidence available** (eligible runs) | 36/42 (86%) | 30/30 (100%) |

## Outcome decomposition

Mutually exclusive and exhaustive: these sum to every attempted run. `evaluator unresolved` is deliberately kept apart from `answerable non-answer` - the judge failing to decide is an instrument problem, the agent declining is a behaviour, and merging them would hide which one moved.

| Outcome | Curated | Holdout |
|---|---|---|
| **confirmed success** | 47 | 24 |
| wrong answer | 1 | 1 |
| answerable non-answer | 5 | 1 |
| evaluator unresolved | 1 | 4 |
| execution failure | 0 | 0 |
| *total* | *54* | *30* |

## What each failure implies

Every non-success crossed with whether the answer-bearing evidence reached the model. Not a score: these are five different kinds of work and they do not trade off against each other.

| Failure implies | Curated | Holdout |
|---|---|---|
| Retrieval / Evidence — no answer-bearing text reached the model | 6 | 0 |
| Synthesis — evidence present, answer wrong | 0 | 1 |
| Answer — evidence present, declined anyway | 0 | 1 |
| Evaluator — judge rubric, reference answer, or ambiguity | 1 | 4 |
| Execution — agent loop or infrastructure | 0 | 0 |
| *total failures* | *7* | *6* |

## Supporting (cost and behaviour)

Used to explain tradeoffs between versions, not to claim one.

| Metric | Curated | Holdout |
|---|---|---|
| Turns (mean / max) | 2.8 / 10 | 2.7 / 9 |
| Input tokens / run | 7,389 | 7,078 |
| Searched at all | 51/54 (94%) | 30/30 (100%) |
| Searches / run | 1.5 | 1.4 |
| Runs that opened an article | 19/54 (35%) | 8/30 (27%) |
| Fetches / run (spread) | 0x35 · 1x16 · 2x3 | 0x22 · 1x7 · 2x1 |
| Turns by fetch count | 0 fetch: 2.1t · 1 fetch: 3.1t · 2 fetch: 9.3t | 0 fetch: 2.1t · 1 fetch: 3.7t · 2 fetch: 9.0t |
| Failed fetches | 0 | 0 |
| Fetches with no prior search | 0 | 0 |
| Latency median (s) | 3.2 | 3.2 |
| Answer length (chars) | 460 | 418 |
| Output tokens | 247 | 250 |

## Appendix (instrument health)

How much the measurement itself can be trusted.

| Metric | Curated | Holdout |
|---|---|---|
| Judge coverage (resolved / attempted) | 53/54 (98%) | 26/30 (87%) |
| Unresolved runs | 1 | 4 |
| Judge/matcher disagreements | 0/40 | 0/25 |
| Judge unclear, matcher confident | 0 | 4 |
| Correct (contains matcher, guardrail) | 39/45 (87%) | 26/30 (87%) |
| Articles named per answer | 1.4 | 1.2 |
| Questions judged ambiguous | 8/18 (44%) | 7/10 (70%) |
|   correct on those | 20/23 (87%) | 15/17 (88%) |
|   flagged as suspect rubric calls | 3 | 0 |
| Multi-fact coverage | 100% (2 multi-fact cases, 6 runs) | 100% (1 multi-fact cases, 3 runs) |
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
| 4 synthesis: had the evidence, answered wrong | 0 | 1 |
| 5 grounding: answered from memory | 0 | 0 |
| 6 answer: declined with the evidence in hand | 0 | 1 |
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
