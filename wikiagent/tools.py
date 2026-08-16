"""The tool schema Claude sees, and the dispatch that backs it.

The description is prompt engineering, not plumbing — it's what tells the model
when to reach for the tool and how to phrase a query. It therefore lives in
`prompts.py` under the same version as the system prompt, so one version pins
everything the model reads.
"""

from __future__ import annotations

from pathlib import Path

from . import prompts, wikipedia

_NUMBER_WORDS = {1: "single", 2: "two", 3: "three", 4: "four", 5: "five"}


def schema(
    top_k: int = wikipedia.DEFAULT_TOP_K,
    version: str = prompts.DEFAULT_VERSION,
) -> dict:
    """Build the tool definition.

    Built rather than declared as a constant because the description has to
    state how many results come back, and that count is a tunable lever.
    """
    description = prompts.get(version).tool_description
    return {
        "name": "search_wikipedia",
        "description": description.format(n=_NUMBER_WORDS.get(top_k, str(top_k))),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "What to search for, e.g. 'Marie Curie' or "
                        "'Nobel Prize in Chemistry 1911'."
                    ),
                }
            },
            "required": ["query"],
        },
    }


def dispatch(
    name: str,
    tool_input: dict,
    top_k: int = wikipedia.DEFAULT_TOP_K,
    cache_dir: Path | None = None,
    use_cache: bool = True,
) -> wikipedia.SearchResponse:
    """Execute a tool call.

    Returns the full response object rather than the rendered string, so the
    trace keeps every result — including the ones beyond top_k that the model
    never saw.
    """
    if name != "search_wikipedia":
        return wikipedia.SearchResponse(
            query="", top_k=top_k, error=f"Unknown tool: {name}"
        )
    query = (tool_input or {}).get("query", "")
    if not isinstance(query, str) or not query.strip():
        return wikipedia.SearchResponse(
            query="", top_k=top_k, error="No query provided."
        )
    return wikipedia.search(
        query, top_k=top_k, cache_dir=cache_dir, use_cache=use_cache
    )
