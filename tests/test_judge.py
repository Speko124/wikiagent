"""The judge: one dimension it owns, one it audits.

Two calls, not one, and the reason is the false-negative mechanism. If the
judge sees the agent's answer while deciding whether the *question* was
ambiguous, a cleanly-handled answer makes the question look unambiguous — the
agent's competence erases the evidence that it was needed. So the inputs are
separated and a test enforces it.
"""

from __future__ import annotations

import pytest

from conftest import Block, Response, StubClient
from evals import judge
from evals.cases import Case


def verdict_block(**fields) -> Block:
    return Block("tool_use", id="t1", name=judge.TOOL_NAME, input=fields)


CASE = Case(
    id="c1",
    question="Where is Tesla from?",
    expected="Ambiguous: the company or the person.",
    dimensions=["ambiguous-entity"],
)


# --- correctness (audit role) -----------------------------------------------

def test_correctness_returns_the_recorded_verdict():
    client = StubClient([Response([verdict_block(verdict="correct", why="matches")])])
    out = judge.correctness(CASE, "Tesla, Inc. is American.", client=client)
    assert out["verdict"] == "correct"
    assert out["why"] == "matches"


def test_correctness_records_the_judge_identity():
    """A verdict whose model and rubric aren't recorded can't be compared with
    anything later, and drift becomes undetectable."""
    client = StubClient([Response([verdict_block(verdict="correct", why="")])])
    out = judge.correctness(CASE, "answer", client=client)
    assert out["judge_model"] == judge.JUDGE_MODEL
    assert out["rubric"] == judge.RUBRIC_VERSION


def test_correctness_does_not_see_the_retrieved_text():
    """Correctness is about truth; showing the judge what was retrieved turns
    it into consistency-with-retrieval, which is a different question and the
    one faithfulness asks."""
    client = StubClient([Response([verdict_block(verdict="correct", why="")])])
    judge.correctness(CASE, "answer", client=client)
    sent = str(client.calls[0])
    assert "retrieved" not in sent.lower() or "SEARCH RESULTS" not in sent


# --- ambiguity (owned dimension) --------------------------------------------

def test_ambiguity_judges_the_question_not_the_answer():
    client = StubClient([Response([verdict_block(ambiguous=True, why="entity")])])
    out = judge.ambiguity(CASE, ["Nikola Tesla", "Tesla, Inc."], client=client)
    assert out["ambiguous"] is True


def test_the_agents_answer_cannot_reach_the_ambiguity_judge():
    """The structural guard on the false-negative mode. If the answer reaches
    this call, a well-handled ambiguity reads as no ambiguity and the very
    behaviour we want to reward becomes invisible. Enforced on the signature,
    so it can't be reintroduced by passing 'just a bit of context'."""
    import inspect

    assert set(inspect.signature(judge.ambiguity).parameters) == {
        "case", "retrieved_titles", "client",
    }


def test_the_reference_answer_does_not_leak_into_the_ambiguity_call():
    """`expected` often states the ambiguity outright ('Ambiguous: the company
    or the person'). Showing it would let the judge read the verdict off the
    label - scoring near-perfectly during calibration and being worthless on
    the questions where we don't already know the answer."""
    client = StubClient([Response([verdict_block(ambiguous=False, why="")])])
    judge.ambiguity(CASE, ["Nikola Tesla"], client=client)
    assert CASE.expected not in str(client.calls[0])


def test_ambiguity_sees_the_retrieved_titles():
    """Ambiguity is often only concrete once you see what exists — 'Tesla' is
    ambiguous *because* both articles come back."""
    client = StubClient([Response([verdict_block(ambiguous=True, why="")])])
    judge.ambiguity(CASE, ["Nikola Tesla", "Tesla, Inc."], client=client)
    assert "Tesla, Inc." in str(client.calls[0])


# --- robustness -------------------------------------------------------------

def test_a_missing_verdict_is_recorded_not_raised():
    """One malformed judge response must not end a sweep."""
    client = StubClient([Response([Block("text", text="I'm not sure")])])
    out = judge.correctness(CASE, "answer", client=client)
    assert out["verdict"] is None
    assert out["error"]


def test_the_judge_refuses_to_be_the_agent_model():
    """Same-model judging carries a documented self-preference bias, and the
    guard belongs in code rather than in a doc nobody rereads."""
    from wikiagent import agent

    assert judge.JUDGE_MODEL != agent.DEFAULT_MODEL


def test_the_judge_forces_the_verdict_tool():
    """Free-text verdicts have to be parsed, and parsing is where categorical
    grading quietly turns into string archaeology."""
    client = StubClient([Response([verdict_block(verdict="correct", why="")])])
    judge.correctness(CASE, "answer", client=client)
    assert client.calls[0]["tool_choice"]["name"] == judge.TOOL_NAME


@pytest.mark.parametrize("fn", ["correctness", "ambiguity"])
def test_both_judges_use_the_judge_model(fn):
    client = StubClient([Response([verdict_block(verdict="correct", ambiguous=True)])])
    args = (CASE, "answer") if fn == "correctness" else (CASE, ["T"])
    getattr(judge, fn)(*args, client=client)
    assert client.calls[0]["model"] == judge.JUDGE_MODEL


# --- versioning -------------------------------------------------------------

# Same canary as the agent prompts, for a sharper reason: calibration numbers
# belong to a rubric version. Editing a calibrated rubric in place detaches the
# alignment evidence from the thing it measured, and every row still says `j1`.
# If a change is intended, add a version, re-calibrate, and update this digest.
FROZEN_RUBRICS = {"j1": "702cc4a8a5468af5", "j2": "b9b6fe414c0199c8"}


