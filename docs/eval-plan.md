# Eval plan — final set and rubric

Follows `error-analysis.md`. Two things drive it: the set needs **headroom**
(10 of 11 curated cases passed, so it cannot show improvement), and the metrics
need to measure **answer quality**, not only failure modes.

---

## 1. Final eval set

### Principle

Keep what earns its slot. A case earns its slot by doing one of three jobs:

* **Regression anchor** — currently passes, and would break if we broke
  something. Cheap to keep, and the only thing that catches a fix making
  something else worse.
* **Headroom** — currently fails for a reason we intend to address. This is
  what makes a delta measurable.
* **Coverage** — a mode with no case at all.

Cases that measure nothing get cut or redesigned, not kept out of politeness.

### Composition (18)

**Regression anchors — keep unchanged (7)**

| id | Mode | Why it stays |
|---|---|---|
| `rosetta-year` | single-hop floor | If this breaks, every other number is noise |
| `tosca-nationality` | multi-hop bridge | The one clean synthesis success |
| `eiffel-height` | must-search | Guards the "answers from memory" regression |
| `tesla-origin` | term ambiguity | The one case that *did* flag ambiguity — anchors 6b |
| `straw-doll-village` | query from description | Anchors healthy stage-1 behaviour |
| `paris-weather` | no-search-needed | The other pole of the tool-use pair |
| `einstein-nobel-premise` | false premise | Gold list widened; behaviour unchanged |

**Redesigned (3)**

| id | Problem | Fix |
|---|---|---|
| `opera-house-seats` | Invalid — fact was reachable via another article's intro | Rebuild against a fact verified absent from **all top-5 intros**, not one |
| `lovelace-breakfast` | Question is *so* obviously unrecorded that declining to search is defensible reasoning | Replace with something that **sounds** answerable and isn't, so not-searching is unambiguously wrong |
| `switzerland-borders` | Gold list too narrow; also tests completeness | Keep the question, fix the reference articles |

**Headroom — promoted from explore (5)**

Copied into core with new ids; `explore.jsonl` stays frozen and untouched.

| Source | Mode it buys |
|---|---|
| nq-001 | 3a body-fact **+ 1a memory-seeded query** — two modes in one case |
| nq-004 | 3b infobox-only data (a full-page fetch will *not* fix this) |
| nq-010 | 3c aggregation over tables (a full-page fetch only partly fixes this) |
| nq-017 | 3a body-fact, with a second route (FAO Schwarz) available |
| nq-011 | 2a/2c no article exists + gave up after one search |

Deliberately **not** promoting nq-007: it's a fourth instance of plain 3a and
would over-weight a mode that already has three cases. One case per mode.

**New coverage (3)**

| Mode | Shape |
|---|---|
| Comparison multi-hop | Two entities, cross-document compare — HotpotQA's second-largest type, currently absent |
| Obvious query fails | The straightforward phrasing returns a weak set and a re-query is required — generalises 2b |
| False-premise control | Near-identical answerable twin of `einstein-nobel-premise`, per FalseQA. Without it, "rejects any odd-sounding premise" scores as success |

### Held-out set

The 15 un-promoted explore cases stay frozen and become the **held-out** set.
This matters: once we promote failures into the scored set and fix against
them, core is training data. Re-running the untouched 15 after the fix is the
only check that we generalised rather than fitted.

### Resampling

A fresh random draw is the highest-value addition once time allows — the first
one produced every instance of the dominant failure mode. Trigger: after the
retrieval fix lands, draw 20 with a new seed as held-out validation. Cost is
20 runs.

---

## 2. Rubric and metrics

Two categories, because they answer different questions: **did it fail, and
how** versus **how good was the answer when it didn't fail**.

### Deterministic (no judge)

Exact, free, and computed for every run. Preferred wherever a signal can be
computed rather than judged.

| Signal | Definition |
|---|---|
| `searched` / `n_searches` | Tool-use discipline; catches 6a and thrash |
| `n_distinct_articles_cited` | **Corroboration proxy** — an answer resting on three agreeing articles is stronger than one resting on one |
| `answer_length` | Proxy for 6d off-mission padding |
| `n_turns`, tokens, latency | Cost and distress signals |
| `cited ⊆ retrieved` | Citation integrity |
| **per-query results** | Which query produced which titles — replaces the flattened `shown_titles` |

**`gold_shown` is retired.** It asked "did the predicted article come back",
which is the wrong question: facts are carried by many articles, and both of
its MISSes were correct grounded answers. `gold_articles` demotes to
*reference articles*, a non-exclusive hint, and retrieval success is judged as
"did the retrieved text support the answer".

### Judged — reassessed after the determinism work

The plan originally had five judged dimensions. Three were absorbed by exact
computation and one was deferred, leaving one:

