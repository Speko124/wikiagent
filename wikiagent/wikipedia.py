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
USER_AGENT = "wikiagent/0.1 (Anthropic take-home; contact: speko124@gmail.com)"

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"

# How much of each article intro the model sees. Long enough to answer most
# questions, short enough to keep three results affordable.
EXTRACT_CHARS = 1500

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

    def render(self) -> str:
        """The exact string the model sees as the tool result."""
        if self.error:
            return f"Search failed: {self.error}"
        if not self.results:
            return (
                f'No Wikipedia articles matched "{self.query}". '
                "Try different or broader search terms."
            )
        blocks = []
        for i, a in enumerate(self.shown, 1):
            blocks.append(f"[{i}] {a.title}\n{a.extract}")
        return "\n\n".join(blocks)


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
            return cut[: idx + 1] + " [...]"
    return cut.rsplit(" ", 1)[0] + " [...]"


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
