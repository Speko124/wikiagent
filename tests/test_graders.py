"""Deterministic graders.

These emit raw signals and nothing else — no funnel stages, no pass/fail
verdict. Staging happens in Phase 5 analysis over traces, so an unanticipated
failure mode means relabelling rather than rewriting the harness.

Every signal here is exact. The LLM judge is deliberately a separate, much
smaller surface.
"""

from __future__ import annotations

import pytest

from conftest import Response, StubClient, text, tool_use
from evals import graders
from evals.cases import Case
from wikiagent import agent, wikipedia


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(wikipedia, "DEFAULT_CACHE_DIR", tmp_path / "cache")


def fake_trace(monkeypatch, titles, answer="Answer.", searched=True):
    """Build a real Trace by driving the real agent against canned search results."""
    monkeypatch.setattr(
        wikipedia,
        "_fetch",
        lambda query, fetch_k, timeout: [
            wikipedia.Article(t, f"https://en.wikipedia.org/wiki/{t}", "extract", i)
            for i, t in enumerate(titles)
        ][:fetch_k],
    )
    responses = (
        [Response([tool_use("q")], stop_reason="tool_use"), Response([text(answer)])]
        if searched
        else [Response([text(answer)])]
    )
    return agent.ask("q", model="claude-haiku-4-5", top_k=3,
                     client=StubClient(responses))


CASE = Case(id="c1", question="q", expected="e",
            gold_articles=["Marie Curie"], dimensions=["factual"])
NO_GOLD = Case(id="c2", question="q", expected="e",
               gold_articles=[], dimensions=["unanswerable"])


# --- search behaviour -------------------------------------------------------

def test_records_whether_the_agent_searched(monkeypatch):
    t = fake_trace(monkeypatch, ["A"], searched=True)
    assert graders.grade(CASE, t)["searched"] is True

    t2 = fake_trace(monkeypatch, ["A"], searched=False)
    assert graders.grade(NO_GOLD, t2)["searched"] is False


def test_counts_searches_and_turns(monkeypatch):
    t = fake_trace(monkeypatch, ["A"])
    g = graders.grade(CASE, t)
    assert g["n_searches"] == 1
    assert g["n_turns"] == 2


# --- retrieval recall -------------------------------------------------------

def test_gold_retrieved_when_shown(monkeypatch):
    t = fake_trace(monkeypatch, ["Marie Curie", "B", "C"])
    g = graders.grade(CASE, t)
    assert g["gold_shown"] is True
    assert g["gold_fetched"] is True


def test_gold_missed_entirely(monkeypatch):
    t = fake_trace(monkeypatch, ["X", "Y", "Z"])
    g = graders.grade(CASE, t)
    assert g["gold_shown"] is False
    assert g["gold_fetched"] is False


def test_gold_fetched_but_not_shown_is_distinguishable(monkeypatch):
    """This is the whole point of over-fetching: it separates 'retrieval can't
    find it' from 'top_k was too small', which have different fixes."""
    t = fake_trace(monkeypatch, ["X", "Y", "Z", "Marie Curie", "W"])
    g = graders.grade(CASE, t)
    assert g["gold_shown"] is False
    assert g["gold_fetched"] is True


def test_gold_signals_are_none_when_the_case_has_no_gold(monkeypatch):
    """Not False — None. A case with no gold article must not count against
    retrieval recall; that would inflate the denominator."""
    t = fake_trace(monkeypatch, ["A", "B"])
    g = graders.grade(NO_GOLD, t)
    assert g["gold_shown"] is None
    assert g["gold_fetched"] is None


def test_gold_matching_ignores_case_and_whitespace(monkeypatch):
    case = Case(id="c", question="q", expected="e",
                gold_articles=["  marie curie "], dimensions=["f"])
    t = fake_trace(monkeypatch, ["Marie Curie"])
    assert graders.grade(case, t)["gold_shown"] is True


def test_any_gold_article_counts(monkeypatch):
    case = Case(id="c", question="q", expected="e",
                gold_articles=["Nope", "Marie Curie"], dimensions=["f"])
    t = fake_trace(monkeypatch, ["Marie Curie"])
    assert graders.grade(case, t)["gold_shown"] is True


# --- citation integrity -----------------------------------------------------

def test_cited_titles_are_extracted_from_the_answer(monkeypatch):
    t = fake_trace(monkeypatch, ["Marie Curie", "Pierre Curie"],
                   answer="According to the Marie Curie article, she won twice.")
    g = graders.grade(CASE, t)
    assert "Marie Curie" in g["cited_titles"]


def test_citation_matching_survives_surrounding_prose(monkeypatch):
    t = fake_trace(monkeypatch, ["Marie Curie"],
                   answer="The Marie Curie article says she won twice.")
    g = graders.grade(CASE, t)
    assert g["cited_titles"] == ["Marie Curie"]
    assert g["cites_any_retrieved"] is True


def test_naming_no_retrieved_title_is_recorded(monkeypatch):
    """Weaker than 'fabricated' on purpose — it says the agent named none of
    what it was shown, not that it invented something. Whether the attribution
    was invented is a semantic call, and belongs to the judge."""
    t = fake_trace(monkeypatch, ["Marie Curie"],
                   answer="Per the Albert Einstein article, she won twice.")
    g = graders.grade(CASE, t)
    assert g["cited_titles"] == []
    assert g["cites_any_retrieved"] is False


def test_partial_title_does_not_count_as_a_citation(monkeypatch):
    """'Penicillin' must not match inside 'History of penicillin'."""
    t = fake_trace(monkeypatch, ["History of penicillin"],
                   answer="Penicillin was discovered in 1928.")
    assert graders.grade(NO_GOLD, t)["cited_titles"] == []


