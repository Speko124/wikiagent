"""The Trace: one record of everything a single run did.

This is the source of truth for both `--verbose` and the eval harness, so what
you see while debugging can't drift from what gets scored. It stores full raw
tool results, never summaries — that's what makes it possible to tell "the
right article came back but the intro didn't contain the fact" apart from "the
model ignored the evidence". Those two have opposite fixes.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolCall:
    query: str  # the search query, or the article title for a fetch
    raw: dict  # the full SearchResponse — every fetched result, not just shown
    rendered: str  # exactly what the model was shown
    top_k: int = 3  # how many of `raw` were rendered
    tool: str = "search_wikipedia"  # which tool produced this

    @property
    def titles(self) -> list[str]:
        """Every title fetched, including those beyond top_k."""
        return [r["title"] for r in self.raw.get("results", [])]

    @property
    def shown_titles(self) -> list[str]:
        """Only the titles the model actually saw."""
        return self.titles[: self.top_k]


@dataclass
class Turn:
    """One assistant response, plus whatever tools it asked for."""

    index: int
    thinking: str | None = None
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    latency_s: float = 0.0


@dataclass
class Trace:
    question: str
    model: str
    prompt_version: str
    effort: str | None = None
    tools_enabled: bool = True
    top_k: int = 3
    turns: list[Turn] = field(default_factory=list)
    answer: str = ""
    error: str | None = None
    latency_s: float = 0.0

    # --- derived views the eval harness reads -------------------------------

    @property
    def searched(self) -> bool:
        return bool(self.queries)

    @property
    def queries(self) -> list[str]:
        return [c.query for t in self.turns for c in t.tool_calls]

    def _titles(self, shown_only: bool) -> list[str]:
        seen: dict[str, None] = {}
        for turn in self.turns:
            for call in turn.tool_calls:
                for title in (call.shown_titles if shown_only else call.titles):
                    seen.setdefault(title, None)
        return list(seen)

    @property
    def shown_titles(self) -> list[str]:
        """Titles the model actually saw. This is the denominator for
        retrieval recall — the agent cannot use what it was never shown."""
        return self._titles(shown_only=True)

    @property
    def retrieved_titles(self) -> list[str]:
        """Every title fetched, including those past top_k the model never saw.

        The gap between this and `shown_titles` answers "would raising top_k
        have helped?" without spending a single extra agent call.
        """
        return self._titles(shown_only=False)

    @property
    def n_searches(self) -> int:
        return sum(
            1 for t in self.turns for c in t.tool_calls
            if c.tool == "search_wikipedia"
        )

    @property
    def n_fetches(self) -> int:
        """Full-article reads. Separate from searches because they answer
        different questions: whether the agent looked, and whether it looked
        *deeper* when the first look was not enough."""
        return sum(
            1 for t in self.turns for c in t.tool_calls if c.tool == "fetch_article"
        )

    @property
    def fetched_titles(self) -> list[str]:
        seen: dict[str, None] = {}
        for turn in self.turns:
            for call in turn.tool_calls:
                if call.tool == "fetch_article":
                    seen.setdefault(call.query, None)
        return list(seen)

    @property
    def escalated(self) -> bool:
        """Did a fetch follow a search, rather than replace it?

        Fetching after a search is the intended pattern - look, then look
        deeper. Fetching with no search first means the agent guessed a title
        from memory, which is the failure mode this tool could introduce.
        """
        order = [c.tool for t in self.turns for c in t.tool_calls]
        return "fetch_article" in order and order.index("search_wikipedia") < order.index(
            "fetch_article"
        ) if "search_wikipedia" in order and "fetch_article" in order else False

    @property
    def n_turns(self) -> int:
        return len(self.turns)

    @property
    def cache_hits(self) -> int:
        return sum(
            1
            for t in self.turns
            for c in t.tool_calls
            if c.raw.get("cache_hit")
        )

    @property
    def usage(self) -> dict[str, int]:
        return {
            "input_tokens": sum(t.input_tokens for t in self.turns),
            "output_tokens": sum(t.output_tokens for t in self.turns),
            "cache_read_tokens": sum(t.cache_read_tokens for t in self.turns),
        }

    # --- serialization ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "effort": self.effort,
            "tools_enabled": self.tools_enabled,
            "top_k": self.top_k,
            "answer": self.answer,
            "error": self.error,
            "latency_s": round(self.latency_s, 3),
            "summary": {
                "searched": self.searched,
                "n_searches": self.n_searches,
                "n_fetches": self.n_fetches,
                "fetched_titles": self.fetched_titles,
                "escalated": self.escalated,
                "n_turns": self.n_turns,
                "cache_hits": self.cache_hits,
                "queries": self.queries,
                "shown_titles": self.shown_titles,
                "retrieved_titles": self.retrieved_titles,
                "usage": self.usage,
            },
            "turns": [asdict(t) for t in self.turns],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Trace":
        """Rebuild a Trace from its JSON form.

        Exists so a grader fix can be applied to sweeps already paid for. The
        derived views (`shown_titles`, `n_searches`, usage) are all computed
        from the stored turns, so nothing has to be persisted twice.
        """
        trace = cls(
            question=data["question"],
            model=data["model"],
            prompt_version=data["prompt_version"],
            effort=data.get("effort"),
            tools_enabled=data.get("tools_enabled", True),
            top_k=data.get("top_k", 3),
            answer=data.get("answer", ""),
            error=data.get("error"),
            latency_s=data.get("latency_s", 0.0),
        )
        for raw_turn in data.get("turns", []):
            calls = [ToolCall(**c) for c in raw_turn.get("tool_calls", [])]
            trace.turns.append(Turn(**{**raw_turn, "tool_calls": calls}))
        return trace

    @classmethod
    def load(cls, path: str | Path) -> "Trace":
        return cls.from_dict(json.loads(Path(path).read_text()))

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path
