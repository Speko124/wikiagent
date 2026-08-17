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
    base = dict(
        case_id=case_id, run_id=f"{case_id}#0", repeat=0, error=None,
        answer_match=True, evidence_match=True, answer_completeness=1.0,
        searched=True, n_searches=1, n_turns=2, cited_titles=["A"],
        answer="An answer.", input_tokens=100, output_tokens=50, latency_s=1.0,
        question="q?", judge=None,
    )
    return {**base, **kw}


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
                answer_completeness=None, gold_shown=None,
                judge={"correctness": {"verdict": "correct", "why": "declined"}})
    m = report._metrics([blank])

    # Nothing unmeasured may land in a rate's numerator or denominator.
    assert m["correct"] == "n/a"
    assert m["evidence_found"] == "n/a"
    assert m["completeness"] == "n/a"
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
    solid, n_cases, buckets = report.pass_at_k(rows)
    assert (solid, n_cases) == (1, 3)          # only `always` passes every repeat
    assert buckets == {"solid (k/k)": 1, "flaky": 1, "systematic (0/k)": 1}


def test_pass_at_k_ignores_unscorable_cases():
    assert report.pass_at_k([row("x", answer_match=None)]) == (0, 0, {
        "solid (k/k)": 0, "flaky": 0, "systematic (0/k)": 0})
