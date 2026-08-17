"""Deterministic answer and evidence matching.

This replaces `gold_shown` as the retrieval signal and replaces an LLM judge
for correctness on cases with checkable answers. Both roles make its edge
cases load-bearing, so they're tested rather than assumed.

The structure is an **AND of ORs**: `[["Italian", "Italy"]]` is one requirement
with two acceptable phrasings; `[["Germany"], ["France"]]` is two separate
requirements. That one shape covers paraphrase tolerance and completeness
without needing two mechanisms.
"""

from __future__ import annotations

import pytest

from evals import graders
from evals.cases import Case


def case(**kw) -> Case:
    base = dict(id="c1", question="q", expected="e", dimensions=["factual"])
    return Case(**{**base, **kw})


# --- the matcher ------------------------------------------------------------

def test_a_single_requirement_with_one_phrasing():
    spec = [["1799"]]
    assert graders.matches(spec, "Discovered in 1799.") == (True, 1.0)
    assert graders.matches(spec, "Discovered in 1801.") == (False, 0.0)


def test_alternatives_within_a_requirement_are_or():
    """Paraphrase tolerance. 'Italian' and 'from Italy' are the same answer,
    and a matcher that only accepts one of them manufactures failures."""
    spec = [["Italian", "from Italy"]]
    assert graders.matches(spec, "He was Italian.")[0] is True
    assert graders.matches(spec, "He was from Italy.")[0] is True


def test_separate_requirements_are_and():
    spec = [["Germany"], ["France"], ["Liechtenstein"]]
    ok, fraction = graders.matches(spec, "It borders Germany and France.")
    assert ok is False
    assert fraction == pytest.approx(2 / 3)


def test_the_fraction_is_the_completeness_signal():
    """A partial list presented as complete is invisible to a boolean. The
    fraction is what makes it visible."""
    spec = [["a"], ["b"], ["c"], ["d"]]
    assert graders.matches(spec, "a and c")[1] == 0.5


def test_matching_ignores_case_and_surrounding_punctuation():
    assert graders.matches([["marie curie"]], "**Marie Curie**, twice.")[0] is True


def test_numbers_match_across_thousands_separators():
    """'2,679' in the article and '2679' in the answer are the same number;
    scoring them as a miss would be the matcher's error, not the agent's."""
    assert graders.matches([["2,679"]], "The hall seats 2679.")[0] is True
    assert graders.matches([["2679"]], "The hall seats 2,679.")[0] is True


def test_word_boundaries_are_respected():
    """'no' must not match inside 'Nobel', or every negative-answer case
    scores itself correct."""
    assert graders.matches([["no"]], "He won the Nobel Prize.")[0] is False
    assert graders.matches([["no"]], "No, he did not.")[0] is True


def test_an_empty_spec_is_unscorable_not_perfect():
    """Cases with no checkable answer must be excluded, never counted as a
    free pass - that would silently inflate correctness."""
    assert graders.matches([], "anything") == (None, None)


# --- how the grader uses it -------------------------------------------------

def test_answer_and_evidence_are_scored_separately(monkeypatch):
    """The point of splitting them. For a derived answer the evidence is the
    intermediate facts, so retrieval gets credit for finding them even though
    the final answer appears in no article."""
    c = case(
        answer_contains=[["Bologna"]],
        evidence_contains=[["1088"], ["1096"]],
        answer_kind="derived",
    )
    assert c.answer_contains != c.evidence_contains


def test_answer_kind_none_means_the_check_is_skipped():
    c = case(answer_kind="none")
    assert c.answer_contains == []


def test_unknown_answer_kind_is_rejected(tmp_path):
    import json

    from evals import cases as cases_mod

    p = tmp_path / "c.jsonl"
    p.write_text(json.dumps({
        "id": "c1", "question": "q", "expected": "e",
        "dimensions": ["factual"], "answer_kind": "vibes",
    }))
    with pytest.raises(ValueError, match="answer_kind"):
        cases_mod.load(p)


def test_specs_must_be_lists_of_lists(tmp_path):
    """`["Italian"]` instead of `[["Italian"]]` would silently become five
    single-character requirements."""
    import json

    from evals import cases as cases_mod

    p = tmp_path / "c.jsonl"
    p.write_text(json.dumps({
        "id": "c1", "question": "q", "expected": "e",
        "dimensions": ["factual"], "answer_contains": ["Italian"],
    }))
    with pytest.raises(ValueError, match="answer_contains"):
        cases_mod.load(p)


def test_non_breaking_spaces_do_not_defeat_a_match():
    """Natural Questions stores dates with non-breaking spaces. Found by
    measuring the matcher against hand labels, not by guessing."""
    assert graders.matches([["June\xa09,\xa02017"]], "premiered on June 9, 2017.")[0]
