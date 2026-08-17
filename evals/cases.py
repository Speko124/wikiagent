"""Eval case loading.

Validation is strict and happens at load time. A sweep is 120 agent calls; the
worst outcome is spending all of them and only then discovering a case was
malformed, or that two cases shared an id and silently overwrote each other.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED = ("id", "question", "expected", "dimensions")

# Ids name trace files, so anything path-ish has to be rejected here rather
# than sanitised later — sanitising two different ids can collide silently.
ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


ANSWER_KINDS = ("extractive", "derived", "none")


@dataclass
class Case:
    id: str
    question: str
    expected: str
    dimensions: list[str]

    # Checkable answer, as an AND of ORs: [["Italian", "from Italy"]] is one
    # requirement with two acceptable phrasings; [["Germany"], ["France"]] is
    # two requirements. One shape covers paraphrase tolerance and completeness.
    answer_contains: list[list[str]] = field(default_factory=list)

    # What retrieval had to surface, which is NOT always the answer. For a
    # derived answer ("which is older, Bologna or Oxford?") the evidence is the
    # two founding dates; the answer appears in no article. Keeping them apart
    # is what stops a synthesis question being blamed on retrieval.
    evidence_contains: list[list[str]] = field(default_factory=list)

    # extractive: answer is a span that should appear in some article.
    # derived:    answer is computed from evidence (compare, count, date maths).
    # none:       no answer exists to check (unanswerable, no-search-needed).
    answer_kind: str = "extractive"

    # Demoted from "gold" to a non-exclusive hint. Facts are usually carried by
    # several articles, and an answer corroborated by three is stronger, not
    # differently sourced — a metric keyed to one predicted title can't say so.
    gold_articles: list[str] = field(default_factory=list)
    notes: str = ""

    @property
    def has_gold(self) -> bool:
        return bool(self.gold_articles)


def _parse(raw: dict, where: str) -> Case:
    for key in REQUIRED:
        if key not in raw or raw[key] in (None, "", []):
            raise ValueError(f"{where}: missing required field {key!r}")
    if not ID_PATTERN.match(str(raw["id"])):
        raise ValueError(
            f"{where}: id {raw['id']!r} must contain only letters, digits, "
            "'.', '_' or '-' — ids are used as filenames"
        )
    if not isinstance(raw["dimensions"], list) or not all(
        isinstance(d, str) for d in raw["dimensions"]
    ):
        raise ValueError(f"{where}: 'dimensions' must be a list of strings")
    gold = raw.get("gold_articles") or []
    if not isinstance(gold, list):
        raise ValueError(f"{where}: 'gold_articles' must be a list")

    kind = raw.get("answer_kind", "extractive")
    if kind not in ANSWER_KINDS:
        raise ValueError(
            f"{where}: 'answer_kind' must be one of {', '.join(ANSWER_KINDS)}"
        )

    specs = {}
    for key in ("answer_contains", "evidence_contains"):
        spec = raw.get(key) or []
        # ["Italian"] instead of [["Italian"]] would silently become seven
        # single-character requirements and score everything as a miss.
        if not isinstance(spec, list) or not all(
            isinstance(group, list) and group and all(isinstance(s, str) for s in group)
            for group in spec
        ):
            raise ValueError(
                f"{where}: {key!r} must be a list of non-empty lists of strings, "
                'e.g. [["Italian", "from Italy"]]'
            )
        specs[key] = [list(group) for group in spec]

    return Case(
        id=str(raw["id"]),
        question=raw["question"],
        expected=raw["expected"],
        dimensions=list(raw["dimensions"]),
        answer_kind=kind,
        gold_articles=[str(g) for g in gold],
        notes=raw.get("notes", ""),
        **specs,
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
