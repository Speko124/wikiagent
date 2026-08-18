# Design rationale

A Claude agent that answers questions using Wikipedia, and an eval suite that
measures it. Everything claimed here is backed by committed artifacts —
traces, per-run verdicts, hand labels and four sweeps live in `results/`.
This document is the reasoning that the artifacts don't contain.

---

## 1. Guiding principles

Four, chosen up front and visible in every decision that follows.

**Simple surfaces.** One prompt, one tool to start. Every capability added
later had to be argued for by an eval result, not by anticipation. The system
ended with two tools and a ~150-word prompt.

**Deterministic wherever possible.** An LLM judge is a last resort, used only
where a deterministic signal was *built, measured, and observed to fail*. This
is a safeguards instinct: exact signals can be wrong, but they are wrong the
same way every time, and you can test them.

**Let the results lead.** No taxonomy, no metric set and no failure funnel was
finalised before running the system and reading what it did. This is also why
the eval set includes questions nobody on the project chose.

**Guard against silent corruption, not just crashes.** A run that fails costs
an hour; a run that is quietly wrong costs a phase of false conclusions. This
principle earned its place repeatedly — see §7.

---

## 2. Approach: sweep first, taxonomy second

The first real activity was not designing metrics. It was running 31 questions
once each and **reading every trace by hand**.

Defining the taxonomy first would have produced an eval that could only confirm
what we already believed. Two concrete things say it mattered:

- **The funnel weights inverted.** We expected grounding (fabrication) to
  dominate — it is the famous failure of retrieval-augmented systems. It came
  in at **zero across 138 runs**. The real bottleneck was retrieval *depth*,
  which we had barely scoped.
- **Two of the six failure sub-modes were not on anyone's list**, including the
  one that mattered most.

Repeats came *after* reading. Running a question three times before reading it
once buys nothing and costs 3×.

---

## 3. Prompt engineering

**Three surfaces, not one.** The system prompt, the tool descriptions, *and*
the rendered tool output are all prompt engineering — the last one is what the
model actually reads most of. All three are versioned **together**, because a
tool-description edit otherwise silently invalidates a previous sweep while the
trace still claims the runs are comparable.

**Frozen by digest.** Each version's text is hashed and asserted in a test. This
is not ceremony: mid-project it caught a live edit to a prompt that had already
been scored against, and every trace now records the digest of what actually
ran, so "which wording produced these numbers?" is answerable from the results
rather than from file timestamps.

**Short on purpose.** ~150 words. A long prompt makes a delta unattributable
and leaves no room to hill-climb where evals point.

**Every line traceable to an observed failure.** Examples: *"Name the articles
you used, by their exact titles"* exists because the model paraphrased titles
and made citation-matching unreadable. *"Search for one subject at a time"*
exists because of an observed multi-hop failure.

---

## 4. Eval design

### Three question sets, three jobs

| Set | Size | Job |
|---|---|---|
| **Curated** | 18 | Test what we decided matters; regression anchors |
| **Explore** (random) | 20 | Find what we *didn't think of* |
| **Holdout** (random, disjoint) | 10 | Ground the result |

The random sets are drawn from Natural Questions — real Google queries, frozen
by seed, **nothing filtered**. Dropping the awkward ones would put our own
taxonomy straight back in.

**The random draw earned its keep decisively.** Five of six failures in the
random set shared one cause — the right article retrieved, the answer in the
article body the tool never read. **The curated set surfaced zero instances.**
Real users ask about cast members, filming locations and counts; that material
lives below the intro, and we would not have written those questions.

**The holdout exists because the curated set becomes training data.** Once
failures are promoted into it and fixed against, it can no longer tell you
whether you generalised. Discipline is enforced by the harness, not by
intent: `--holdout` suppresses the review worksheet and label file entirely,
and the cross-arm report emits holdout aggregates only — no case ids, no
answers. A test asserts the report never names a holdout case.

### What is measured, and by what

**Deterministic (preferred).** Correctness against hand-authored accepted
phrasings; retrieval quality against whether the retrieved text carried the
evidence, matched per tool call and accumulated across calls so a multi-hop
question isn't blamed on retrieval. Crossing the two gives the funnel stage
exactly:

| | evidence found | not found |
|---|---|---|
| **answer right** | grounded | answered from memory |
| **answer wrong** | had it, didn't use it | never had it |

Plus corroboration (distinct articles cited), completeness (fraction of
required facts), tool discipline, turns, tokens, latency — and **pass^k**,
cases correct on *every* repeat, bucketed solid / flaky / systematic. A per-run
rate hides the shape: 50% could be one case that always works beside one that
never does.

**Judged, where determinism was measured to fail.** Two dimensions survived
from five. *Ambiguity* is judged because the obvious deterministic proxy —
disambiguation-page retrieval — was built and misfired in **both** directions.
*Correctness* is judge-primary with the string matcher retained as a guardrail.
The judge is Sonnet 5 judging Haiku 4.5 (self-preference bias is documented),
rubric frozen and digest-tested, calibrated at **51/54** against hand labels
with **zero cases where it said `correct` and a human said `incorrect`**.

**Why both correctness signals are kept** — they fail in opposite directions,
and we have one instance of each:

- The matcher certified two failing runs as passes; an accepted phrasing
  (`login`) matched unrelated text. The judge flagged both.
- On another case the judge returned `incorrect` for an answer that was right,
  with a rationale that contradicted itself. The matcher had it right, three
  sweeps running.

Neither dominates. Disagreements are surfaced and adjudicated by hand.

### The variance floor is measured

Two identical sweeps agree on **54/54** deterministic verdicts and differ on
2 judged runs. Variance is *concentrated*: zero flips across 39 runs on cases
with a reachable answer, 4 of 12 on cases where the answer doesn't exist. So a
change targeting retrieval can be measured at 3 repeats; a change targeting
abstention cannot. **An improvement below ~3 runs is not distinguishable from
noise on this set** — stated so results can be called unresolved rather than
overclaimed.

---

## 5. Versions and results

| Version | What changed | Curated | Holdout | pass^3 |
|---|---|---|---|---|
| *pre-baseline* | first draft; never scored | — | — | — |
| **v0** | search only, intros, top-3 | 71% | 81% | 13/18 |
| **v1** | **+ `fetch_article`** + 1 prompt line | **89%** | **93%** | 15/18 |
| v1 repeat | identical, to measure variance | 89% | 92% | 16/18 |
| **v2** | generalised escalation rule | **91%** | 93% | 15/18 |

**Pre-baseline → v0** was defect repair, not tuning. The first draft hardcoded
"three articles" while `top_k` is a knob, asked for citations without saying
how, and never explained the truncation marker. It was never scored, so it was
never a baseline — it's archived rather than kept as a version.

**v0 → v1: the one intervention that mattered.** Adding `fetch_article` and a
single prompt line moved correctness **+18 points curated and +12 held out**,
with zero regressions among the 13 cases that already passed and stage-3
body-fact failures down 12 → 5. The tool is used selectively — a third of runs,
only where the intro genuinely lacked the answer, zero failed fetches, zero
fetches without a preceding search — and costs exactly one extra turn when
used. Cost: +63% input tokens, latency unchanged (the fetch *replaces* search
rounds).

**v1 → v2: a proven mechanism of unsized magnitude.** v1's rule said open *the*
article when its opening section lacked the answer, and the traces showed the
agent obeying it narrowly — it fetched the article whose title matched the
topic and never the article about the person who did the thing. `Leonard
Kleinrock` was a top-3 result in all six v1 runs of one case and fetched
**zero** times. v2 hands the choice back to the model, and it fetched Kleinrock
in 2 of 3 runs; both flipped to correct, and that article is the *only*
reachable path to the answer.

But **+2 runs against a 3-run noise bar is not a result**, and it is recorded
as unresolved rather than claimed. The real v2 win is efficiency: the worst case
went 9/9/10 turns → 7/6/8, **40% cheaper and 28% faster**, and v1's single
runaway error disappeared.

**That is the expected shape at ~90%.** With most headroom gone, further prompt
changes mostly buy efficiency, and pushing correctness higher on *these*
questions risks fitting the prompt to them. The right next move is harder
questions, not more prompt.