| Originally judged | Now | Why |
|---|---|---|
| Correctness | **deterministic** | Hand-authored accepted phrasings: 8/8 against hand labels. Holdout specs authored too, so every set we run is scorable without a judge |
| Disposition (abstained-correctly vs avoidably) | **deterministic** | Falls out of the `answer_match` × `evidence_match` cross-tab. "Had the evidence and didn't use it" versus "never had it" is two booleans, not a judgement |
| Completeness | **deterministic** | The satisfied-fraction of an AND-of-ORs spec |
| Faithfulness | **deferred** | 0 unsupported claims in 31 runs. Revisit when a full-page fetch multiplies context, which is when misattribution starts |
| **Ambiguity** | **judged** | The only one where determinism was measured and failed |

So the judge earns exactly one dimension plus one audit role:

**1. Ambiguity detection.** Disambiguation-page retrieval — the obvious exact
proxy — fires on `rosetta-year` and `eiffel-height` (neither ambiguous), misses
`tesla-origin`, `nq-003` and `nq-015` (all ambiguous), and returns nothing at
all across 20 explore cases. Wrong in both directions, so this genuinely needs
judgement.

**2. Correctness auditing.** Not scoring — a second opinion whose disagreements
with the string matcher flag candidates for human review. As an auditor it
needs far less alignment than a scorer: it doesn't have to be right, only
*differently wrong*. The deterministic score stays the headline number.

### Judge configuration

**Model: Claude Sonnet 5** — deliberately not Haiku 4.5, which is the agent.
Same-model judging carries a documented self-preference bias, and the agent is
the weaker model in exactly the judgement being asked for.

**Cost is smaller than it looks.** Ambiguity is a property of the *question*,
not of a run, so it is judged once per question rather than once per repeat:
28 calls, not 84. Only "did this answer address the ambiguity" is per-run, and
only for questions labelled ambiguous.

**It can be validated before the baseline runs**, because it judges questions
that already exist. No sweep required.

### Alignment: recall, not agreement

Base rate is 34% (curated 22%, explore 45%), so **a judge that always says
"unambiguous" scores 66% agreement** — a false negative wearing a good score.

The metric is therefore **recall on the ambiguous class**, which is exactly one
minus the false-negative rate. Precision matters much less: a false positive
costs a glance at a small flagged set, a false negative is invisible. The
rubric is biased toward sensitivity accordingly — flag anything with more than
one reasonable reading, then hand-filter.

**Input separation removes the mechanism that produces false negatives.** If
the judge sees the agent's answer while deciding whether the question was
ambiguous, a cleanly-handled answer makes the question look unambiguous. So:
"is this question ambiguous?" sees question + retrieved titles and never the
answer; "did the answer address it?" is a separate call.

**Limit worth stating:** 13 labelled positives gives a coarse recall estimate —
enough to catch a badly broken judge (recall under ~50%), not enough to
distinguish 85% from 95%.

### Measured: where deterministic matching works, and where it doesn't

Run over the 31 already-labelled runs, comparing the matcher's verdict to the
hand labels. No extra labelling, no alignment run.

| Spec source | Set | Agreement |
|---|---|---|
| Hand-authored variants | curated (8 scorable) | **8/8** |
| Auto-derived from NQ reference | explore (20) | **11/20** |

The 55% is diagnostic, not noise. Of the nine disagreements: one was a real
matcher bug (Natural Questions stores dates with non-breaking spaces, so
`June\xa09,\xa02017` never matched a plainly typed date — now fixed and
tested); four were paraphrase or variant gaps (`Tughlaq`/`Tughluq`,
`Sandra Miju Oh`/`Sandra Oh`, `2 Titles`/`two times`, `Dominion of Canada`/
`Canadian North-West Territories`); and four were **references that are simply
wrong**, where the agent was right and the dataset was not.

**Conclusion, measured rather than argued:** deterministic correctness is
trustworthy exactly where a human authored the accepted phrasings, and unusable
where specs are derived automatically. So the curated set is scored
deterministically, and the random sets are where a judge earns its keep.

**Caveat on the 8/8.** Those specs were written *after* reading the baseline
answers, so they are contaminated — I knew the phrasing I had to accept. The
honest number will come from the ten new or rewritten cases at baseline, whose
specs were authored before any run existed.

### Judge design

* **Different model from the agent** (Sonnet 5 judging Haiku) — self-preference
  bias is documented.
* **Correctness and faithfulness get different evidence.** Show the judge the
  retrieved text and it grades consistency-with-retrieval, not truth. So
  correctness sees question + reference + answer; faithfulness sees answer +
  retrieved text. Same call, separated inputs.
* **Validated against the 31 existing hand labels** before any number is
  trusted. Those labels already exist, so alignment costs nothing extra.
  Agreement gets reported; poor agreement means fixing the rubric, not the
  agent.
* Judge model and rubric version recorded in every row; changing either forces
  re-validation.