def test_no_citation_when_nothing_was_retrieved(monkeypatch):
    t = fake_trace(monkeypatch, [], answer="I couldn't find anything.", searched=False)
    g = graders.grade(NO_GOLD, t)
    assert g["cited_titles"] == []
    assert g["cites_any_retrieved"] is False


# --- cost and health --------------------------------------------------------

def test_records_usage_and_latency(monkeypatch):
    g = graders.grade(CASE, fake_trace(monkeypatch, ["A"]))
    assert g["input_tokens"] > 0
    assert g["output_tokens"] > 0
    assert g["latency_s"] >= 0


def test_records_errors(monkeypatch):
    t = fake_trace(monkeypatch, ["A"])
    t.error = "Stopped after 10 turns without a final answer."
    assert graders.grade(CASE, t)["error"] is not None


def test_grade_output_is_json_serializable(monkeypatch):
    import json
    json.dumps(graders.grade(CASE, fake_trace(monkeypatch, ["A"])))


# --- answer and evidence matching -------------------------------------------

def test_evidence_is_attributed_to_the_search_that_found_it(monkeypatch):
    """Which search found it, not just whether some search did. Five searches
    where the first would have done is a different problem from five searches
    that were all needed."""
    monkeypatch.setattr(
        wikipedia, "_fetch",
        lambda query, fetch_k, timeout: [
            wikipedia.Article(f"T-{query}", "u", f"extract about {query}", 0)
        ],
    )
    responses = [
        Response([tool_use("alpha", id="t1")], stop_reason="tool_use"),
        Response([tool_use("bravo", id="t2")], stop_reason="tool_use"),
        Response([text("Answer.")]),
    ]
    t = agent.ask("q", model="claude-haiku-4-5", top_k=3,
                  client=StubClient(responses))
    case = Case(id="c", question="q", expected="e", dimensions=["f"],
                evidence_contains=[["bravo"]])
    g = graders.grade(case, t)
    assert g["evidence_match"] is True
    assert g["evidence_found_at_search"] == 1      # the second search, not the first
    assert g["evidence_found_in"] == ["T-bravo"]


def test_evidence_absent_from_every_search_is_a_miss(monkeypatch):
    t = fake_trace(monkeypatch, ["A"])
    case = Case(id="c", question="q", expected="e", dimensions=["f"],
                evidence_contains=[["nowhere"]])
    g = graders.grade(case, t)
    assert g["evidence_match"] is False
    assert g["evidence_found_at_search"] is None


def test_answer_and_evidence_can_disagree(monkeypatch):
    """The interesting cell: the evidence never came back, yet the answer is
    right - meaning it came from memory, not from Wikipedia."""
    t = fake_trace(monkeypatch, ["A"], answer="The answer is 1799.")
    case = Case(id="c", question="q", expected="e", dimensions=["f"],
                answer_contains=[["1799"]], evidence_contains=[["1799"]])
    g = graders.grade(case, t)
    assert g["answer_match"] is True
    assert g["evidence_match"] is False


def test_unscorable_cases_are_none_not_false(monkeypatch):
    t = fake_trace(monkeypatch, ["A"])
    g = graders.grade(NO_GOLD, t)
    assert g["answer_match"] is None
    assert g["evidence_match"] is None


def test_searches_are_recorded_per_query(monkeypatch):
    """A flattened title list across several searches can't say which query
    produced what."""
    t = fake_trace(monkeypatch, ["A", "B", "C", "D", "E"])
    [search] = graders.grade(CASE, t)["searches"]
    assert search["query"] == "q"
    assert search["shown"] == ["A", "B", "C"]
    assert search["beyond_top_k"] == ["D", "E"]


def test_grade_emits_no_verdict(monkeypatch):
    """Graders emit signals; verdicts come later. Baking pass/fail in here would
    freeze the funnel into the harness."""
    g = graders.grade(CASE, fake_trace(monkeypatch, ["A"]))
    assert not any(k in g for k in ("passed", "verdict", "score", "stage"))


def test_grade_emits_no_semantic_judgement(monkeypatch):
    """Correctness, faithfulness and posture are the judge's. Anything here
    that needed semantics would be an unreliable signal in an exact layer."""
    g = graders.grade(CASE, fake_trace(monkeypatch, ["A"]))
    assert not any(
        k in g for k in ("correct", "faithful", "posture", "fabricated_citation")
    )


def test_evidence_accumulates_across_searches(monkeypatch):
    """A multi-hop question gathers evidence in separate searches by design.
    Requiring every requirement inside one call marked bologna-oxford-older as
    'answered from memory' in the V0 baseline, when the answer plainly quoted
    both dates from two searches."""
    monkeypatch.setattr(
        wikipedia, "_fetch",
        lambda query, fetch_k, timeout: [
            wikipedia.Article(f"T-{query}", "u", f"founded in {query}", 0)
        ],
    )
    t = agent.ask("q", model="claude-haiku-4-5", top_k=3, client=StubClient([
        Response([tool_use("1088", id="t1")], stop_reason="tool_use"),
        Response([tool_use("1096", id="t2")], stop_reason="tool_use"),
        Response([text("Bologna is older.")]),
    ]))
    case = Case(id="c", question="q", expected="e", dimensions=["f"],
                evidence_contains=[["1088"], ["1096"]])
    g = graders.grade(case, t)
    assert g["evidence_match"] is True
    assert g["evidence_found_at_search"] == 1  # complete only after the second
