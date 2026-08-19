# Error analysis — read pass

31 runs · `claude-haiku-4-5` · prompt `v0` · `top_k` 3 · one run per case.
Sources: `results/read-core/`, `results/read-explore/`, hand labels in each
directory's `labels.jsonl`.

Converged from two independent manual passes over the same traces. Where they
disagreed, the disagreement is recorded rather than resolved away — twice the
second pass was right and the first had labelled too coarsely.

**What n=1 supports.** Every run was read and labelled by hand against the
retrieved text, not against a reference answer. That is enough to *identify*
failure modes and to rule some out. It is not enough to size any of them —
"5 of 20" means "five times in twenty single runs", not a rate. The score pass
(3×) exists to separate systematic from flaky.

---

## 1. Headline

| | Core (11) | Explore (20) |
|---|---|---|
| Correct | 10 | 14 |
| Incorrect | 1 | 6 |
| Harness errors | 0 | 0 |
| **Fabrications** | **0** | **0** |

**Zero fabrications in 31 runs.** Every specific claim spot-checked against the
rendered tool output was present in it — including ones that read as invented
(the Einstein presentation-speech quote, Nagoro's "25 residents as of January
2026"). Grounding and honest abstention are **not** where this system is weak,
which redirects the effort away from the dimension we expected to spend it on.

---

## 2. The dominant finding: intro-only retrieval is the binding constraint

**5 of the 6 explore failures share a cause** — the correct article was
retrieved and shown, and the answer sits in the article *body*, which the tool
never fetches. Verified against the MediaWiki API per case, not inferred:

| Case | Question | In intro? | In body? |
|---|---|---|---|
| nq-001 | who played eric in head of the class | ✗ | ✓ Brian Robbins |
| nq-004 | where is let's make a deal filmed 2018 | ✗ | ✓ Raleigh Studios |
| nq-007 | who plays the witch in pirates of the caribbean 5 | ✗ | ✓ Golshifteh Farahani |
| nq-010 | beat bobby flay how many times has he won | ✗ | ✓ (see 3c) |
| nq-017 | name of toy store in home alone 2 | ✗ | ✓ Duncan's Toy Chest |

In every one the agent behaved **correctly given its tool**: it searched, found
the right article, and reported that the retrieved text doesn't contain the
answer. The failure is in the tool surface, not the prompt or the model.

Note the shape of the questions. Real users ask for cast members, filming
locations and counts — material that lives below the intro. **The curated set
surfaced none of this**; every instance came from the random sample.

**Accidental confirmation from the other side.** The curated deep-fact case
(`opera-house-seats`) was answered correctly because a *different* article's
intro (Sydney Symphony Orchestra) happened to carry the number. Reachability
depends on which article happens to mention a fact in its first paragraph.

---

## 3. Taxonomy

Sub-modes marked ⁺ came from the second manual pass and were missed by the
first, which had collapsed them into the stage above.

### Stage 1 — Query formulation

| | Mode | Evidence |
|---|---|---|
| 1a⁺ | **Memory-seeded query** | nq-001 searched `Eric Foreman Head of the Class actor`. Eric Foreman is a character in *House* and *That '70s Show* — **not** in *Head of the Class*, where the character is Eric Mardian. The model invented a name from parametric memory and searched for it; that search returned the *House* and *That '70s Show* character lists. Searches 3–5 were chasing a hallucination. |
| 1b | Hypothesis-confirming drift | nq-019 drifted from `Fertile Crescent resources` to `oil reserves Middle East Iraq Kuwait` — hypothesis first, then searching to confirm it. The answer was defensible; the process would launder a wrong hypothesis just as smoothly. |
| 1c | Thrashing | nq-001 (5 searches, 6 turns), nq-019 (4). Now understood as *downstream* of 1a and 3a rather than independent. |

Healthy: `straw-doll-village` built a working query from a pure description
with no entity name in it.

### Stage 2 — Retrieval

| | Mode | Evidence |
|---|---|---|
| 2a | No article exists | nq-011 — the song has no Wikipedia article. Agent offered a near-match explicitly labelled as not matching. |
| 2b⁺ | Obvious query returns a weak set | `switzerland-borders` queried `Switzerland borders` and got *France–Switzerland border*, *Germany–Switzerland border*, *Switzerland–EU relations* — the **`Switzerland` article itself never came back**. Ranking order was also odd. |
| 2c⁺ | Insufficient persistence after a miss | nq-011 gave up after one search. Compare nq-001, which ran five. Persistence is inconsistent, not calibrated. |

### Stage 3 — Evidence *(the bottleneck)*

| | Mode | Evidence |
|---|---|---|
| 3a | Fact in article body | nq-001, 004, 007, 010, 017 — five instances |
| 3b⁺ | **Fact in infobox / sidebar, not prose** | nq-004's production location is infobox data. `explaintext` extracts **do not include infoboxes at all**, so a full-text fetch would still miss it. |
| 3c⁺ | **Fact requires aggregation over tables** | nq-010's win count must be computed across per-season tables. Even full-page text wouldn't hand it over. |

3b and 3c matter for scoping the fix: **a full-page read is necessary but not
sufficient.** It resolves 3a cleanly, 3b not at all, 3c only partially.

### Stage 4 — Synthesis

| | Mode | Evidence |
|---|---|---|
| 4a | Superlative from a subset | nq-014 answered "which planet is most similar in temperature to Earth" after checking only Venus and Mars. Also ambiguous (solar system vs exoplanets), and the searches were seeded from memory rather than from a survey — 1a again. |
| 4b⁺ | **Single-source claim where corroboration was available** | `turing-nobel` concluded "no Nobel" from one article's intro not mentioning one. Correct, but a Nobel laureates list would have made it evidence rather than absence-of-evidence. |

Healthy: the multi-hop bridge (`tosca-nationality`) worked in two clean searches.

### Stage 5 — Grounding

Nothing observed. Zero fabricated claims, zero fabricated citations.

### Stage 6 — Answer and posture

| | Mode | Evidence |
|---|---|---|
| 6a | Answered without searching | `lovelace-breakfast`, 0 searches. **The case is weak** — the question is so obviously unrecorded that declining to search is defensible reasoning, not a failure. Needs redesign before it can test anything. |
| 6b | Ambiguity silently resolved | nq-003 (2006 vs 1967 *Casino Royale*), nq-015 (1991 vs 2017 *Beauty and the Beast*). Inconsistent: `tesla-origin` *did* flag its ambiguity. |
| 6c | Attribution imprecision | `switzerland-borders` credited one article for facts drawn from three. `cited ⊆ retrieved` still passes. |
| 6d⁺ | Off-mission verbosity | `paris-weather` correctly declined, then listed weather websites — outside the system's job. |

**Process failures that produce correct answers** (6a, and 1a in nq-014) are a
category the original funnel lacked. Only visible because retrieval is scored
separately from correctness; an answer-only eval marks them all as passes.

---

## 4. Where the instrument was wrong

Principle 2.4 — a bad grader gets fixed before the agent does.

**`gold_shown` measures the wrong thing.** It asks "did the article I predicted
come back", not "did sufficient evidence come back". Both core MISSes
(`einstein-nobel-premise`, `switzerland-borders`) were correct, grounded
answers built from articles that weren't on my list.

**The single-gold-article model is wrong in principle, not just in
calibration.** Facts are usually carried by several articles, and an answer
corroborated by three articles is *stronger*, not merely differently sourced.
A metric keyed to one predicted title can't express that. Replaced — see the
rubric plan.

**One curated case is invalid.** `opera-house-seats` was verified against the
Sydney Opera House intro only; that doesn't establish the fact is unreachable.

**NQ reference answers are wrong or dubious in 4 of 20 (20%)**, and in three of
those **the agent was more correct than the reference**: Lin-Manuel Miranda vs
the alternates (nq-020), "oil" vs "water" (nq-019), Paige O'Hara for a question
that says *voice* (nq-015). Automated scoring against NQ would have booked
three wins as losses.

**Per-query results aren't visible in the row.** `shown_titles` is flattened
and deduplicated across every search in a run, so a multi-search run shows six
titles with no indication of which query produced which. The detail is in the
trace; the summary needs it too.

---

## 5. Revised funnel weights

Stage weights are inverted from the Phase-2 guess.

| # | Stage | Observed | Verdict |
|---|---|---|---|
| 1 | Query formulation | 3 | **Weaker than assumed** — memory-seeded queries are a real mode |
| 2 | Retrieval | 3 | Adequate; persistence uncalibrated |
| 3 | **Evidence** | **7** | **The bottleneck** |
| 4 | Synthesis | 2 | Healthy |
| 5 | Grounding | 0 | Clean |
| 6 | Answer / posture | 4 | Honest but inconsistent |


---

## 7. V0 baseline (54 curated + 30 holdout runs, 3× each)

The read pass above was hand-labelled over a different case set, so it is **not
comparable** with what follows. From V0 onward the funnel is computed from
exact signals and every later iteration is like-for-like.

| Stage | Curated | Holdout |
|---|---|---|
| correct, grounded | 28 | 23 |
| correct, evidence not checkable | 3 | 0 |
| 5 grounding: answered from memory | **0** | **0** |
| 4 synthesis: had the evidence, answered wrong | 2 | 1 |
| **3 evidence: right article, fact not in the retrieved text** | **9** | **3** |
| 2 retrieval: article never surfaced | 0 | 3 |
| 1 query: did not search at all | 0 | 0 |
| not scorable (abstention cases) | 12 | 0 |

Correctness 74% curated / 77% holdout. **Zero ungrounded answers in 84 runs**,
and **zero judge/matcher disagreements** across 62 judged runs.

The holdout tracking the curated set within 3 points is the first evidence the
hand-built set is not badly miscalibrated against real questions.

### 7.1 Confirmed on data that was not used to find it

Stage 3 is the largest failure bucket in **both** arms. The three systematic
`0/3` curated cases are exactly the promoted body-fact ones —
`head-of-class-eric`, `home-alone-toy-store`, `lets-make-a-deal-location`.

### 7.2 New modes

**Memory in the query, refusal in the answer.** `home-alone-toy-store` r0 and
r1 searched `Duncan's Toy Store Home Alone 2` — the agent *recalled the
answer*, searched to confirm it, failed (body-only fact), and then correctly
declined to state it. The must-search discipline working exactly as designed
and costing us a correct answer. It is also the strongest evidence for
`fetch_article`: the agent already knows which article and which entity, and
merely cannot open the page.

**Self-disambiguating query.** `tesla-origin` is 2/3. The two passes searched
`Tesla` and `Tesla inventor`; the failure searched `Tesla company` — the query
resolved the ambiguity before the agent could notice there was one, so it
answered only the corporate reading. Ambiguity handling is downstream of the
agent's own query formulation, which no prompt line about "flagging ambiguity"
would fix.

**Reading drift across repeats.** `arpanet-first-message` is 2/3. The failing
run answered "an email sent by Ray Tomlinson in 1971", citing *History of
email* — a different but defensible reading of "first message sent over the
internet". Flakiness here is ambiguity resolution varying run to run, not
retrieval variance.

**Partial-grounding drift.** `home-alone-toy-store` r2 answered *FAO Schwarz*,
which really was a filming location for the film — true, retrieved, and not
the answer to the question asked. Grounded and wrong at once, which the
grounding signal alone cannot catch.

### 7.3 Instrument defects found in this iteration

Three, all the same class — `bool(None)` is `False`, so a signal that was never
computed read as one that failed:

1. The funnel counted "answer right, no evidence spec" as *answered from
   memory*. `turing-nobel`'s evidence is an absence and has no spec; unknown
   grounding is not ungrounded.
2. The report counted every unscorable abstention run as a judge/matcher
   disagreement. All 8 reported clashes were spurious; the real count is 0.
3. Evidence matching required every requirement inside a **single** tool call,
   while a multi-hop question gathers evidence across several by design. This
   is what misreported `bologna-oxford-older` as answered from memory.

All three would have produced confident wrong conclusions, and all three were
caught by reading generated output rather than by a test. The suite now asserts
the whole metric surface at once in both `report.py` and `run.py`.

The baseline was re-graded from saved traces after the fix — 3 rows changed, no
API calls. Without that, V1 would have shown a phantom grounding improvement at
precisely the stage the fix targets.

### 7.4 Measurement gap, since closed

At the time of this pass, 22% of curated runs (12 of 54) had no correctness
signal at all: the `answer_kind: "none"` abstention cases. That mattered
precisely because `fetch_article` was the change most likely to move them, so
the fix was pointed at the least-instrumented dimension.

**Closed by the judge rubric and metric contract.** `declined` became its own
verdict, scored against the case: declining is a success where the case has no
answer to give and a failure where it does. The correctness denominator is now
every attempted run, and the outcome decomposition names those runs explicitly
as `answerable non-answer` rather than dropping them. That bucket turned out to
be where almost the entire V0 → V2 gain came from (13 → 4 curated), which it
could not have shown while the runs were unscored.
