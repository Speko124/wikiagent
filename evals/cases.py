"""Eval case loading.

Validation is strict and happens at load time. A sweep is 120 agent calls; the
worst outcome is spending all of them and only then discovering a case was
malformed, or that two cases shared an id and silently overwrote each other.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED = ("id", "question", "expected", "dimensions")


@dataclass
class Case:
    id: str
    question: str
    expected: str
    dimensions: list[str]
    # Optional by necessity: unanswerable and false-premise cases have no gold
    # article. Retrieval recall is reported over only the subset that has them.
    gold_articles: list[str] = field(default_factory=list)
    notes: str = ""

    @property
    def has_gold(self) -> bool:
        return bool(self.gold_articles)


def _parse(raw: dict, where: str) -> Case:
    for key in REQUIRED:
        if key not in raw or raw[key] in (None, "", []):
            raise ValueError(f"{where}: missing required field {key!r}")
    if not isinstance(raw["dimensions"], list) or not all(
        isinstance(d, str) for d in raw["dimensions"]
    ):
        raise ValueError(f"{where}: 'dimensions' must be a list of strings")
    gold = raw.get("gold_articles") or []
    if not isinstance(gold, list):
        raise ValueError(f"{where}: 'gold_articles' must be a list")
    return Case(
        id=str(raw["id"]),
        question=raw["question"],
        expected=raw["expected"],
        dimensions=list(raw["dimensions"]),
        gold_articles=[str(g) for g in gold],
        notes=raw.get("notes", ""),
    )


def _load_file(path: Path) -> list[Case]:
    out = []
    for i, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        where = f"{path.name} line {i}"
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{where}: invalid JSON ({exc.msg})") from exc
        out.append(_parse(raw, where))
    return out


def load(path: str | Path) -> list[Case]:
    """Load cases from a .jsonl file or a directory of them."""
    path = Path(path)
    files = sorted(path.glob("*.jsonl")) if path.is_dir() else [path]

    cases: list[Case] = []
    seen: dict[str, str] = {}
    for f in files:
        for case in _load_file(f):
            if case.id in seen:
                raise ValueError(
                    f"Duplicate case id {case.id!r} in {f.name} "
                    f"(already defined in {seen[case.id]})"
                )
            seen[case.id] = f.name
            cases.append(case)
    return cases
