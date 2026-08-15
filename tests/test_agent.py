"""Agent loop and trace, with no API calls.

Two groups matter most. The API-contract tests (assistant content echoed back
whole, all tool results in one user message) guard things that fail loudly but
only in production. The trace tests guard things that fail silently — a trace
that misreports what the model saw would make every eval number wrong while
looking perfectly healthy.
"""

from __future__ import annotations

import httpx
import pytest

import anthropic
from conftest import Response, StubClient, Usage, text, thinking, tool_use
from wikiagent import agent, wikipedia


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch, tmp_path):
    """Never touch the real cache, and never hit the network."""
    monkeypatch.setattr(wikipedia, "DEFAULT_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(
        wikipedia,
        "_fetch",
        lambda query, fetch_k, timeout: [
            wikipedia.Article(f"Article {i}", f"u{i}", f"extract {i}", i)
            for i in range(fetch_k)
        ],
    )


HAIKU = "claude-haiku-4-5"


def answer_only(msg="Final answer."):
    return StubClient([Response([text(msg)])])


def search_then_answer(query="marie curie", msg="Done."):
    return StubClient([
        Response([thinking("look it up"), text("Searching."), tool_use(query)],
                 stop_reason="tool_use"),
        Response([text(msg)]),
    ])


# --- basic flow -------------------------------------------------------------

def test_answer_without_tool_use_ends_in_one_turn():
    t = agent.ask("q", model=HAIKU, client=answer_only("42."))
    assert t.answer == "42."
    assert t.n_turns == 1
    assert t.searched is False
    assert t.error is None


def test_tool_use_runs_the_search_and_continues():
    t = agent.ask("q", model=HAIKU, client=search_then_answer("marie curie"))
    assert t.answer == "Done."
    assert t.n_turns == 2
    assert t.queries == ["marie curie"]
    assert t.n_searches == 1


def test_thinking_is_captured_in_the_trace():
    t = agent.ask("q", model="claude-opus-5", client=search_then_answer())
    assert t.turns[0].thinking == "look it up"


# --- API contracts ----------------------------------------------------------

def test_assistant_turn_is_echoed_back_unmodified():
    """Thinking blocks must survive the round trip verbatim; the API rejects
    modified ones when continuing on the same model."""
    client = search_then_answer()
    agent.ask("q", model="claude-opus-5", client=client)

    second = client.calls[1]["messages"]
    assert [m["role"] for m in second] == ["user", "assistant", "user"]
    assert [b.type for b in second[1]["content"]] == ["thinking", "text", "tool_use"]


def test_parallel_tool_results_go_back_in_one_user_message():
    """Splitting results across messages trains the model out of parallel calls."""
    client = StubClient([
        Response(
            [tool_use("a", id="t1"), tool_use("b", id="t2")], stop_reason="tool_use"
        ),
        Response([text("Done.")]),
    ])
    t = agent.ask("q", model=HAIKU, client=client)

    final_user = client.calls[1]["messages"][-1]
    assert final_user["role"] == "user"
    assert len(final_user["content"]) == 2
    assert [b["tool_use_id"] for b in final_user["content"]] == ["t1", "t2"]
    assert t.n_searches == 2


def test_tool_result_ids_match_the_requested_calls():
    client = search_then_answer()
    agent.ask("q", model=HAIKU, client=client)
    result = client.calls[1]["messages"][-1]["content"][0]
    assert result["type"] == "tool_result"
    assert result["tool_use_id"] == "toolu_1"
    assert result["is_error"] is False


def test_search_failure_is_reported_as_an_error_result(monkeypatch):
    """A failed tool must come back with is_error, not be silently dropped."""
    monkeypatch.setattr(
        wikipedia,
        "_fetch",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("network down")),
    )
    client = search_then_answer()
    agent.ask("q", model=HAIKU, client=client)
    result = client.calls[1]["messages"][-1]["content"][0]
    assert result["is_error"] is True
    assert "network down" in result["content"]


# --- model capability gating ------------------------------------------------

def test_haiku_request_omits_thinking_and_effort():
    """Both are Opus/Sonnet-5-family parameters; sending them to Haiku is a 400."""
    client = answer_only()
    agent.ask("q", model=HAIKU, client=client)
    req = client.calls[0]
    assert "thinking" not in req
    assert "output_config" not in req


def test_opus_request_includes_adaptive_thinking():
    client = answer_only()
    agent.ask("q", model="claude-opus-5", client=client)
    assert client.calls[0]["thinking"] == {
        "type": "adaptive",
        "display": "summarized",
    }


def test_effort_is_passed_through_on_supported_models():
    client = answer_only()
    agent.ask("q", model="claude-opus-5", effort="medium", client=client)
    assert client.calls[0]["output_config"] == {"effort": "medium"}


