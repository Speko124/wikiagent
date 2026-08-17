# Error analysis — read pass

31 runs · `claude-haiku-4-5` · prompt `v0` · `top_k` 3 · one run per case.
Sources: `results/read-core/`, `results/read-explore/`. Hand labels in each
directory's `labels.jsonl`.

**What n=1 supports.** Every run was read and labelled by hand against the
retrieved text, not against a reference answer. That is enough to *identify*
failure modes and to rule some out. It is not enough to size any of them —
"6 of 20" here means "six times out of twenty single runs", not a rate. The
score pass (3×) exists to separate systematic from flaky.

---

## 1. Headline

| | Core (11) | Explore (20) |
|---|---|---|
| Correct | 10 | 14 |
| Incorrect | 1 | 6 |
| Harness errors | 0 | 0 |
| **Fabrications** | **0** | **0** |

**Zero fabrications in 31 runs.** Every specific claim spot-checked against the
rendered tool output was present in it — including ones that looked invented,
like the Einstein presentation-speech quote and Nagoro's "25 residents as of
January 2026". When the agent didn't know, it said so and often asked a
clarifying question. Grounding and honest abstention are **not** where this
system is weak, which redirects the effort.

**One failure mode dominates everything else.**

---

## 2. The dominant finding: intro-only retrieval is the binding constraint

**5 of the 6 explore failures have the same cause** — the correct article was
retrieved and shown, and the answer-bearing fact sits in the article *body*,
which our tool never fetches.

Verified directly against the MediaWiki API, not inferred:

| Case | Question | Answer in intro? | In body? |
|---|---|---|---|
| nq-001 | who played eric in head of the class | ✗ | ✓ Brian Robbins |
| nq-004 | where is let's make a deal filmed 2018 | ✗ | ✓ Raleigh Studios |
| nq-007 | who plays the witch in pirates of the caribbean 5 | ✗ | ✓ Golshifteh Farahani |
| nq-010 | beat bobby flay how many times has he won | ✗ | ✓ |
| nq-017 | name of toy store in home alone 2 | ✗ | ✓ Duncan's Toy Chest |

In every one the agent behaved *correctly given its tool*: it searched, found
the right article, and said the retrieved text doesn't contain the answer. The
failure is in the tool surface, not the prompt or the model.

The sixth failure (nq-011, "am i all alone or is it only me") is a genuine
retrieval miss — the song has no Wikipedia article at all. The agent offered a
near-match explicitly labelled as not matching, which is the best available
behaviour.

**This closes the `fetch_article` open question with evidence.** It was raised
in Phase 2 on a single anecdote; it now has five independent instances from
questions nobody wrote for the purpose. Note the shape: real user questions ask
for cast members, filming locations, and specific counts — exactly the material
that lives below the intro. Our curated set never surfaced this at all.

**Accidental confirmation from the other direction.** The one curated
deep-fact case (`opera-house-seats`) was answered correctly — because a
*different* article's intro (Sydney Symphony Orchestra) happened to carry the
number. Same mechanism, opposite outcome: intros are the whole world, and
whether an answer is reachable depends on which article happens to mention it.

---

## 3. Secondary error modes

Each seen once or twice. Recorded, not yet actionable — the score pass decides
which are systematic.

| Mode | Where | What happened |
|---|---|---|
| **Ungrounded abstention** | `lovelace-breakfast` | 0 searches. Right conclusion from priors, and it wrote "While I could search…", so it knew the tool was there. A prompt that abstains from priors will eventually abstain on something Wikipedia covers. Third sighting across three prompt versions. |
| **Ambiguity silently resolved** | nq-003, nq-015 | Picked the 2006 *Casino Royale* and the 1991 *Beauty and the Beast* without flagging the other reading. Notable because the curated `tesla-origin` case *did* flag its ambiguity — so this is inconsistent, i.e. exactly what repeats are for. |
| **Unsupported superlative** | nq-014 | "Which planet is most similar in temperature to Earth" answered "Mars" after checking only Venus and Mars. Grounded and defensible, but a superlative reached from a subset. |
| **Confirmation-driven retrieval** | nq-019 | Queries drifted from `Fertile Crescent resources` to `oil reserves Middle East Iraq Kuwait` — hypothesis first, then searching to confirm it. Answer was defensible; the process would launder a wrong hypothesis just as smoothly. |
| **Attribution imprecision** | `switzerland-borders` | All five countries right and grounded across three articles, but credited to one. `cited_titles ⊆ retrieved` passes; the citation is still misleading. |
| **Thrashing on hard queries** | nq-001 (5 searches, 6 turns), nq-019 (4) | Cost and latency signal. Both hit the intro-only wall — over-searching looks like a distress symptom of the dominant mode, not an independent problem. |

---

## 4. Where the instrument was wrong

Principle 2.4 — a bad grader gets fixed before the agent does. Three defects,
all found by reading:

**`gold_shown` measures the wrong thing.** It asks "did the article I predicted
come back", not "did sufficient evidence come back". Both core MISSes
(`einstein-nobel-premise`, `switzerland-borders`) were fully correct, grounded
answers built from articles I hadn't listed. Retrieval recall as currently
defined understates the system.

**One curated case was invalid.** `opera-house-seats` was verified against the
Sydney Opera House intro only. Verifying that *one* article's intro lacks a
fact does not establish that no retrievable article's intro has it.

**NQ reference answers are wrong or dubious in 4 of 20 (20%).** nq-020's
"original Broadway cast" answer names the alternates rather than Lin-Manuel
Miranda; nq-014 answers an exoplanet; nq-015 names the live-action actress for
a question that says "voice"; nq-019's "water" is weaker than the agent's
"oil". **In three of these the agent was more correct than the reference.** Any
automated scoring against NQ answers would have booked three wins as losses.

---

## 5. Revised funnel

The Phase-2 funnel survives, with the stage weights inverted from what we
guessed. Counts are single-run observations, not rates.

| # | Stage | Observed | Note |
|---|---|---|---|
| 1 | Query formulation | 1 (nq-019 drift) | Healthy. Built a good query from a pure description in `straw-doll-village`. |
| 2 | Retrieval | 1 (nq-011, no article exists) | Healthy. Right article in the top 3 nearly every time. |
| 3 | **Evidence** | **5** | **The bottleneck.** Right article, fact below the intro. |
| 4 | Synthesis | 1 (nq-014 subset superlative) | Healthy; multi-hop bridge worked. |
| 5 | Grounding | **0** | No fabrication observed at all. |
| 6 | Answer / posture | 1 (`lovelace` no-search) + 2 unflagged ambiguity | Abstention honest; ambiguity handling inconsistent. |

One addition the funnel lacked: **process failures that produce correct
answers** (`lovelace-breakfast`). Right output, wrong route. Only visible
because retrieval signals are scored separately from correctness — an
answer-only eval would have marked it a pass.

---

## 6. What to change, in order

1. **Add `fetch_article(title)`** — one tool call returning a named article's
   full text (or a section). Five of six explore failures resolve to this, and
   it's the only change with evidence behind it. Cost is bounded: the agent
   already identifies the right article; it just can't open it.
2. **Fix the instrument before the agent** — widen `gold_articles` to every
   article that could carry the answer, or retire `gold_shown` in favour of
   "did the retrieved text contain the answer", which is what we actually mean.
3. **Prompt lever for the no-search abstention** — one line, cheap to test, and
   the failure has now survived three prompt versions.
4. **Leave the rest.** Ambiguity flagging, superlatives and attribution
   precision are single sightings. Fixing them now would be tuning noise.
