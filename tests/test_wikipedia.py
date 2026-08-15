"""Retrieval layer.

The cache tests matter most: a cache that poisons itself, or that silently
invalidates when an unrelated knob moves, corrupts eval comparisons without
ever raising an error.
"""

from __future__ import annotations

import json

import pytest

from conftest import article, requires_network
from wikiagent import wikipedia


# --- truncation -------------------------------------------------------------

def test_short_text_passes_through():
    assert wikipedia._truncate("Hello world.", limit=100) == "Hello world."


def test_collapses_whitespace():
    assert wikipedia._truncate("a\n\n  b\tc") == "a b c"


def test_truncates_at_sentence_boundary():
    body = "First sentence here. " * 20
    out = wikipedia._truncate(body, limit=100)
    assert out.endswith("[...]")
    # The kept portion must end at a full sentence, not mid-clause — a severed
    # fact reads as complete and invites the model to answer from a fragment.
    assert out[: -len(" [...]")].endswith(".")
    assert len(out) <= 100 + len(" [...]")


def test_falls_back_to_word_boundary_without_sentences():
    out = wikipedia._truncate("word " * 100, limit=50)
    assert out.endswith("[...]")
    assert "  " not in out


# --- cache keying -----------------------------------------------------------

def test_cache_key_ignores_case_and_surrounding_space(tmp_path):
    a = wikipedia._cache_path("Marie Curie", 5, tmp_path)
    b = wikipedia._cache_path("  marie curie  ", 5, tmp_path)
    assert a == b


def test_cache_key_distinguishes_queries(tmp_path):
    a = wikipedia._cache_path("Marie Curie", 5, tmp_path)
    b = wikipedia._cache_path("Pierre Curie", 5, tmp_path)
    assert a != b


def test_fetch_count_never_below_overfetch():
    assert wikipedia._fetch_count(1) == wikipedia.OVERFETCH
    assert wikipedia._fetch_count(3) == wikipedia.OVERFETCH
    # ...but honours a top_k larger than the margin.
    assert wikipedia._fetch_count(9) == 9


# --- rendering --------------------------------------------------------------

def test_render_numbers_results_and_respects_top_k():
    r = wikipedia.SearchResponse(
        query="q", results=[article(t) for t in "ABCDE"], top_k=2
    )
    out = r.render()
    assert "[1] A" in out and "[2] B" in out
    assert "C" not in out, "results past top_k must never reach the model"
    assert len(r.shown) == 2


def test_render_reports_no_matches_rather_than_failing():
    out = wikipedia.SearchResponse(query="zzz", results=[]).render()
    assert "No Wikipedia articles matched" in out
    assert "zzz" in out


def test_render_surfaces_errors():
    out = wikipedia.SearchResponse(query="q", error="Timeout").render()
    assert "Search failed" in out and "Timeout" in out


# --- search + cache behaviour ----------------------------------------------

def test_first_search_is_a_miss_and_is_cached(cache_dir, fake_search):
    fake_search(["A", "B", "C"])
    r = wikipedia.search("q", cache_dir=cache_dir)
    assert r.cache_hit is False
    assert [a.title for a in r.results] == ["A", "B", "C"]
    assert list(cache_dir.glob("*.json")), "a successful search must be cached"


def test_second_search_is_served_from_cache(cache_dir, fake_search):
    calls = fake_search(["A", "B", "C"])
    wikipedia.search("q", cache_dir=cache_dir)
    r = wikipedia.search("q", cache_dir=cache_dir)
    assert r.cache_hit is True
    assert len(calls) == 1, "a cache hit must not touch the network"


def test_errors_are_never_cached(cache_dir, fake_search):
    """A transient network blip must not poison every later run of that query."""
    calls = fake_search([], error="boom")
    r = wikipedia.search("q", cache_dir=cache_dir)
    assert r.error and "boom" in r.error
    assert not list(cache_dir.glob("*.json"))

    # And the next attempt genuinely retries rather than replaying the failure.
    wikipedia.search("q", cache_dir=cache_dir)
    assert len(calls) == 2


