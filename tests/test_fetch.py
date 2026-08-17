"""`fetch_article`: the second tool.

Exists because of one measured finding. Stage 3 — right article retrieved, the
answer in the body the tool never fetched — is 12 of 54 curated runs and 3 of
30 holdout runs, the largest failure bucket in both arms across two
independent iterations.

Its limits are known in advance and asserted here, because a fix whose
boundary is untested is a fix nobody can size. `explaintext` omits infoboxes
entirely, so `lets-make-a-deal-location` **should still fail** after this
lands. That case exists to mark the edge.
"""

from __future__ import annotations

import pytest

from conftest import requires_network
from wikiagent import tools, wikipedia


# --- fetching ---------------------------------------------------------------

def test_fetch_returns_the_body_not_just_the_intro(monkeypatch):
    monkeypatch.setattr(wikipedia, "_fetch_full",
                        lambda title, timeout: ("T", "Intro. " + "Body sentence. " * 200))
    [article] = wikipedia.fetch("T", use_cache=False).results
    assert "Body sentence." in article.extract
    assert len(article.extract) > wikipedia.EXTRACT_CHARS


def test_a_long_article_is_bounded(monkeypatch):
    """An unbounded article blows the context window on a single call and makes
    cost per run unpredictable. The cap is far larger than a search result and
    far smaller than the longest Wikipedia articles."""
    monkeypatch.setattr(wikipedia, "_fetch_full",
                        lambda title, timeout: ("T", "word " * 200_000))
    [article] = wikipedia.fetch("T", use_cache=False).results
    assert len(article.extract) <= wikipedia.ARTICLE_CHARS + 16
    assert article.extract.endswith(wikipedia.TRUNCATION_MARKER)


def test_a_missing_article_is_reported_not_raised(monkeypatch):
    monkeypatch.setattr(wikipedia, "_fetch_full", lambda title, timeout: (None, ""))
    response = tools.dispatch("fetch_article", {"title": "Nope"}, use_cache=False)
    assert response.error and "Nope" in response.error
    assert "search" in response.render().lower()   # tells the model what to do next


def test_the_resolved_title_is_recorded(monkeypatch):
    """Redirects mean the article you get may not be the title you asked for.
    Scoring 'did it open the right article' needs the one it actually got."""
    monkeypatch.setattr(wikipedia, "_fetch_full",
                        lambda title, timeout: ("Actual Title", "Body."))
    [article] = wikipedia.fetch("redirect source", use_cache=False).results
    assert article.title == "Actual Title"


def test_fetch_and_search_do_not_share_a_cache_key(cache_dir, monkeypatch):
    """Same key space would let a cached search for X serve a fetch of X, and
    silently hand back the intro when the body was asked for - which is the
    exact failure this tool exists to remove."""
    monkeypatch.setattr(wikipedia, "_fetch", lambda q, k, t: [
        wikipedia.Article("T", "u", "INTRO ONLY", 1)])
    monkeypatch.setattr(wikipedia, "_fetch_full", lambda title, timeout: ("T", "FULL BODY"))
    wikipedia.search("T", cache_dir=cache_dir)
    assert "FULL BODY" in wikipedia.fetch("T", cache_dir=cache_dir).render()


def test_fetches_are_cached(cache_dir, monkeypatch):
    calls = []
    monkeypatch.setattr(wikipedia, "_fetch_full",
                        lambda title, timeout: (calls.append(title), ("T", "Body."))[1])
    wikipedia.fetch("T", cache_dir=cache_dir)
    wikipedia.fetch("T", cache_dir=cache_dir)
    assert len(calls) == 1


def test_a_failed_fetch_is_never_cached(cache_dir, monkeypatch):
    """Same rule as search: one network blip must not poison that title
    forever."""
    monkeypatch.setattr(wikipedia, "_fetch_full",
                        lambda title, timeout: (_ for _ in ()).throw(RuntimeError("boom")))
    assert wikipedia.fetch("T", cache_dir=cache_dir).error
    monkeypatch.setattr(wikipedia, "_fetch_full", lambda title, timeout: ("T", "Body."))
    assert wikipedia.fetch("T", cache_dir=cache_dir).error is None


# --- the tool surface -------------------------------------------------------

def test_v0_declares_search_only_so_the_baseline_stays_reproducible():
    """Adding a tool must not retroactively change what v0 was. The V0 results
    on disk were produced by an agent with one tool, and re-running them has to
    give an agent with one tool."""
    assert [t["name"] for t in tools.all_schemas(version="v0")] == ["search_wikipedia"]


def test_both_tools_are_declared():
    assert {t["name"] for t in tools.all_schemas(version="v1")} == {
        "search_wikipedia", "fetch_article"}


def test_fetch_takes_an_exact_title_not_a_query():
    [schema] = [t for t in tools.all_schemas(version="v1") if t["name"] == "fetch_article"]
    assert schema["input_schema"]["required"] == ["title"]


def test_the_description_states_where_titles_come_from_and_what_is_missing():
    """It only works on exact titles, so the description has to say they come
    from search results or the model invents one. And it has to say infoboxes
    are absent, or the model will keep looking for data that is not there."""
    [schema] = [t for t in tools.all_schemas(version="v1") if t["name"] == "fetch_article"]
    description = schema["description"].lower()
    assert "search" in description
    assert "infobox" in description or "table" in description


def test_a_bad_title_type_is_reported_not_raised():
    assert tools.dispatch("fetch_article", {"title": None}).error


# --- known limits, asserted --------------------------------------------------

@requires_network
def test_fetch_reaches_a_body_fact_that_search_cannot():
    """The whole justification, end to end."""
    intro = wikipedia.search("Home Alone 2", top_k=1, use_cache=False)
    [full] = wikipedia.fetch("Home Alone 2: Lost in New York", use_cache=False).results
    assert "Duncan" not in "".join(a.extract for a in intro.shown)
    assert "Duncan" in full.extract


@requires_network
def test_infobox_data_is_still_missing_after_a_full_fetch():
    """The boundary of the fix, asserted rather than assumed.
    `lets-make-a-deal-location` should still fail at V1 - if it starts passing,
    the measurement changed, not the capability."""
    [full] = wikipedia.fetch("Let's Make a Deal", use_cache=False).results
    assert "Raleigh" not in full.extract
