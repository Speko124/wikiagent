"""The cross-arm report: curated and holdout side by side.

One rule dominates the design. The curated arm is reported case by case
because that is what error analysis needs. The holdout arm is reported as
aggregate values only — naming a case, quoting an answer or listing a failing
question would let the holdout teach us something, and then it is training
data. The guard is a test, not a convention.
"""

from __future__ import annotations

import json

from evals import report


def row(case_id, **kw):
    """A results row. Correctness is the judge's verdict, so unless a test
    supplies one it is derived from `answer_match` — the guardrail and the
    primary signal agreeing is the ordinary case."""
    base = dict(
        case_id=case_id, run_id=f"{case_id}#0", repeat=0, error=None,
        answer_match=True, evidence_match=True, answer_completeness=1.0,
        searched=True, n_searches=1, n_turns=2, cited_titles=["A"],
        answer="An answer.", input_tokens=100, output_tokens=50, latency_s=1.0,
        question="q?", answer_kind="extractive",
    )
    merged = {**base, **kw}
    if "judge" not in kw:
        match = merged.get("answer_match")
        merged["judge"] = (
            None if match is None
            else {"correctness": {"verdict": "correct" if match else "incorrect"}}
        )
    return merged


def write(tmp_path, name, rows, holdout=False):
    d = tmp_path / name
    (d / "traces").mkdir(parents=True)
    (d / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (d / "config.json").write_text(json.dumps({
        "model": "claude-haiku-4-5", "prompt_version": "v0", "top_k": 3,
        "repeats": 1, "holdout": holdout,
    }))
    return d


# --- the poisoning guard ----------------------------------------------------

def test_the_holdout_section_never_names_a_case(tmp_path):
    """The whole point. A named failing case is a lead, and following it turns
    the holdout into training data with nothing downstream able to detect it."""
    cur = write(tmp_path, "cur", [row("rosetta-year")])
    hld = write(tmp_path, "hld", [row("hd-secret", answer_match=False)], holdout=True)
    text = report.compare(cur, hld)

    head, holdout_section = text.split("## Holdout", 1)
    assert "hd-secret" not in holdout_section
    assert "hd-secret" not in text


def test_the_holdout_section_never_quotes_an_answer(tmp_path):
    cur = write(tmp_path, "cur", [row("c1")])
    hld = write(tmp_path, "hld", [row("hd-1", answer="A distinctive holdout answer.")],
                holdout=True)
    assert "distinctive holdout answer" not in report.compare(cur, hld)


def test_the_curated_section_does_name_cases(tmp_path):
    """The asymmetry is deliberate, so it is asserted rather than assumed."""
    cur = write(tmp_path, "cur", [row("rosetta-year", answer_match=False)])
    hld = write(tmp_path, "hld", [row("hd-1")], holdout=True)
    assert "rosetta-year" in report.compare(cur, hld)


def test_holdout_metrics_are_still_reported(tmp_path):
    """Suppressed detail, not suppressed measurement - the arm exists to give
    a number."""
    cur = write(tmp_path, "cur", [row("c1")])
    hld = write(tmp_path, "hld", [row("h1", answer_match=False), row("h2")],
                holdout=True)
    text = report.compare(cur, hld)
    assert "1/2" in text or "50%" in text


# --- the metrics ------------------------------------------------------------

def test_the_answer_evidence_cross_tab(tmp_path):
    """Four cells with four different meanings: grounded, answered from
    memory, had the evidence and didn't use it, never had it."""
    rows = [
        row("a", answer_match=True, evidence_match=True),
        row("b", answer_match=True, evidence_match=False),
        row("c", answer_match=False, evidence_match=True),
        row("d", answer_match=False, evidence_match=False),
    ]
    cur = write(tmp_path, "cur", rows)
    text = report.compare(cur, write(tmp_path, "hld", [row("h1")], holdout=True))
    assert "from memory" in text.lower()
    assert "evidence unused" in text.lower() or "didn't use" in text.lower()


def test_judge_disagreements_are_surfaced(tmp_path):
    """The audit. Where the string matcher and the judge disagree is where the
    accepted phrasings may be overfitted."""
    rows = [
        row("agree", answer_match=True,
            judge={"correctness": {"verdict": "correct"}}),
        row("clash", answer_match=False,
            judge={"correctness": {"verdict": "correct", "why": "paraphrase"}}),
    ]
    cur = write(tmp_path, "cur", rows)
    text = report.compare(cur, write(tmp_path, "hld", [row("h1")], holdout=True))
    assert "clash" in text


def test_holdout_judge_disagreements_are_counted_not_named(tmp_path):
    cur = write(tmp_path, "cur", [row("c1")])
    hld = write(tmp_path, "hld", [
        row("hd-clash", answer_match=False,
            judge={"correctness": {"verdict": "correct", "why": "leaky rationale"}}),
    ], holdout=True)
    text = report.compare(cur, hld)
    assert "hd-clash" not in text
    assert "leaky rationale" not in text


def test_configs_that_differ_are_called_out(tmp_path):
    """Comparing two arms run on different models is not a comparison."""
    cur = write(tmp_path, "cur", [row("c1")])
    hld = tmp_path / "hld"
    (hld / "traces").mkdir(parents=True)
    (hld / "results.jsonl").write_text(json.dumps(row("h1")) + "\n")
    (hld / "config.json").write_text(json.dumps({
        "model": "other", "prompt_version": "v0", "top_k": 3,
        "repeats": 1, "holdout": True,
    }))
    assert "differ" in report.compare(cur, hld).lower()


def test_a_missing_holdout_arm_is_not_fatal(tmp_path):
    """The curated numbers are still worth having before the holdout runs."""
    cur = write(tmp_path, "cur", [row("c1")])
    assert report.compare(cur, None)


# --- funnel attribution -----------------------------------------------------

def test_the_funnel_is_computed_not_hand_labelled():
    """Iteration 0 needed a human to read 31 traces. The same attribution is
    now three exact signals, which is what makes it repeatable per sweep."""
    rows = [
        row("a", answer_match=True, evidence_match=True),
        row("b", answer_match=True, evidence_match=False),
        row("c", answer_match=False, evidence_match=True),
        row("d", answer_match=False, evidence_match=False, gold_shown=True),
        row("e", answer_match=False, evidence_match=False, gold_shown=False),
        row("f", answer_match=False, evidence_match=False, searched=False,
            n_searches=0),
    ]
    f = report.funnel(rows)
    assert f["correct, grounded"] == 1
    assert f["5 grounding: answered from memory"] == 1
    assert f["4 synthesis: had the evidence, answered wrong"] == 1
    assert f["3 evidence: right article, fact not in the retrieved text"] == 1
    assert f["2 retrieval: the answer-bearing article never surfaced"] == 1
    assert f["1 query: did not search at all"] == 1


def test_unscorable_cases_sit_outside_the_funnel():
    """Abstention cases have no correct answer to attribute, so counting them
    anywhere would distort every stage below."""
    f = report.funnel([row("x", answer_match=None, evidence_match=None)])
    assert f["not scorable (abstention cases)"] == 1
    assert sum(v for k, v in f.items() if k.startswith(("1", "2", "3"))) == 0


def test_the_funnel_appears_for_both_arms(tmp_path):
    cur = write(tmp_path, "cur", [row("c1", answer_match=False, evidence_match=False)])
    hld = write(tmp_path, "hld", [row("h1", answer_match=False, evidence_match=False)],
                holdout=True)
    text = report.compare(cur, hld)
    assert "Funnel" in text


def test_a_missing_evidence_spec_is_not_read_as_ungrounded():
    """turing-nobel's evidence is an absence, so it has no spec. Unknown
    grounding is not the same as ungrounded - conflating them invents a
    failure out of a missing check. Found by reading the V0 report: the funnel
    said 6 answered-from-memory where the cross-tab said 3."""
    f = report.funnel([row("t", answer_match=True, evidence_match=None)])
    assert f["correct, evidence not checkable"] == 1
    assert f["5 grounding: answered from memory"] == 0


def test_unscorable_runs_cannot_disagree_with_the_judge():
    """`bool(None)` is False, so an abstention case would read as a matcher
    'incorrect' on every run and manufacture a disagreement with the judge.
    Found by reading the V0 report: all 8 reported clashes were abstention
    cases where nothing had been scored."""
    rows = [row("abstain", answer_match=None,
                judge={"correctness": {"verdict": "correct", "why": "right to decline"}})]
    text = report.compare(write.__wrapped__ if False else None, None) if False else None
    m = report._metrics(rows)
    assert m["_clashes"] == []


# --- the None-is-not-False sweep --------------------------------------------

def test_no_metric_counts_an_unmeasured_signal_as_a_failure(tmp_path):
    """Three bugs in one sitting were this same mistake: `bool(None)` is False,
    so a signal that was never computed reads as a signal that failed. This
    asserts the whole surface at once rather than one metric at a time.

    Would have caught: the funnel calling unknown-grounding 'answered from
    memory', the report manufacturing 8 judge disagreements out of abstention
    cases, and evidence requiring every requirement inside one tool call.
    """
    blank = row("c1", answer_match=None, evidence_match=None,
                answer_completeness=None, gold_shown=None, judge=None)
    m = report._metrics([blank])

    # Nothing unmeasured may land in a rate's numerator or denominator.
    assert m["correct"] == "0/1 (0%)"       # unresolved is not a success
    assert m["unresolved"] == "1"           # and is visible as such
    assert m["correct_contains"] == "n/a"   # no accepted phrasings
    assert m["evidence_found"] == "n/a"
    assert m["coverage"].startswith("n/a")
    assert m["_clashes"] == []
    # Nor in any funnel stage that names a failure.
    f = report.funnel([blank])
    assert f["not scorable (abstention cases)"] == 1
    assert sum(v for k, v in f.items() if k[0].isdigit()) == 0


def test_a_partially_measured_row_only_counts_where_it_was_measured(tmp_path):
    """The subtler half: a row with a real answer signal and an absent evidence
    signal belongs in the correctness rate and nowhere near the grounding one."""
    partial = row("c1", answer_match=True, evidence_match=None,
                  answer_completeness=1.0)
    m = report._metrics([partial])
    assert m["correct"] == "1/1 (100%)"
    assert m["evidence_found"] == "n/a"

    assert report.funnel([partial])["correct, evidence not checkable"] == 1


def test_an_unclear_judge_verdict_against_a_confident_matcher_is_surfaced(tmp_path):
    """`unclear` is not a non-answer. This is the cell that caught
    arpanet-first-message, where an accepted phrasing matched unrelated text
    and certified two failures as passes - and the report was discarding it,
    reporting 0 disagreements while the audit was working."""
    cur = write(tmp_path, "cur", [row("suspect", answer_match=True,
        judge={"correctness": {"verdict": "unclear", "why": "cannot confirm"}})])
    text = report.compare(cur, None)
    assert "suspect" in text
    assert "cannot confirm" in text


def test_holdout_hedged_verdicts_are_counted_not_named(tmp_path):
    cur = write(tmp_path, "cur", [row("c1")])
    hld = write(tmp_path, "hld", [row("hd-hedge", answer_match=True,
        judge={"correctness": {"verdict": "unclear", "why": "leaky"}})], holdout=True)
    text = report.compare(cur, hld)
    assert "hd-hedge" not in text and "leaky" not in text


def test_pass_at_k_is_stricter_than_the_run_rate():
    """A per-run rate hides the shape: 50% could be one case that always works
    beside one that never does, or two that flip a coin - and those need
    different responses."""
    rows = [
        row("always", answer_match=True), row("always", answer_match=True),
        row("never", answer_match=False), row("never", answer_match=False),
        row("coinflip", answer_match=True), row("coinflip", answer_match=False),
    ]
    solid, n_questions, buckets = report.pass_at_k(rows, repeats=2)
    assert (solid, n_questions) == (1, 3)      # only `always` passes every repeat
    assert buckets == {"solid (k/k)": 1, "flaky": 1, "systematic (0/k)": 1,
                       "incomplete": 0, "unresolved": 0}


def test_a_question_with_nothing_scored_stays_in_the_denominator():
    """Superseded the old behaviour of dropping it. A question nothing could
    be said about is one the system failed to resolve, and removing it from
    the denominator makes the set look easier than it was."""
    solid, n_questions, buckets = report.pass_at_k(
        [row("x", answer_match=None, judge=None)], repeats=1)
    assert (solid, n_questions) == (0, 1)
    assert buckets["unresolved"] == 1


def test_declining_is_correct_only_where_the_case_has_no_answer_to_give():
    """This is what finally closes the abstention gap. The same verdict means
    opposite things depending on the case: on `paris-weather` declining is the
    right answer, on `home-alone-toy-store` it is a failure to find one."""
    declined = {"correctness": {"verdict": "declined", "why": "no answer given"}}
    abstention = row("paris-weather", answer_match=None, answer_kind="none",
                     judge=declined)
    lookup = row("home-alone", answer_match=None, answer_kind="extractive",
                 judge=declined)
    assert report.judged_correct(abstention) is True
    assert report.judged_correct(lookup) is False


def test_an_unclear_verdict_is_not_a_success():
    """It stays in the denominator. `judged_correct` still returns None so the
    run is never scored as *wrong* in the funnel, but headline correctness
    counts confirmed successes over everything attempted."""
    unclear = row("c1", answer_match=True,
                  judge={"correctness": {"verdict": "unclear", "why": "disputed"}})
    assert report.judged_correct(unclear) is None
    m = report._metrics([unclear])
    assert m["correct"] == "0/1 (0%)"
    assert m["unresolved"] == "1"


def test_the_guardrail_disagreeing_with_the_judge_is_surfaced():
    """Neither overrides the other. A disagreement means one of them is wrong
    and a human should look - which is the entire reason to keep both."""
    clash = row("c1", answer_match=True,
                judge={"correctness": {"verdict": "incorrect", "why": "wrong entity"}})
    assert len(report._metrics([clash])["_guardrail_clash"]) == 1


def test_the_report_shows_turn_max_not_only_the_mean():
    """A runaway loop is invisible in a mean over 54 runs. V1 had one run hit
    the 10-turn guard while the mean stayed at 2.6."""
    rows = [row("a", n_turns=2), row("b", n_turns=2), row("c", n_turns=10)]
    turns = report._metrics(rows)["turns"]
    assert turns.endswith("/ 10")     # "mean / max"


def test_fetch_use_is_reported_as_a_rate_not_only_a_total():
    """'22 fetches' does not say whether one run made 22 or 22 runs made one.
    The rate is what tells you the tool is used selectively."""
    rows = [row("a", n_fetches=1, escalated=True), row("b", n_fetches=0)]
    m = report._metrics(rows)
    assert m["fetch_rate"] == "1/2 (50%)"
    assert m["unescalated_fetches"] == "0"


def test_fetch_spread_separates_escalation_from_thrash():
    """One fetch is the intended pattern and costs one extra turn; two means
    the agent is lost. A mean over 54 runs cannot tell those apart - in V1 the
    only two-fetch runs were the single case that hit the turn guard."""
    rows = [row("a", n_fetches=0, n_turns=2), row("b", n_fetches=1, n_turns=3),
            row("c", n_fetches=2, n_turns=9)]
    m = report._metrics(rows)
    assert m["fetch_spread"] == "0x1 · 1x1 · 2x1"
    assert "2 fetch: 9.0t" in m["turns_by_fetch"]


# --- pass^k must be strict ---------------------------------------------------

def test_an_unscored_run_cannot_count_toward_passing_every_repeat():
    """pass^k claims the case was correct on *every* one of k repeats. A run
    the judge would not score is not a demonstrated pass, and dropping it
    silently shrinks k.

    Live instance: `tesla-origin` at v0 was [correct, unclear, unclear] and was
    reported as pass^3 solid on the strength of one run.
    """
    unclear = {"correctness": {"verdict": "unclear", "why": "disputed"}}
    rows = [
        row("c", answer_match=True),
        row("c", answer_match=None, judge=unclear),
        row("c", answer_match=None, judge=unclear),
    ]
    solid, n_cases, buckets = report.pass_at_k(rows, repeats=3)
    assert solid == 0, "one scored run out of three is not pass^3"
    assert buckets["incomplete"] == 1


def test_a_case_correct_on_every_repeat_still_counts():
    rows = [row("c", answer_match=True) for _ in range(3)]
    solid, n_cases, buckets = report.pass_at_k(rows, repeats=3)
    assert (solid, n_cases) == (1, 1)
    assert buckets["solid (k/k)"] == 1


def test_an_errored_run_also_blocks_a_solid_claim():
    """An error says nothing about the agent, which is exactly why it cannot
    be counted as a pass."""
    rows = [row("c", answer_match=True), row("c", answer_match=True),
            row("c", answer_match=None, error="boom", judge=None)]
    solid, _, buckets = report.pass_at_k(rows, repeats=3)
    assert solid == 0
    assert buckets["incomplete"] == 1


def test_all_scored_runs_wrong_is_systematic_not_incomplete():
    rows = [row("c", answer_match=False) for _ in range(3)]
    _, _, buckets = report.pass_at_k(rows, repeats=3)
    assert buckets["systematic (0/k)"] == 1


def test_ambiguity_verdicts_reach_the_report():
    """They were being collected per run and never surfaced, so the dimension
    was paid for and invisible. Counted over distinct cases, since ambiguity
    is a property of the question and does not vary across repeats."""
    amb = {"ambiguity": {"ambiguous": True, "why": "two readings", "flags": []},
           "correctness": {"verdict": "correct"}}
    plain = {"ambiguity": {"ambiguous": False, "why": "", "flags": []},
             "correctness": {"verdict": "correct"}}
    rows = [row("a", judge=amb), row("a", judge=amb), row("b", judge=plain)]
    m = report._metrics(rows)
    assert m["ambiguous_questions"] == "1/2 (50%)"
    assert m["correct_on_ambiguous"] == "2/2 (100%)"


def test_coverage_ignores_single_requirement_cases():
    """A one-requirement spec scores 0.0 or 1.0, which is `answer_match` under
    another name. Averaging those in produced a metric that looked like a
    fourth dimension and tracked correctness exactly - 39 of 45 curated runs,
    and zero partial scores across two versions."""
    rows = [
        row("single", answer_completeness=1.0, n_answer_requirements=1),
        row("multi", answer_completeness=0.5, n_answer_requirements=5),
    ]
    m = report._metrics(rows)
    assert m["coverage"].startswith("50%")      # the multi-fact case only
    assert "1 multi-fact cases" in m["coverage"]


def test_coverage_says_so_when_no_case_exercises_it():
    rows = [row("single", answer_completeness=1.0, n_answer_requirements=1)]
    assert report._metrics(rows)["coverage"].startswith("n/a")


# --- the canonical metric contract ------------------------------------------

def test_all_run_correctness_counts_every_attempted_run():
    """Headline correctness is confirmed-correct over ALL attempted runs.
    `unclear`, errors and declines are not successes, and excluding them from
    the denominator flatters the score - it moved holdout V0 from 70% to 81%."""
    rows = [
        row("a", answer_match=True),                                    # correct
        row("b", answer_match=False),                                   # incorrect
        row("c", answer_match=None,
            judge={"correctness": {"verdict": "unclear", "why": ""}}),  # unresolved
        row("d", answer_match=None, error="boom", judge=None),          # errored
    ]
    assert report._metrics(rows)["correct"] == "1/4 (25%)"


def test_an_inappropriate_decline_is_not_a_success():
    """Declining is correct only where the case has no answer to give."""
    declined = {"correctness": {"verdict": "declined", "why": ""}}
    lookup = row("has-answer", answer_kind="extractive", judge=declined)
    abstention = row("no-answer", answer_kind="none", judge=declined)
    assert report._metrics([lookup])["correct"] == "0/1 (0%)"
    assert report._metrics([abstention])["correct"] == "1/1 (100%)"


def test_pass_at_k_keeps_unresolved_questions_in_the_denominator():
    """A question nothing could be said about is not removed from the set; it
    is a question the system failed to resolve."""
    rows = [
        row("solid", answer_match=True), row("solid", answer_match=True),
        row("dark", answer_match=None, judge=None),
        row("dark", answer_match=None, judge=None),
    ]
    solid, n_questions, buckets = report.pass_at_k(rows, repeats=2)
    assert (solid, n_questions) == (1, 2)          # 2 questions, not 1
    assert buckets["unresolved"] == 1


def test_evidence_shows_its_eligible_denominator():
    """Evidence is only checkable where a case declares what evidence would
    look like, so the eligible count has to be visible next to the rate."""
    rows = [row("a", evidence_match=True), row("b", evidence_match=None)]
    assert report._metrics(rows)["evidence_found"] == "1/1 (100%)"


# --- outcome decomposition ---------------------------------------------------

def test_the_five_outcomes_are_mutually_exclusive_and_sum_to_all_runs():
    """The decomposition's whole value is that it accounts for every attempted
    run exactly once. If the categories can overlap or leave a gap, the
    breakdown stops explaining the headline."""
    rows = [
        row("a", judge={"correctness": {"verdict": "correct"}}),
        row("b", judge={"correctness": {"verdict": "incorrect"}}),
        row("c", answer_kind="none", judge={"correctness": {"verdict": "declined"}}),
        row("d", answer_kind="extractive",
            judge={"correctness": {"verdict": "declined"}}),
        row("e", judge={"correctness": {"verdict": "unclear"}}),
        row("f", error="boom", judge=None),
    ]
    out = report.outcomes(rows)
    assert sum(out.values()) == len(rows)
    assert out["confirmed success"] == 2      # correct + appropriate decline
    assert out["wrong answer"] == 1
    assert out["answerable non-answer"] == 1
    assert out["evaluator unresolved"] == 1
    assert out["execution failure"] == 1


def test_an_evaluator_unresolved_run_is_not_an_agent_non_answer():
    """The judge failing to decide is an instrument problem; the agent
    declining is a behaviour. Merging them would hide which one moved."""
    rows = [row("a", judge={"correctness": {"verdict": "unclear"}})]
    out = report.outcomes(rows)
    assert out["evaluator unresolved"] == 1
    assert out["answerable non-answer"] == 0


def test_an_execution_failure_outranks_any_verdict():
    """A run that produced no final answer has nothing to grade, so a stale or
    partial verdict must not reclassify it."""
    rows = [row("a", error="stopped after 10 turns",
                judge={"correctness": {"verdict": "correct"}})]
    assert report.outcomes(rows)["execution failure"] == 1


def test_confirmed_success_matches_the_headline_correctness_numerator():
    """The decomposition explains the headline, so its success bucket has to
    be the same number, computed the same way."""
    rows = [
        row("a", judge={"correctness": {"verdict": "correct"}}),
        row("b", answer_kind="none", judge={"correctness": {"verdict": "declined"}}),
        row("c", judge={"correctness": {"verdict": "incorrect"}}),
    ]
    assert report.outcomes(rows)["confirmed success"] == 2
    assert report._metrics(rows)["correct"].startswith("2/3")


def test_an_errored_run_with_a_stale_verdict_is_not_counted_correct():
    """The headline numerator and the decomposition's success bucket are the
    same computation, so they cannot disagree. Computed separately, a run that
    errored while carrying an old `correct` verdict counted as a success in
    one place and a failure in the other."""
    rows = [row("a", error="boom", judge={"correctness": {"verdict": "correct"}})]
    m = report._metrics(rows)
    assert m["correct"] == "0/1 (0%)"
    assert m["_outcomes"]["execution failure"] == 1
    assert m["_outcomes"]["confirmed success"] == 0


def test_a_malformed_judge_payload_is_unresolved_not_a_crash():
    """One bad row must not take down aggregation for a whole sweep."""
    assert report.outcome_of(
        {"judge": {"correctness": "correct"}, "answer": "x"}
    ) == "evaluator unresolved"
    assert report.outcome_of({"judge": None, "answer": "x"}) == "evaluator unresolved"


# --- outcome x evidence diagnosis -------------------------------------------

def test_diagnosis_routes_each_failure_to_the_work_it_implies():
    """The point of crossing outcome with evidence: the same wrong answer
    means retrieval work or reasoning work depending on whether the evidence
    ever reached the model, and those are different fixes."""
    rows = [
        row("a", evidence_match=False,
            judge={"correctness": {"verdict": "incorrect"}}),
        row("b", evidence_match=True,
            judge={"correctness": {"verdict": "incorrect"}}),
        row("c", evidence_match=False, answer_kind="extractive",
            judge={"correctness": {"verdict": "declined"}}),
        row("d", evidence_match=True, answer_kind="extractive",
            judge={"correctness": {"verdict": "declined"}}),
        row("e", judge={"correctness": {"verdict": "unclear"}}),
        row("f", error="boom", judge=None),
    ]
    d = report.diagnose(rows)
    assert d["Retrieval / Evidence — no answer-bearing text reached the model"] == 2  # a, c
    assert d["Synthesis — evidence present, answer wrong"] == 1                              # b
    assert d["Answer — evidence present, declined anyway"] == 1                     # d
    assert d["Evaluator — judge rubric, reference answer, or ambiguity"] == 1         # e
    assert d["Execution — agent loop or infrastructure"] == 1                        # f


def test_diagnosis_only_covers_failures_and_is_exhaustive_over_them():
    """Successes need no diagnosis, and every non-success must land in exactly
    one bucket or the breakdown stops accounting for the gap."""
    rows = [
        row("ok", judge={"correctness": {"verdict": "correct"}}),
        row("abstain-ok", answer_kind="none",
            judge={"correctness": {"verdict": "declined"}}),
        row("bad", evidence_match=True,
            judge={"correctness": {"verdict": "incorrect"}}),
    ]
    d = report.diagnose(rows)
    failures = len(rows) - report.outcomes(rows)["confirmed success"]
    assert sum(d.values()) == failures == 1


def test_diagnosis_is_stable_across_every_outcome_kind():
    """Exercises unclear, appropriate decline, inappropriate decline and error
    together, since those are the four that shift between versions."""
    rows = [
        row("unclear", judge={"correctness": {"verdict": "unclear"}}),
        row("good-decline", answer_kind="none",
            judge={"correctness": {"verdict": "declined"}}),
        row("bad-decline", answer_kind="extractive", evidence_match=True,
            judge={"correctness": {"verdict": "declined"}}),
        row("err", error="boom", judge=None),
    ]
    d = report.diagnose(rows)
    assert sum(d.values()) == 3          # the appropriate decline is a success
    assert d["Evaluator — judge rubric, reference answer, or ambiguity"] == 1
    assert d["Answer — evidence present, declined anyway"] == 1
    assert d["Execution — agent loop or infrastructure"] == 1


def test_a_decline_with_evidence_is_an_answer_stage_failure_not_synthesis():
    """Declining is not answering wrongly. Routing declines into synthesis
    said the model reasoned badly when it never committed to a claim, and it
    put the same two runs in two different stages depending on which table you
    read."""
    rows = [row("d", evidence_match=True, answer_kind="extractive",
                judge={"correctness": {"verdict": "declined"}})]
    f = report.funnel(rows)
    assert f["4 synthesis: had the evidence, answered wrong"] == 0
    assert f["6 answer: declined with the evidence in hand"] == 1
