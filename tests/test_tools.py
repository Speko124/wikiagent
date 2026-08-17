"""Tool schema and dispatch.

The schema is prompt engineering — if the description says "three" while the
tool returns five, the model is being misinformed about its own tool.
"""

from __future__ import annotations

import pytest

from wikiagent import prompts, tools, wikipedia


def test_schema_shape_is_valid():
    s = tools.schema()
    assert s["name"] == "search_wikipedia"
    assert s["input_schema"]["required"] == ["query"]
    assert "query" in s["input_schema"]["properties"]
    assert s["input_schema"]["properties"]["query"]["description"]


@pytest.mark.parametrize(
    "top_k,phrase",
    [(1, "single"), (2, "two"), (3, "three"), (5, "five"), (7, "7")],
)
def test_description_matches_the_number_actually_returned(top_k, phrase):
    assert f"{phrase} best-matching" in tools.schema(top_k)["description"]


@pytest.mark.parametrize("version", sorted(prompts.PROMPTS))
def test_description_warns_that_only_intros_come_back(version):
    """The intro-only limitation is the single most important thing for the
    model to know — it's what should drive a re-query rather than a guess."""
    d = tools.schema(version=version)["description"].lower()
    assert "opening section" in d
    assert "not the whole article" in d or "not the full article" in d


def test_dispatch_runs_a_search(cache_dir, fake_search):
    fake_search(["A", "B", "C"])
    r = tools.dispatch(
        "search_wikipedia", {"query": "marie"}, cache_dir=cache_dir, use_cache=False
    )
    assert r.error is None
    assert [a.title for a in r.results] == ["A", "B", "C"]


def test_dispatch_passes_top_k_through(cache_dir, fake_search):
    fake_search(["A", "B", "C", "D", "E"])
    r = tools.dispatch(
        "search_wikipedia", {"query": "x"}, top_k=2,
        cache_dir=cache_dir, use_cache=False,
    )
    assert len(r.shown) == 2
    assert len(r.results) == wikipedia.OVERFETCH


def test_unknown_tool_is_reported_not_raised():
    r = tools.dispatch("delete_everything", {"query": "x"})
    assert r.error and "Unknown tool" in r.error
    assert "Search failed" in r.render()


@pytest.mark.parametrize("bad", [{}, {"query": ""}, {"query": "   "}, {"query": None}])
def test_malformed_input_is_reported_not_raised(bad):
    """A bad tool call should come back as an error the model can recover from,
    never as an exception that kills the run."""
    r = tools.dispatch("search_wikipedia", bad)
    assert r.error is not None
    assert "Search failed" in r.render()


def test_none_input_is_handled():
    assert tools.dispatch("search_wikipedia", None).error is not None
