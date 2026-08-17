# Wikipedia QA agent + eval suite

A system that answers questions using Claude and Wikipedia, and an eval suite
that measures how well it works.

```bash
uv run python -m wikiagent.cli ask "How tall is the Eiffel Tower?" -v
uv run python -m evals.run --cases evals/cases/core.jsonl --repeats 3
uv run python -m evals.report results/v0-curated results/v0-holdout
uv run pytest -q          # 224 offline, 2 opt-in live
```

## Read in this order

| Doc | What it holds |
|---|---|
| `project.md` | The spec. Every decision and why, kept current |
| `error-analysis.md` | What the runs actually showed, iteration by iteration |
| `eval-plan.md` | The case set and the rubric, and what the judge is for |
| `prompt-archive.md` | Replaced prompts and the defects that replaced them |

## How this got built

Roughly in order, because the order is the argument.

**1. Simplest thing end to end.** One tool (`search_wikipedia`, intros only,
top 3), an explicit agent loop, and a `Trace` that records every query, every
raw result, and the exact string the model was shown. Debuggability was a build
requirement, not a later addition — the trace is what everything downstream
reads.

**2. A read pass, not a score run.** 31 questions, one run each, read by hand.
Repeating runs you are about to read yourself buys nothing and costs 3×.

**3. Eleven curated questions and twenty random ones.** The curated set tests
what we thought of. The random draw from Natural Questions — frozen, seeded,
nothing filtered — tests what we didn't. **Every instance of the dominant
failure mode came from the random set; the curated set surfaced none of it.**

**4. The finding.** Five of six random-set failures were one defect: the right
article was retrieved and the answer lives in the article *body*, which the
tool never fetches. Verified per case against the API rather than inferred.
Zero fabrications in 31 runs, so grounding was never the problem we expected.

**5. Rebuild the instrument before the agent.** Retrieval recall was measuring
"did the article I predicted come back" rather than "did the evidence come
back". Correctness moved to hand-authored accepted phrasings, checked against
the answer and — separately — against the retrieved text, because for a
multi-hop question the evidence is the intermediate facts and the answer
appears in no article.

**6. Judge only where determinism was measured to fail.** Five planned judged
dimensions became one. Ambiguity is the only one a deterministic proxy could
not do; correctness keeps a judge purely as an auditor of the string matcher.
Rubric `j1` is frozen and calibrated: **recall 19/19 across 47 questions**.

**7. V0 baseline.** 84 runs. 74% correct curated, 77% holdout, zero ungrounded
answers, zero judge/matcher disagreements — and stage-3 body-facts the largest
failure bucket in **both** arms, confirming the read-pass finding on data that
was not used to find it.

## Things that went wrong, kept on the record

The interesting parts of the log are the corrections, so they are documented
rather than tidied away:

- A deep-fact case asserted a fact was unreachable. **It wasn't** — a different
  article's intro carried it. Caught by verifying cases against live retrieval
  before committing them; it would have read as a synthesis failure every time
  the agent got it right.
- A deterministic fabricated-citation grader flagged honest answers twice and
  was **deleted** rather than patched. Detecting an invented citation needs
  semantics, and an unreliable signal in the exact layer is worse than no
  signal.
- Three separate measurement bugs, all one mistake: `bool(None)` is `False`, so
  a signal that was never computed read as one that failed. Found by reading
  output, not by tests. The suite now asserts the whole metric surface at once.
- The ambiguity judge caught **three labelling errors in the human ground
  truth**, including one where our own case file contradicted the label beside
  it. Only the corrections with evidence independent of the judge were applied;
  fixing the rest would have been fitting ground truth to the instrument.

## Guarantees worth knowing about

- **Frozen artifacts.** Prompts, judge rubrics and the random question sets are
  digest-tested. A calibrated rubric that gets edited detaches from the
  calibration describing it, while every row still names it.
- **The holdout cannot be read.** `--holdout` suppresses the review worksheet
  and label file entirely, and the cross-arm report emits holdout aggregates
  only — no case ids, no answers, no judge rationales. Enforced by tests, since
  a holdout you have analysed is training data.
- **Sweeps are resumable and failure-isolated**, errored runs are retried
  rather than frozen in, and a resume refuses a changed config.
- **Grader bugs cost a re-grade, not a re-run** — `evals/regrade.py` rebuilds
  results from saved traces with no API calls, carrying paid-for judge verdicts
  over untouched.
