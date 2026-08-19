# Sweep report — prompt `v0`

`claude-haiku-4-5` · prompt `v0` · top_k 3 · 3x per case

**Runs** 54 curated, 30 holdout

## Headline

Correctness counts confirmed successes over **every attempted run**: unclear verdicts, errors, wrong answers and declines on answerable questions are all non-successes. pass^k keeps unresolved questions in the denominator. Evidence shows its eligible denominator, since it is only checkable where a case declares what the evidence should contain.

| Metric | Curated | Holdout |
|---|---|---|
| **Correct** (all attempted runs) | 37/54 (69%) | 21/30 (70%) |
| **pass^k** (correct on every repeat) | 12/18 (67%) | 7/10 (70%) |
|   of which | 12 solid (k/k) · 0 flaky · 5 systematic (0/k) · 1 incomplete · 0 unresolved | 7 solid (k/k) · 0 flaky · 1 systematic (0/k) · 1 incomplete · 1 unresolved |
| **Evidence available** (eligible runs) | 27/42 (64%) | 24/30 (80%) |

## Outcome decomposition

Mutually exclusive and exhaustive: these sum to every attempted run. `evaluator unresolved` is deliberately kept apart from `answerable non-answer` - the judge failing to decide is an instrument problem, the agent declining is a behaviour, and merging them would hide which one moved.

| Outcome | Curated | Holdout |
|---|---|---|
| **confirmed success** | 37 | 21 |
| wrong answer | 2 | 2 |
| answerable non-answer | 13 | 3 |
| evaluator unresolved | 2 | 4 |
| execution failure | 0 | 0 |
| *total* | *54* | *30* |

## What each failure implies

Every non-success crossed with whether the answer-bearing evidence reached the model. Not a score: these are five different kinds of work and they do not trade off against each other.

| Failure implies | Curated | Holdout |
|---|---|---|
| Retrieval / Evidence — no answer-bearing text reached the model | 15 | 5 |
| Synthesis — evidence present, answer wrong | 0 | 0 |
| Answer — evidence present, declined anyway | 0 | 0 |
| Evaluator — judge rubric, reference answer, or ambiguity | 2 | 4 |
| Execution — agent loop or infrastructure | 0 | 0 |
| *total failures* | *17* | *9* |

## Supporting (cost and behaviour)

Used to explain tradeoffs between versions, not to claim one.

| Metric | Curated | Holdout |
|---|---|---|
| Turns (mean / max) | 2.4 / 5 | 2.2 / 4 |
| Input tokens / run | 3,902 | 3,227 |
| Searched at all | 51/54 (94%) | 30/30 (100%) |
| Searches / run | 1.5 | 1.2 |
| Runs that opened an article | 0/54 (0%) | 0/30 (0%) |
| Fetches / run (spread) | 0x54 | 0x30 |
| Turns by fetch count | 0 fetch: 2.4t | 0 fetch: 2.2t |
| Failed fetches | 0 | 0 |
| Fetches with no prior search | 0 | 0 |
| Latency median (s) | 3.4 | 3.1 |
| Answer length (chars) | 496 | 399 |
| Output tokens | 223 | 194 |

## Appendix (instrument health)

How much the measurement itself can be trusted.

| Metric | Curated | Holdout |
|---|---|---|
| Judge coverage (resolved / attempted) | 52/54 (96%) | 26/30 (87%) |
| Unresolved runs | 2 | 4 |
| Judge/matcher disagreements | 0/31 | 0/23 |
| Judge unclear, matcher confident | 2 | 4 |
| Correct (contains matcher, guardrail) | 28/45 (62%) | 23/30 (77%) |
| Articles named per answer | 1.5 | 1.2 |
| Questions judged ambiguous | 7/17 (41%) | 5/10 (50%) |
|   correct on those | 13/19 (68%) | 9/12 (75%) |
|   flagged as suspect rubric calls | 3 | 0 |
| Multi-fact coverage | 89% (2 multi-fact cases, 6 runs) | 100% (1 multi-fact cases, 3 runs) |
| Errors | 0 | 0 |

## Answer × evidence

| Cell | Meaning | Curated | Holdout |
|---|---|---|---|
| grounded | right, and the evidence was there | 25 | 23 |
| from memory | **right without the evidence — not grounded** | 0 | 0 |
| evidence unused | **had the evidence, still wrong** | 2 | 1 |
| neither | never had the evidence | 15 | 6 |

## Funnel

Computed from `answer_match`, `evidence_match` and `searched` — the same attribution the read pass needed a human to make.

| Stage | Curated | Holdout |
|---|---|---|
| 1 query: did not search at all | 0 | 0 |
| 2 retrieval: the answer-bearing article never surfaced | 0 | 2 |
| 3 evidence: right article, fact not in the retrieved text | 15 | 3 |
| 4 synthesis: had the evidence, answered wrong | 0 | 0 |
| 5 grounding: answered from memory | 0 | 0 |
| 6 answer: declined with the evidence in hand | 0 | 0 |
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
