"""The committed eval set.

Two sets with opposite purposes, and the tests differ accordingly:

* `core.jsonl` — hand-written, one case per failure mode we chose to test.
  Guarded for structure and for the polarity pairs that only mean something
  together.
* `explore.jsonl` — a frozen random draw of real user questions. Guarded for
  being *unedited*. Its value comes entirely from nobody having curated it, and
  that property is invisible in a diff review months later.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evals import cases as cases_mod

CASES_DIR = Path(__file__).resolve().parent.parent / "evals" / "cases"
CORE = CASES_DIR / "core.jsonl"
EXPLORE = CASES_DIR / "explore.jsonl"


@pytest.fixture(scope="module")
def core():
    return cases_mod.load(CORE)


@pytest.fixture(scope="module")
def explore():
    return cases_mod.load(EXPLORE)


def test_the_whole_directory_loads_without_id_collisions():
    """Loading the directory is what a sweep does; a collision across files
    would silently drop a case."""
    assert len(cases_mod.load(CASES_DIR)) == len(cases_mod.load(CORE)) + len(
        cases_mod.load(EXPLORE)
    )


# --- core -------------------------------------------------------------------

def test_core_covers_one_case_per_mode(core):
    modes = {d for c in core for d in c.dimensions}
    expected = {
        "factual", "single-hop", "multi-hop", "bridge", "deep-fact",
        "abstention", "unanswerable", "false-premise", "ambiguous-entity",
        "must-search", "negative-existence", "query-formulation", "obscure",
        "no-search-needed", "completeness", "list",
    }
    assert modes == expected


def test_core_keeps_both_halves_of_the_tool_use_polarity(core):
    """`must-search` and `no-search-needed` only mean something as a pair: one
    fails if the agent trusts its memory, the other if it searches reflexively.
    Dropping either leaves a prompt mis-tuned in that direction undetected."""
    dims = [d for c in core for d in c.dimensions]
    assert "must-search" in dims
    assert "no-search-needed" in dims


def test_core_cases_that_should_have_a_gold_article_have_one(core):
    """Retrieval recall is only computable where a gold article exists. These
    are the cases whose retrieval we intend to score."""
    needs_gold = {"factual", "multi-hop", "deep-fact", "false-premise",
                  "negative-existence", "query-formulation", "completeness"}
    for case in core:
        if needs_gold & set(case.dimensions):
            assert case.gold_articles, f"{case.id} needs a gold article"


def test_cases_without_a_gold_article_are_the_ones_that_cannot_have_one(core):
    """Not an oversight — unanswerable and no-search cases have no gold article
    by definition, and `gold_shown` is None for them rather than False."""
    for case in core:
        if not case.gold_articles:
            assert {"unanswerable", "no-search-needed"} & set(case.dimensions)


def test_every_core_case_records_why_it_exists(core):
    """A case whose purpose isn't written down becomes uninterpretable the
    moment it fails."""
    for case in core:
        assert case.notes.strip(), f"{case.id} has no notes"


# --- explore ----------------------------------------------------------------

# The frozen draw: seed 20260816 over nq_open/train, every drawn row kept.
# This digest is the freeze. It fails if a question is reworded, a case is
# dropped for being awkward, or a "better" one is swapped in — each of which
# would quietly turn a random sample back into a curated one.
EXPLORE_DIGEST = "d2472b9571eb7f34"


def test_the_random_sample_is_frozen():
    actual = hashlib.sha256(EXPLORE.read_bytes()).hexdigest()[:16]
    assert actual == EXPLORE_DIGEST, (
        "explore.jsonl changed. This set's only value is that nobody curated "
        "it. Re-draw with a new seed and record it, or restore the file."
    )


def test_explore_is_not_pre_categorised(explore):
    """Tagging these by failure mode now would impose the taxonomy the read
    pass is supposed to discover."""
    for case in explore:
        assert case.dimensions == ["explore"]


def test_explore_carries_no_gold_articles(explore):
    """Deliberate. Choosing the 'right' article is the judgement the failure
    analysis should make, not an input to it."""
    for case in explore:
        assert case.gold_articles == []


def test_provenance_matches_the_sample(explore):
    p = json.loads((CASES_DIR / "explore.provenance.json").read_text())
    assert p["seed"] == 20260816
    assert len(p["row_indices"]) == len(explore) == p["n"]
    assert len(set(p["row_indices"])) == len(p["row_indices"])
