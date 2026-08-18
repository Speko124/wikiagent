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
                        lambda title=None, pageid=None, timeout=20.0: ("T", "Intro. " + "Body sentence. " * 200, 1))
    [article] = wikipedia.fetch("T", use_cache=False).results
    assert "Body sentence." in article.extract
    assert len(article.extract) > wikipedia.EXTRACT_CHARS


def test_a_long_article_is_bounded(monkeypatch):
    """An unbounded article blows the context window on a single call and makes
    cost per run unpredictable. The cap is far larger than a search result and
    far smaller than the longest Wikipedia articles."""
    monkeypatch.setattr(wikipedia, "_fetch_full",
                        lambda title=None, pageid=None, timeout=20.0: ("T", "word " * 200_000, 1))
    [article] = wikipedia.fetch("T", use_cache=False).results
    assert len(article.extract) <= wikipedia.ARTICLE_CHARS + 16
    assert article.extract.endswith(wikipedia.TRUNCATION_MARKER)


def test_a_missing_article_is_reported_not_raised(monkeypatch):
    monkeypatch.setattr(wikipedia, "_fetch_full",
                        lambda title=None, pageid=None, timeout=20.0: (None, "", None))
    monkeypatch.setattr(wikipedia, "_fetch", lambda q, k, t: [])
    response = tools.dispatch("fetch_article", {"title": "Nope"}, use_cache=False)
    assert response.error and "Nope" in response.error
    assert "search" in response.render().lower()   # tells the model what to do next


def test_the_resolved_title_is_recorded(monkeypatch):
    """Redirects mean the article you get may not be the title you asked for.
    Scoring 'did it open the right article' needs the one it actually got."""
    monkeypatch.setattr(wikipedia, "_fetch_full",
                        lambda title=None, pageid=None, timeout=20.0: ("Actual Title", "Body.", 5))
    [article] = wikipedia.fetch("redirect source", use_cache=False).results
    assert article.title == "Actual Title"


def test_fetch_and_search_do_not_share_a_cache_key(cache_dir, monkeypatch):
    """Same key space would let a cached search for X serve a fetch of X, and
    silently hand back the intro when the body was asked for - which is the
    exact failure this tool exists to remove."""
    monkeypatch.setattr(wikipedia, "_fetch", lambda q, k, t: [
        wikipedia.Article("T", "u", "INTRO ONLY", 1)])
    monkeypatch.setattr(wikipedia, "_fetch_full",
                        lambda title=None, pageid=None, timeout=20.0: ("T", "FULL BODY", 1))
    wikipedia.search("T", cache_dir=cache_dir)
    assert "FULL BODY" in wikipedia.fetch("T", cache_dir=cache_dir).render()


def test_fetches_are_cached(cache_dir, monkeypatch):
    calls = []
    monkeypatch.setattr(wikipedia, "_fetch_full",
                        lambda title=None, pageid=None, timeout=20.0: (calls.append(title), ("T", "Body.", 1))[1])
    wikipedia.fetch("T", cache_dir=cache_dir)
    wikipedia.fetch("T", cache_dir=cache_dir)
    assert len(calls) == 1


def test_a_failed_fetch_is_never_cached(cache_dir, monkeypatch):
    """Same rule as search: one network blip must not poison that title
    forever."""
    monkeypatch.setattr(wikipedia, "_fetch_full",
                        lambda title=None, pageid=None, timeout=20.0: (_ for _ in ()).throw(RuntimeError("boom")))
    assert wikipedia.fetch("T", cache_dir=cache_dir).error
    monkeypatch.setattr(wikipedia, "_fetch_full",
                        lambda title=None, pageid=None, timeout=20.0: ("T", "Body.", 1))
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
def test_the_char_cap_is_the_binding_constraint_not_the_tool():
    """Replaces a circular test.

    The old version asserted `"Raleigh" not in fetch(...).extract` and called
    that proof the fact was infobox-only. But `fetch` truncates at
    ARTICLE_CHARS, and Raleigh sits at offset ~15,650 of a 44,579-char article
    - so the assertion passed because of the cap, and would have passed no
    matter where the fact lived. It "verified" a claim it could not see.

    What is actually true: the fact is in the prose, past our cap. So
    `lets-make-a-deal-location` fails because the article is longer than we
    read, not because plaintext extracts omit infoboxes."""
    import httpx

    raw = httpx.get(wikipedia.API_URL, params={
        "action": "query", "prop": "extracts", "explaintext": 1,
        "titles": "Let's Make a Deal", "redirects": 1, "format": "json",
    }, headers={"User-Agent": wikipedia.USER_AGENT}, timeout=30)
    body = next(iter(raw.json()["query"]["pages"].values()))["extract"]

    assert "Raleigh" in body, "fact is in the prose, not an infobox"
    assert body.index("Raleigh") > wikipedia.ARTICLE_CHARS, "and past our cap"

    [fetched] = wikipedia.fetch("Let's Make a Deal", use_cache=False).results
    assert "Raleigh" not in fetched.extract
    assert fetched.extract.endswith(wikipedia.TRUNCATION_MARKER)


