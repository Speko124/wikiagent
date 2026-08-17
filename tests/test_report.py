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
