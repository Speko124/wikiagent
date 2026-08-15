"""Eval case loading and validation.

A malformed case set must fail loudly at load time. Discovering at scoring time
that a case had no `expected`, or that two cases share an id, means the sweep
already burned its budget on data that can't be interpreted.
"""

from __future__ import annotations

import json

import pytest

from evals import cases


def write(tmp_path, rows, name="cases.jsonl"):
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(r) for r in rows))
    return p


MINIMAL = {"id": "c1", "question": "Who?", "expected": "Someone", "dimensions": ["factual"]}


def test_loads_a_minimal_case(tmp_path):
    [c] = cases.load(write(tmp_path, [MINIMAL]))
    assert c.id == "c1"
    assert c.question == "Who?"
    assert c.expected == "Someone"
    assert c.dimensions == ["factual"]
    assert c.gold_articles == []


def test_gold_articles_are_optional(tmp_path):
    """Unanswerable and false-premise cases have none by definition."""
    row = {**MINIMAL, "id": "c2"}
    row.pop("gold_articles", None)
    [c] = cases.load(write(tmp_path, [row]))
    assert c.gold_articles == []
    assert c.has_gold is False


def test_gold_articles_are_kept_when_present(tmp_path):
    row = {**MINIMAL, "gold_articles": ["Marie Curie", "Pierre Curie"]}
    [c] = cases.load(write(tmp_path, [row]))
    assert c.gold_articles == ["Marie Curie", "Pierre Curie"]
    assert c.has_gold is True


def test_blank_lines_are_ignored(tmp_path):
    p = tmp_path / "c.jsonl"
    p.write_text(json.dumps(MINIMAL) + "\n\n   \n")
    assert len(cases.load(p)) == 1


def test_duplicate_ids_are_rejected(tmp_path):
    """Ids key the results; duplicates would silently overwrite each other."""
    with pytest.raises(ValueError, match="[Dd]uplicate"):
        cases.load(write(tmp_path, [MINIMAL, {**MINIMAL, "question": "Other?"}]))


@pytest.mark.parametrize("missing", ["id", "question", "expected", "dimensions"])
def test_missing_required_fields_are_rejected(tmp_path, missing):
    row = {k: v for k, v in MINIMAL.items() if k != missing}
    with pytest.raises(ValueError, match=missing):
        cases.load(write(tmp_path, [row]))


def test_error_names_the_offending_line(tmp_path):
    bad = {**MINIMAL, "id": "c2"}
    bad.pop("expected")
    with pytest.raises(ValueError, match="line 2"):
        cases.load(write(tmp_path, [MINIMAL, bad]))


def test_malformed_json_names_the_line(tmp_path):
    p = tmp_path / "c.jsonl"
    p.write_text(json.dumps(MINIMAL) + "\n{not json}\n")
    with pytest.raises(ValueError, match="line 2"):
        cases.load(p)


def test_dimensions_must_be_a_list_of_strings(tmp_path):
    with pytest.raises(ValueError, match="dimensions"):
        cases.load(write(tmp_path, [{**MINIMAL, "dimensions": "factual"}]))


def test_loads_a_whole_directory(tmp_path):
    write(tmp_path, [MINIMAL], "a.jsonl")
    write(tmp_path, [{**MINIMAL, "id": "c2"}], "b.jsonl")
    assert {c.id for c in cases.load(tmp_path)} == {"c1", "c2"}


def test_duplicate_ids_across_files_are_rejected(tmp_path):
    write(tmp_path, [MINIMAL], "a.jsonl")
    write(tmp_path, [MINIMAL], "b.jsonl")
    with pytest.raises(ValueError, match="[Dd]uplicate"):
        cases.load(tmp_path)