# --- addressing an article ---------------------------------------------------

def test_a_pageid_is_authoritative(monkeypatch):
    """Search results already carry pageids, and an id cannot be mistyped or
    mis-capitalised. When the model has one, it is strictly better than a title."""
    seen = {}
    def _full(title=None, pageid=None, timeout=20.0):
        seen.update(title=title, pageid=pageid)
        return "Resolved", "Body.", 42
    monkeypatch.setattr(wikipedia, "_fetch_full", _full)
    wikipedia.fetch(title="wrong title", pageid=42, use_cache=False)
    assert seen["pageid"] == 42


def test_a_lowercase_title_is_retried_capitalised(monkeypatch):
    """The measured failure. MediaWiki capitalises only the first letter, so
    'home alone 2: lost in new york' 404s while the title-cased form resolves -
    and every question in the random sets is lowercase, so a model echoing the
    question's casing hits this."""
    tried = []
    def _full(title=None, pageid=None, timeout=20.0):
        tried.append(title)
        if title != "Home Alone 2: Lost In New York":
            return None, "", None
        return "Home Alone 2: Lost in New York", "Body.", 1
    monkeypatch.setattr(wikipedia, "_fetch_full", _full)
    response = wikipedia.fetch("home alone 2: lost in new york", use_cache=False)
    assert response.error is None
    assert len(tried) == 2      # tried verbatim first, then title-cased


def test_a_genuinely_wrong_title_names_candidates_instead_of_substituting(monkeypatch):
    """It must not quietly fetch a different article. Naming near matches keeps
    the model in control and keeps the miss visible in the trace - a silent
    substitution is the failure class this whole project keeps guarding."""
    monkeypatch.setattr(wikipedia, "_fetch_full",
                        lambda title=None, pageid=None, timeout=20.0: (None, "", None))
    monkeypatch.setattr(wikipedia, "_fetch", lambda q, k, t: [
        wikipedia.Article("Duncan's Toy Chest", "u", "x", 7)])
    response = wikipedia.fetch("Duncans Toy Chest", use_cache=False)
    assert response.error
    assert "Duncan's Toy Chest" in response.render()
    assert response.results == []          # nothing substituted


def test_a_failed_fetch_is_counted(monkeypatch):
    """Its own signal. If the agent burns turns on titles that do not exist,
    that is a distinct problem from not fetching at all."""
    from conftest import Response, StubClient, text, tool_use
    from evals import graders
    from evals.cases import Case
    from wikiagent import agent

    monkeypatch.setattr(wikipedia, "_fetch_full",
                        lambda title=None, pageid=None, timeout=20.0: (None, "", None))
    monkeypatch.setattr(wikipedia, "_fetch", lambda q, k, t: [])
    trace = agent.ask("q", model="claude-haiku-4-5", prompt_version="v1",
                      use_cache=False, client=StubClient([
        Response([tool_use("Nope", id="t1", name="fetch_article")],
                 stop_reason="tool_use"),
        Response([text("Could not find it.")]),
    ]))
    row = graders.grade(Case(id="c", question="q", expected="e", dimensions=["d"]), trace)
    assert row["n_fetches"] == 1
    assert row["failed_fetches"] == 1


def test_search_results_show_pageids_only_when_fetch_exists():
    """v0 declared one tool and its rendered output must stay byte-identical,
    or the baseline on disk stops being reproducible."""
    response = wikipedia.SearchResponse(
        query="q", results=[wikipedia.Article("T", "u", "extract", 99)], top_k=1)
    assert "99" not in response.render()
    assert "99" in response.render(show_ids=True)