def test_effort_on_haiku_fails_loudly_rather_than_400ing():
    with pytest.raises(ValueError, match="not supported"):
        agent.ask("q", model=HAIKU, effort="high", client=answer_only())


@pytest.mark.parametrize(
    "model,supported",
    [
        ("claude-opus-5", True),
        ("claude-sonnet-5", True),
        ("claude-haiku-4-5", False),
        ("claude-sonnet-4-5", False),
    ],
)
def test_adaptive_thinking_support_matrix(model, supported):
    assert agent._supports_adaptive_thinking(model) is supported


# --- the no-tool control arm ------------------------------------------------

def test_control_arm_declares_no_tools():
    client = answer_only()
    agent.ask("q", model=HAIKU, use_tools=False, client=client)
    assert "tools" not in client.calls[0]


def test_control_arm_cannot_retrieve_even_if_the_model_asks():
    """The arm only means anything if retrieval is impossible, not merely
    undeclared — otherwise a stray tool_use silently contaminates the control."""
    client = StubClient([Response([tool_use("q"), text("answered")],
                                  stop_reason="tool_use")])
    t = agent.ask("q", model=HAIKU, use_tools=False, client=client)
    assert t.searched is False
    assert t.n_searches == 0
    assert t.answer == "answered"


# --- top_k ------------------------------------------------------------------

def test_top_k_controls_what_the_model_sees_not_what_is_traced():
    client = search_then_answer()
    t = agent.ask("q", model=HAIKU, top_k=2, client=client)

    call = t.turns[0].tool_calls[0]
    assert len(call.shown_titles) == 2
    assert len(call.titles) == wikipedia.OVERFETCH
    assert "Article 4" not in call.rendered
    assert t.shown_titles != t.retrieved_titles


def test_tool_description_states_the_result_count():
    client = answer_only()
    agent.ask("q", model=HAIKU, top_k=5, client=client)
    assert "five best-matching" in client.calls[0]["tools"][0]["description"]


# --- failure handling -------------------------------------------------------

def test_refusal_stops_the_loop_and_is_recorded():
    client = StubClient([Response([], stop_reason="refusal")])
    t = agent.ask("q", model=HAIKU, client=client)
    assert t.error and "refusal" in t.error
    assert t.n_turns == 1


def test_runaway_loop_is_capped_and_flagged():
    """Hitting the cap is itself a finding — it must not look like success."""
    client = StubClient(
        [Response([tool_use("again")], stop_reason="tool_use")], repeat_last=True
    )
    t = agent.ask("q", model=HAIKU, client=client)
    assert t.n_turns == agent.MAX_TURNS
    assert t.error and "without a final answer" in t.error
    assert t.answer == ""


def test_api_errors_are_captured_rather_than_raised():
    class Boom:
        def create(self, **kw):
            raise anthropic.APIConnectionError(
                request=httpx.Request("POST", "https://api.anthropic.com")
            )

    client = type("C", (), {"messages": Boom()})()
    t = agent.ask("q", model=HAIKU, client=client)
    assert t.error and "APIConnectionError" in t.error
    assert t.answer == ""


# --- trace bookkeeping ------------------------------------------------------

def test_usage_is_summed_across_turns():
    client = StubClient([
        Response([tool_use("a")], stop_reason="tool_use",
                 usage=Usage(input_tokens=100, output_tokens=10)),
        Response([text("done")], usage=Usage(input_tokens=300, output_tokens=20)),
    ])
    t = agent.ask("q", model=HAIKU, client=client)
    assert t.usage == {
        "input_tokens": 400,
        "output_tokens": 30,
        "cache_read_tokens": 0,
    }


def test_repeated_titles_are_deduplicated_in_order():
    client = StubClient([
        Response([tool_use("a", id="t1"), tool_use("b", id="t2")],
                 stop_reason="tool_use"),
        Response([text("done")]),
    ])
    t = agent.ask("q", model=HAIKU, top_k=2, client=client)
    # Both searches return the same canned titles.
    assert t.shown_titles == ["Article 0", "Article 1"]


def test_cache_hits_are_counted():
    client = StubClient([
        Response([tool_use("same")], stop_reason="tool_use"),
        Response([tool_use("same")], stop_reason="tool_use"),
        Response([text("done")]),
    ])
    t = agent.ask("q", model=HAIKU, client=client)
    assert t.n_searches == 2
    assert t.cache_hits == 1, "the second identical query should hit the cache"


def test_trace_serializes_and_saves(tmp_path):
    t = agent.ask("q", model=HAIKU, client=search_then_answer())
    d = t.to_dict()
    assert d["question"] == "q"
    assert d["model"] == HAIKU
    assert d["summary"]["n_searches"] == 1
    assert d["turns"][0]["tool_calls"][0]["rendered"]

    path = t.save(tmp_path / "sub" / "trace.json")
    assert path.exists()
    import json
    assert json.loads(path.read_text())["answer"] == "Done."
