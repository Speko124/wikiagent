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
FROZEN_RUBRICS = {"j1": "702cc4a8a5468af5"}


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