@pytest.mark.parametrize("version,digest", sorted(FROZEN_RUBRICS.items()))
def test_calibrated_rubrics_are_not_edited_in_place(version, digest):
    import hashlib

    r = judge.rubric(version)
    actual = hashlib.sha256(
        (r.correctness + "\x00" + r.ambiguity).encode()
    ).hexdigest()[:16]
    assert actual == digest, (
        f"Rubric {version} changed. Its calibration no longer describes it. "
        "Add a new version and re-calibrate instead of editing this one."
    )


def test_every_verdict_records_the_rubric_it_came_from():
    client = StubClient([Response([verdict_block(verdict="correct", why="")])])
    out = judge.correctness(CASE, "answer", client=client)
    assert out["rubric"] in judge.RUBRICS


def test_unknown_rubric_is_rejected():
    with pytest.raises(KeyError, match="j1"):
        judge.rubric("j99")


# --- known-defect flagging --------------------------------------------------

def test_the_known_category_error_is_flagged():
    """j1 sometimes calls a question ambiguous because the *answer* can't be
    determined. Flagged rather than fixed - a rubric edit would detach j1 from
    the calibration that justifies trusting it."""
    v = {"ambiguous": True, "why": "No Wikipedia article identifies this song."}
    assert "suspect:undeterminable-not-ambiguous" in judge.flag_defects(v)


def test_a_genuine_ambiguity_rationale_is_not_flagged():
    v = {"ambiguous": True, "why": "Tesla could mean the company or the person."}
    assert judge.flag_defects(v) == []


def test_case_metadata_corroborates_the_flag():
    v = {"ambiguous": True, "why": "two readings"}
    c = Case(id="c", question="q", expected="e", dimensions=["false-premise"])
    assert "suspect:false-premise-case" in judge.flag_defects(v, c)


def test_unambiguous_verdicts_have_nothing_to_flag():
    """A false positive is the only error this can catch; a 'no' verdict has
    none to find."""
    assert judge.flag_defects({"ambiguous": False, "why": "no source exists"}) == []


def test_flagging_never_edits_the_verdict():
    """Flag, don't override - the same rule the judge follows with the
    deterministic matcher. An instrument that silently corrects another hides
    the disagreement, which was the useful part."""
    v = {"ambiguous": True, "why": "no source exists"}
    before = dict(v)
    judge.flag_defects(v)
    assert v == before


# --- the sweep adapter ------------------------------------------------------

def test_the_sweep_judge_returns_both_dimensions():
    client = StubClient([
        Response([verdict_block(verdict="correct", why="ok")]),
        Response([verdict_block(ambiguous=True, why="two readings")]),
    ])
    trace = type("T", (), {"answer": "a", "shown_titles": ["T1"]})()
    out = judge.SweepJudge(client=client)(CASE, trace)
    assert out["correctness"]["verdict"] == "correct"
    assert out["ambiguity"]["ambiguous"] is True


def test_ambiguity_is_judged_once_per_question_not_once_per_run():
    """Ambiguity is a property of the question and does not vary across
    repeats. Re-judging it every run would triple the cost and invite three
    different answers to the same question."""
    client = StubClient([
        Response([verdict_block(verdict="correct", why="")]),
        Response([verdict_block(ambiguous=True, why="two readings")]),
        Response([verdict_block(verdict="correct", why="")]),
    ], repeat_last=True)
    trace = type("T", (), {"answer": "a", "shown_titles": ["T1"]})()
    j = judge.SweepJudge(client=client)
    j(CASE, trace)
    j(CASE, trace)
    # Identified by the tool schema, not by text: `case.expected` often
    # contains the word "ambiguous" and would match every correctness call.
    ambiguity_calls = [
        c for c in client.calls
        if "ambiguous" in c["tools"][0]["input_schema"]["properties"]
    ]
    assert len(ambiguity_calls) == 1


def test_the_sweep_judge_carries_its_identity_for_the_runner():
    """The runner reads these onto every row, so a results file can never be
    mistaken for one judged by something else."""
    j = judge.SweepJudge()
    assert j.model == judge.JUDGE_MODEL
    assert j.version == judge.RUBRIC_VERSION


def test_defect_flags_ride_along_with_the_verdict():
    client = StubClient([
        Response([verdict_block(verdict="correct", why="")]),
        Response([verdict_block(ambiguous=True, why="No Wikipedia article exists")]),
    ])
    trace = type("T", (), {"answer": "a", "shown_titles": []})()
    out = judge.SweepJudge(client=client)(CASE, trace)
    assert out["ambiguity"]["flags"] == ["suspect:undeterminable-not-ambiguous"]


def test_j2_carries_j1s_ambiguity_text_unchanged():
    """j2 revises correctness only. The ambiguity prompt is byte-identical, so
    its 19/19 recall calibration still describes it and does not have to be
    re-earned - but that has to be asserted, not assumed."""
    assert judge.rubric("j2").ambiguity == judge.rubric("j1").ambiguity
    assert judge.rubric("j2").correctness != judge.rubric("j1").correctness


def test_declining_is_its_own_verdict_not_unclear():
    """The reason for j2. j1 folded every honest failure into `unclear`, so a
    primary correctness score could not separate 'did not answer' from 'the
    reference is disputed' - and both fell outside the numerator."""
    client = StubClient([Response([verdict_block(verdict="declined", why="no answer given")])])
    out = judge.correctness(CASE, "I could not find that.", client=client)
    assert out["verdict"] == "declined"
    schema = client.calls[0]["tools"][0]["input_schema"]
    assert set(schema["properties"]["verdict"]["enum"]) == {
        "correct", "incorrect", "declined", "unclear"}
