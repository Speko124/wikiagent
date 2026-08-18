"""MediaWiki API wrapper with an on-disk cache.

The cache is not an optimization. Live Wikipedia changes underneath repeated
eval runs, so without it a score delta can't be attributed to a prompt change.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx

API_URL = "https://en.wikipedia.org/w/api.php"
# MediaWiki's User-Agent policy asks for a way to contact the operator. A
# project URL satisfies it without publishing a personal address.
USER_AGENT = "wikiagent/0.1 (https://github.com/Speko124/wikiagent)"

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"

# How much of each article intro the model sees. Long enough to answer most
# questions, short enough to keep three results affordable.
EXTRACT_CHARS = 1500

# Appended when an intro is cut short. Named because the tool description tells
# the model what it means — without that, "the article doesn't say" and "the
# text stopped here" look identical, and the model either abstains wrongly or
# fills the gap from memory.
TRUNCATION_MARKER = "[...]"

# How much of a fetched article the model sees. Far larger than a search
# result and far smaller than the longest articles: unbounded would blow the
# context window on a single call and make cost per run unpredictable.
ARTICLE_CHARS = 8_000

# How many results the model sees. The one knob; `--top-k` on the CLI.
DEFAULT_TOP_K = 3

# We always fetch at least this many, however few we show. The surplus costs
# nothing — it's cached and never rendered into the prompt — but it lets us ask
# "would showing more have retrieved the gold article?" from traces we already
# have, with zero extra agent calls, so raising top_k becomes evidence-backed
# rather than a guess.
#
# Deliberately not a parameter: it's the width of a diagnostic margin, not a
# behaviour anyone should tune. Keeping it fixed also keeps the cache key
# stable, so changing top_k reuses cached results instead of refetching.
OVERFETCH = 5


def _fetch_count(top_k: int) -> int:
    return max(OVERFETCH, top_k)


@dataclass
class Article:
    title: str
    url: str
    extract: str
    pageid: int


@dataclass
class SearchResponse:
    """One `search_wikipedia` call and everything it produced."""

    query: str
    results: list[Article] = field(default_factory=list)
    top_k: int = DEFAULT_TOP_K
    cache_hit: bool = False
    error: str | None = None
    latency_s: float = 0.0

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "results": [asdict(a) for a in self.results],
            "top_k": self.top_k,
            "cache_hit": self.cache_hit,
            "error": self.error,
            "latency_s": round(self.latency_s, 3),
        }

    @property
    def shown(self) -> list[Article]:
        """The results the model sees. Anything past these was fetched for
        offline analysis only."""
        return self.results[: self.top_k]

    def render(self, show_ids: bool = False) -> str:
        """The exact string the model sees as the tool result.

        `show_ids` is off by default so `v0`'s rendered output stays
        byte-identical now that a second tool exists - the V0 results on disk
        have to stay reproducible.
        """
        if self.error:
            return f"Search failed: {self.error}"
        if not self.results:
            return (
                f'No Wikipedia articles matched "{self.query}". '
                "Try different or broader search terms."
            )
        if self.top_k == 1 and self.results[0].pageid == -1:
            # A fetched article: one title, full text, no result numbering.
            article = self.results[0]
            return f"{article.title}\n{article.extract}"
        blocks = []
        for i, a in enumerate(self.shown, 1):
            label = f"{a.title} (id {a.pageid})" if show_ids else a.title
            blocks.append(f"[{i}] {label}\n{a.extract}")
        return "\n\n".join(blocks)


def _fetch_full(
    title: str | None = None, pageid: int | None = None, timeout: float = 20.0
) -> tuple[str | None, str, int | None]:
    """Full plaintext of one article. Returns `(resolved_title, text, pageid)`.

    The resolved title comes back separately because redirects mean the article
    you get may not be the title you asked for, and "did it open the right
    article" is only answerable against the one it actually got.
    """
    params = {
        "action": "query", "prop": "extracts|info", "explaintext": 1,
        "redirects": 1, "inprop": "url", "format": "json",
    }
    params["pageids" if pageid is not None else "titles"] = (
        str(pageid) if pageid is not None else title
    )
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True) as client:
        page = client.get(API_URL, params=params)
        page.raise_for_status()
        found = next(iter(page.json().get("query", {}).get("pages", {}).values()), {})
    if "missing" in found or not found.get("extract"):
        return None, "", None
    return found["title"], found["extract"], found.get("pageid", -1)


def fetch(
    title: str | None = None,
    pageid: int | None = None,
    cache_dir: Path | None = None,
    use_cache: bool = True,
    timeout: float = 20.0,
) -> SearchResponse:
    """Open one article and return its full text, bounded.

    Addressable by title or by pageid. The pageid wins when both are given: it
    comes straight from a search result and cannot be mistyped or
    mis-capitalised, which is the one title failure MediaWiki does not already
    absorb (it folds diacritics, redirects and a leading "The", but not
    internal capitalisation - "home alone 2: lost in new york" 404s).

    Returns a `SearchResponse` so the trace, the graders and the renderer all
    keep one shape: a fetch is a retrieval that returned exactly one article.
    """
    cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
    # `article:` prefix keeps this out of the search key space. Sharing one
    # would let a cached search for X serve a fetch of X and hand back the
    # intro when the body was asked for - the exact failure fetch exists to fix.
    ident = f"id:{pageid}" if pageid is not None else (title or "").strip().lower()
    key = hashlib.sha256(f"article:{ident}".encode()).hexdigest()[:32]
    path = cache_dir / f"{key}.json"
    label = title or f"pageid {pageid}"

    if use_cache and path.exists():
        raw = json.loads(path.read_text())
        return SearchResponse(
            query=label, results=[Article(**a) for a in raw["results"]],
            top_k=1, cache_hit=True, error=raw.get("error"),
        )

    started = time.monotonic()
    resolved = text = found_id = None
    error = None
    try:
        resolved, text, found_id = _fetch_full(title, pageid, timeout)
        if resolved is None and pageid is None and title:
            # MediaWiki capitalises only the first letter, so a lowercased
            # title misses. Retry title-cased before giving up - this is a
            # transcription artefact, not the model asking for the wrong thing.
            retry = " ".join(w[:1].upper() + w[1:] for w in title.split())
            if retry != title:
                resolved, text, found_id = _fetch_full(retry, None, timeout)
        if resolved is None:
            error = _no_article(title, pageid, timeout)
    except Exception as exc:  # network, HTTP, or malformed payload
        resolved, text, error = None, "", f"{type(exc).__name__}: {exc}"

    results = (
        [Article(title=resolved,
                 url=f"https://en.wikipedia.org/wiki/{resolved.replace(' ', '_')}",
                 extract=_truncate(text, ARTICLE_CHARS), pageid=found_id or -1)]
        if resolved else []
    )
    response = SearchResponse(query=label, results=results, top_k=1, error=error,
                              latency_s=time.monotonic() - started)
    # Errors are never cached - one blip must not poison this title forever.
    if use_cache and error is None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(response.to_dict(), indent=2))
    return response


def _no_article(title: str | None, pageid: int | None, timeout: float) -> str:
    """Report a miss with near matches, and never substitute one.

    Silently opening a different article than the one asked for is the failure
    class this project keeps guarding against; naming candidates instead keeps
    the model in control and leaves the miss visible in the trace.
    """
    if pageid is not None:
        return f"No Wikipedia article with pageid {pageid}."
    try:
        near = [a.title for a in _fetch(title or "", 3, timeout)]
    except Exception:  # a failed suggestion lookup must not mask the real miss
        near = []
    suggestion = (
        " Did you mean: " + ", ".join(repr(t) for t in near) + "?" if near
        else " Search for it first and copy the title exactly."
    )
    return f"No Wikipedia article titled {title!r}.{suggestion}"


def _cache_path(query: str, fetch_k: int, cache_dir: Path) -> Path:
    # Keyed on fetch_k, never top_k — so changing how many results the model
    # sees reuses the existing cache instead of invalidating all of it.
    key = hashlib.sha256(f"{fetch_k}:{query.strip().lower()}".encode()).hexdigest()[:32]
    return cache_dir / f"{key}.json"


def _truncate(text: str, limit: int = EXTRACT_CHARS) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    # Cut at the last sentence boundary we can find, so the model never sees a
    # fact severed mid-clause and treats the fragment as complete.
    cut = text[:limit]
    for stop in (". ", "! ", "? "):
        idx = cut.rfind(stop)
        if idx > limit * 0.6:
            return f"{cut[: idx + 1]} {TRUNCATION_MARKER}"
    return f"{cut.rsplit(' ', 1)[0]} {TRUNCATION_MARKER}"


def _fetch(query: str, fetch_k: int, timeout: float) -> list[Article]:
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True) as client:
        hits = client.get(
            API_URL,
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": fetch_k,
                "srnamespace": 0,
                "format": "json",
            },
        )
        hits.raise_for_status()
        titles = [r["title"] for r in hits.json().get("query", {}).get("search", [])]
        if not titles:
            return []

        # One batched call for all intros, rather than one per title.
        pages = client.get(
            API_URL,
            params={
                "action": "query",
                "prop": "extracts|info",
                "exintro": 1,
                "explaintext": 1,
                "titles": "|".join(titles),
                "redirects": 1,
                "inprop": "url",
                "format": "json",
            },
        )
        pages.raise_for_status()
        by_title = {}
        for page in pages.json().get("query", {}).get("pages", {}).values():
            if "missing" in page:
                continue
            by_title[page["title"]] = Article(
                title=page["title"],
                url=page.get("fullurl", ""),
                extract=_truncate(page.get("extract", "")),
                pageid=page.get("pageid", -1),
            )

    # Preserve search-result ranking; the extracts call returns arbitrary order.
    # Redirects mean a returned title may differ from the one we searched for,
    # so fall back to positional order for anything that didn't match by name.
    ordered = [by_title.pop(t) for t in titles if t in by_title]
    ordered.extend(by_title.values())
    return ordered


def search(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    cache_dir: Path | None = None,
    use_cache: bool = True,
    timeout: float = 20.0,
) -> SearchResponse:
    """Search Wikipedia. The response renders `top_k` results to the model and
    keeps any surplus for offline analysis."""
    cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
    fetch_k = _fetch_count(top_k)
    path = _cache_path(query, fetch_k, cache_dir)

    if use_cache and path.exists():
        raw = json.loads(path.read_text())
        return SearchResponse(
            query=query,
            results=[Article(**a) for a in raw["results"]],
            top_k=top_k,
            cache_hit=True,
            error=raw.get("error"),
        )

    started = time.monotonic()
    try:
        results = _fetch(query, fetch_k, timeout)
        error = None
    except Exception as exc:  # network, HTTP, or malformed payload
        results, error = [], f"{type(exc).__name__}: {exc}"
    elapsed = time.monotonic() - started

    response = SearchResponse(
        query=query,
        results=results,
        top_k=top_k,
        cache_hit=False,
        error=error,
        latency_s=elapsed,
    )

    # Never cache a failure — a transient network blip would otherwise poison
    # every later run of the same query.
    if use_cache and error is None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(response.to_dict(), indent=2))

    return response