def test_changing_top_k_reuses_the_cache(cache_dir, fake_search):
    """top_k controls rendering only. If it changed the cache key, every
    top_k experiment would silently refetch and re-time the whole suite."""
    calls = fake_search(["A", "B", "C", "D", "E"])
    wikipedia.search("q", top_k=3, cache_dir=cache_dir)
    r = wikipedia.search("q", top_k=5, cache_dir=cache_dir)
    assert r.cache_hit is True
    assert len(calls) == 1
    assert len(r.shown) == 5


def test_no_cache_bypasses_reads_and_writes(cache_dir, fake_search):
    calls = fake_search(["A"])
    wikipedia.search("q", cache_dir=cache_dir, use_cache=False)
    wikipedia.search("q", cache_dir=cache_dir, use_cache=False)
    assert len(calls) == 2
    assert not list(cache_dir.glob("*.json"))


def test_cached_payload_round_trips(cache_dir, fake_search):
    fake_search(["A", "B"])
    first = wikipedia.search("q", cache_dir=cache_dir)
    second = wikipedia.search("q", cache_dir=cache_dir)
    assert [a.title for a in first.results] == [a.title for a in second.results]
    assert [a.url for a in first.results] == [a.url for a in second.results]
    assert [a.extract for a in first.results] == [a.extract for a in second.results]


def test_search_overfetches_beyond_top_k(cache_dir, fake_search):
    """The surplus is what makes the 'would more have helped?' check free."""
    calls = fake_search(["A", "B", "C", "D", "E"])
    r = wikipedia.search("q", top_k=3, cache_dir=cache_dir)
    assert calls[0]["fetch_k"] == wikipedia.OVERFETCH
    assert len(r.results) == 5, "all fetched results stay available for analysis"
    assert len(r.shown) == 3, "but only top_k is shown to the model"


def test_to_dict_keeps_every_result_not_just_shown(cache_dir, fake_search):
    fake_search(["A", "B", "C", "D", "E"])
    d = wikipedia.search("q", top_k=2, cache_dir=cache_dir).to_dict()
    assert len(d["results"]) == 5
    assert d["top_k"] == 2


# --- ranking ---------------------------------------------------------------

def test_fetch_preserves_search_ranking(monkeypatch):
    """The extracts endpoint returns pages in arbitrary order; relevance rank
    comes from the search endpoint and must survive the join."""
    search_titles = ["Third", "First", "Second"]

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self._payload

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params):
            if params.get("list") == "search":
                return FakeResponse(
                    {"query": {"search": [{"title": t} for t in search_titles]}}
                )
            # Deliberately shuffled, and with one page that no longer exists.
            return FakeResponse({"query": {"pages": {
                "3": {"title": "Second", "extract": "s", "fullurl": "u", "pageid": 3},
                "1": {"title": "Third", "extract": "t", "fullurl": "u", "pageid": 1},
                "2": {"title": "First", "extract": "f", "fullurl": "u", "pageid": 2},
                "9": {"title": "Gone", "missing": ""},
            }}})

    monkeypatch.setattr(wikipedia.httpx, "Client", lambda **kw: FakeClient())
    got = [a.title for a in wikipedia._fetch("q", 5, 10.0)]
    assert got == search_titles
    assert "Gone" not in got, "missing pages must be dropped, not returned empty"


def test_fetch_returns_nothing_when_search_has_no_hits(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"query": {"search": []}}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params):
            return FakeResponse()

    monkeypatch.setattr(wikipedia.httpx, "Client", lambda **kw: FakeClient())
    assert wikipedia._fetch("nonsense", 5, 10.0) == []


# --- live API (opt-in) ------------------------------------------------------

@requires_network
def test_live_wikipedia_returns_usable_articles(cache_dir):
    r = wikipedia.search("Marie Curie", cache_dir=cache_dir, use_cache=False)
    assert r.error is None
    assert len(r.results) >= 3
    assert r.results[0].title == "Marie Curie"
    assert "Curie" in r.results[0].extract
    assert r.results[0].url.startswith("https://en.wikipedia.org/wiki/")
    assert all(len(a.extract) <= wikipedia.EXTRACT_CHARS + 10 for a in r.results)


@requires_network
def test_live_wikipedia_handles_no_matches(cache_dir):
    r = wikipedia.search(
        "qwzxjk nonexistent gibberish topic 12345", cache_dir=cache_dir, use_cache=False
    )
    assert r.error is None
    assert r.results == []
    assert "No Wikipedia articles matched" in r.render()
