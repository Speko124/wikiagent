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

### Judged (categorical, no scales)

| Dimension | Values | Catches |
|---|---|---|
| **Correctness** | `correct` · `incorrect` · `reference-disputed` | The third value is load-bearing at a 20% bad-reference rate — without it the judge books wins as losses |
| **Disposition** | `answered` · `abstained-correctly` · `abstained-avoidably` · `answered-without-searching` | Replaces `posture`. The old dimension would have scored all five dominant failures as clean abstentions |
| **Faithfulness** | `supported` · `contains-unsupported-claim` | Flat today. Kept because a full-page fetch multiplies context, which is exactly when misattribution begins |
| **Ambiguity handling** | `flagged` · `silently-resolved` · `n/a` | 6b, currently inconsistent |
| **Completeness** | `complete` · `partial` · `n/a` | List and superlative answers; catches 4a |

Five is near the practical ceiling — every dimension needs its own alignment
check against human labels, and unaligned dimensions produce confident noise.
Corroboration and conciseness stay deterministic for exactly that reason.

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
