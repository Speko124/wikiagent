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

*(Outcome decomposition and the failure-implies cross-tab are defined in
`project.md` §3.7. Denominators follow the metric contract there: outcome metrics
count every attempted run, pass^k keeps unresolved questions in the
denominator, and diagnostic metrics show their eligible subset.)*

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

**2. Correctness.** Started as an audit role and became the primary score, on
evidence: the string matcher produced three silent false passes on 54 curated
runs and the judge caught all three. The matcher is retained as a guardrail and
both are reported. Their failure modes are opposite — the matcher passes things
confidently, the judge abstains — so a disagreement means one of them is wrong
and a human should look. Neither overrides the other.

*(This section records the original reasoning; §3 of `project.md` and
`judge.py` carry the final design.)*

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

---

## 3. Backlog — candidate fixes, not decisions

Ordered by the evidence behind them, not by appeal. Nothing here is scheduled;
each needs a measurement before it earns a version.

### B1. The 8,000-char fetch cap is the binding constraint

Strongest evidence, and it displaced the tool's existence as the limiting
factor. 6 of 9 distinct fetched articles in V1 hit the cap. Both remaining
systematic failures trace to it or to what follows it:
`lets-make-a-deal-location`'s answer sits at offset ~15,650 of a 44,579-char
article — in the prose, past what we read.

Options, cheapest first: raise the cap · fetch by section · **give the model a
way to ask for more** (a `from_offset` argument, so paging is possible rather
than the article being all-or-nothing).

### B2. Absence claimed from truncated text

The failure B1 produces. In V1, 8 runs asserted a fact was missing *from the
article* when they had seen only the first 8,000 characters, never mentioning
the cut. V0 was precise here ("the opening section"); V1 lost that precision
because a truncated 8K article reads as complete.

Two candidate fixes, and they are not exclusive: an answering rule that a fact
cannot be called absent from text ending in `[...]`, and making the marker
harder to miss than a four-character token the model has never once
acknowledged — 0 of 54 runs in V0, and the same in V1.

### B3. A summarizing sub-agent over the full article

*Raised as a possibility, not yet evidenced.* Instead of returning raw article
text to the agent, a second model call could read the whole article — no cap —
and return the facts relevant to the question, or answer a targeted follow-up
query against it.

Why it is attractive: it removes the cap problem entirely rather than moving
it, and it would fix `beat-bobby-flay-wins`, where the figure was on screen,
untruncated, and the agent still declined — an extraction failure that a bigger
cap does nothing for.

Why it is not first: it adds a model call per fetch (cost and latency), it puts
a second model between the agent and the evidence — which weakens grounding,
the one dimension currently at zero fabrications across 138 runs — and the
summarizer becomes a new component needing its own evaluation. B1 is a
parameter change with direct evidence; this is an architecture change with an
argument. **Measure B1 first, and if the remaining failures are extraction
rather than reach, this becomes the leading candidate.**

### B4. `top_k` as a lever

Measured but small: 3 tool calls across V0 where the gold article was fetched
and clipped by `top_k`, one of which decided an answer
(`home-alone-toy-store--r2` adopted the rank-3 distractor while the right
article sat at rank 4). Cheap to test since the over-fetch margin is already
cached — no new retrieval needed.

### B5. Prompt wording — generalise the fetch description

The v1 description names "cast members, specific figures and dates", which may
over-anchor. A generalised phrasing exists but was written after the V1 sweep,
so it is unscored and belongs to a v2. Minimal on its own; bundle it with B1
or B2 rather than spending a sweep on it alone.