**The holdout tracked the curated set throughout** — within 3 points at v0
(71/81), v1 (89/93) and v2 (91/93), *including through a +18-point
intervention*. Overfitting would show as that gap widening exactly when
something was fixed. It didn't.

---

## 6. Where it fails

- **The 8,000-char fetch cap is now the binding constraint.** 19 of 22 fetches
  came back truncated. One case's answer sits at offset ~15,650 of a
  44,579-char article — in the prose, past what we read.
- **Absence claimed from truncated text.** The agent asserts a fact is missing
  *from the article* having read part of it. Three attempts to fix this by
  prompt have produced **zero** acknowledgements of truncation across 162 runs.
  It needs a mechanism, not more words.
- **Infobox and table data is unreachable** — plaintext extracts omit both.
- **Ambiguity handling is inconsistent**, and often decided upstream by the
  agent's own query wording before it notices an ambiguity exists.

**What does *not* fail: grounding.** Zero fabricated claims and zero fabricated
citations across 138 runs. Every figure spot-checked against the rendered tool
output was present in it. The system's honest failure mode is declining to
answer, not inventing one.

---

## 7. When the instrument was wrong

Worth its own section, because it happened more often than agent failures did.

- **Three false passes** from hand-authored accepted phrasings matching
  unrelated text.
- **A circular test.** It "verified" a fact was infobox-only by asserting it was
  absent from text the fetcher had already truncated — it would have passed
  wherever the fact lived.
- **Two wrong case notes**, each a plausible cause written down and never
  checked against what the tool returned.
- **A stale-reference bug that fabricated a +3 improvement** between two
  identical sweeps: a case's expected answer was rewritten mid-project and old
  judge verdicts were carried over, so the judge saw a different reference while
  the agent's answers were byte-identical.
- **Three `None`-read-as-`False` bugs**, each turning an unmeasured signal into
  a failed one.

**None were found by the test suite.** All were found by reading traces or
generated reports. The suite's real job turned out to be *preventing regression
of things already understood* — it discovered nothing.

Every one is now covered by a test, and `evals/regrade.py` re-scores a finished
sweep from saved traces with no API calls, so fixing a grader costs a re-grade
rather than a re-run.

---

## 8. Lessons

**There is no replacement for reading traces.** Every real finding in this
project came from reading them. Aggregate metrics told us *that* something was
wrong; only traces told us *what*, and several times told us the metric itself
was broken.

**The best review is hybrid — a strong model and a human, disagreeing.** Both
were used here and they failed differently. The model found things I missed: a
query seeded from a hallucinated character name, the circular test, the stale
reference. I found things it got wrong: an over-claimed conclusion about one
case, and three ambiguity labels *it* was right about and I wasn't. The
disagreements were where the value was — which is the same argument as keeping
both correctness signals, one level up.

---

## 9. With more time

Ordered by evidence behind them, not appeal.

1. **Fix the cap, not the prompt.** Paging (`from_offset`), section-level fetch,
   or a larger cap. Direct evidence: 19 of 22 fetches truncated.
2. **Token efficiency.** 13% of evidence characters are *re-delivered* snippets
   — one article's intro was re-shown up to six times in a single run.
3. **A summarising pass over long articles.** The only candidate that addresses
   extraction failures where the fact was already on screen — but it puts a
   second model between the agent and the evidence, which risks the one
   dimension currently at zero fabrications. Measure the cap fix first.
4. **More questions from the wild, and harder ones.** At ~90% the current set is
   near its ceiling. New random draws cost 20 runs and have already proven the
   highest-yield source of unknown failure modes.
5. **Deliberate adversarial evals** — instructions embedded in retrieved text,
   over-refusal on encyclopedic-but-sensitive topics. Scoped out here to keep
   the pass on core functionality.
6. **A structured trace-analysis agent, itself evaluated.** The analysis loop is
   now the bottleneck, not the agent: it is the only fully manual step, and it
   is where every finding came from. Making it repeatable — and measuring *it*
   against human labels, exactly as the judge was — is the highest-leverage
   remaining piece of infrastructure.

---

## 10. Time spent

Roughly four sessions across four days: design and prototype, eval harness,
three measured iterations with error analysis between each, plus documentation.
