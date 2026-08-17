"""Re-grading a paid-for sweep from its traces.

The point is that a grader bug costs a re-grade rather than a re-run. The
tests guard the two ways that could go wrong: losing what the graders don't
own, and re-rolling the judge.
"""

from __future__ import annotations

import json

from evals import regrade
from evals.cases import Case
from wikiagent.trace import ToolCall, Trace, Turn


def build(tmp_path, evidence_in_call="the answer is 1799"):
    (tmp_path / "traces").mkdir(parents=True)
    t = Trace(question="q", model="m", prompt_version="v0", answer="It was 1799.")
    turn = Turn(index=0, input_tokens=10, output_tokens=5)
    turn.tool_calls.append(ToolCall(query="rosetta", raw={"results": [{"title": "A"}]},
                                    rendered=evidence_in_call, top_k=3))
    t.turns.append(turn)
    t.save(tmp_path / "traces" / "c1--r0.json")

    (tmp_path / "results.jsonl").write_text(json.dumps({
        "case_id": "c1", "run_id": "c1#0", "repeat": 0,
        "trace": "traces/c1--r0.json", "question": "q", "expected": "1799",
        "case_notes": "note", "config": {"model": "m"},
        "judge": {"correctness": {"verdict": "correct", "why": "paid for"}},
        "answer_match": None, "error": None,
    }) + "\n")

    cases = tmp_path / "cases.jsonl"
    cases.write_text(json.dumps({
        "id": "c1", "question": "q", "expected": "1799", "dimensions": ["factual"],
        "answer_contains": [["1799"]], "evidence_contains": [["1799"]],
    }) + "\n")
    return cases


def rows_of(tmp_path):
    return [json.loads(l) for l in (tmp_path / "results.jsonl").read_text().splitlines()]


def test_regrading_recomputes_the_deterministic_signals(tmp_path):
    cases = build(tmp_path)
    regrade.regrade(tmp_path, cases)
    row = rows_of(tmp_path)[0]
    assert row["answer_match"] is True
    assert row["evidence_match"] is True


def test_the_judge_verdict_is_carried_over_not_re_requested(tmp_path):
    """Judge calls cost money and are non-deterministic. Re-rolling them would
    silently move the judge/matcher agreement the audit depends on."""
    cases = build(tmp_path)
    regrade.regrade(tmp_path, cases)
    assert rows_of(tmp_path)[0]["judge"]["correctness"]["why"] == "paid for"


def test_everything_the_graders_do_not_own_survives(tmp_path):
    cases = build(tmp_path)
    regrade.regrade(tmp_path, cases)
    row = rows_of(tmp_path)[0]
    for key in ("run_id", "repeat", "trace", "question", "expected", "case_notes",
                "config"):
        assert key in row, f"{key} lost in regrade"


def test_it_reports_how_many_rows_changed(tmp_path):
    cases = build(tmp_path)
    total, changed = regrade.regrade(tmp_path, cases)
    assert (total, changed) == (1, 1)
    total, changed = regrade.regrade(tmp_path, cases)
    assert (total, changed) == (1, 0)   # idempotent


def test_a_row_whose_case_no_longer_exists_is_left_alone(tmp_path):
    """Cases get renamed and retired between iterations. Dropping their rows
    would quietly shrink a historical sweep."""
    cases = build(tmp_path)
    cases.write_text(json.dumps({
        "id": "different", "question": "q", "expected": "e",
        "dimensions": ["factual"],
    }) + "\n")
    regrade.regrade(tmp_path, cases)
    assert len(rows_of(tmp_path)) == 1
