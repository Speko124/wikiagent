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
HOLDOUT = CASES_DIR / "holdout.jsonl"


@pytest.fixture(scope="module")
def core():
    return cases_mod.load(CORE)


@pytest.fixture(scope="module")
def explore():
    return cases_mod.load(EXPLORE)


def test_the_whole_directory_loads_without_id_collisions():
    """Loading the directory is what a sweep does; a collision across files
    would silently drop a case."""
    parts = sum(len(cases_mod.load(f)) for f in (CORE, EXPLORE, HOLDOUT))
    assert len(cases_mod.load(CASES_DIR)) == parts


# --- holdout ----------------------------------------------------------------

HOLDOUT_DIGEST = "79a2c39d8baa021d"


def questions_digest(path):
    """Digest the ids and questions only.

    The freeze protects "nobody curated the *questions*" — that is what makes
    a random sample worth having. Scoring metadata (accepted phrasings, notes,
    reference articles) is authored by hand on purpose and has to be editable,
    so hashing the whole file would make the guarantee unusable and it would
    get switched off.
    """
    rows = [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]
    blob = "\n".join(f"{r['id']}\t{r['question']}" for r in rows)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def test_the_holdout_questions_are_frozen():
    assert questions_digest(HOLDOUT) == HOLDOUT_DIGEST, (
        "holdout questions changed. A holdout edited after seeing results is "
        "not a holdout."
    )


def test_the_holdout_is_scorable_without_a_judge(explore):
    """Authored before any holdout run existed, which is what makes it a clean
    test of the matcher — unlike the curated specs, written after reading the
    baseline answers."""
    for case in cases_mod.load(HOLDOUT):
        assert case.answer_contains, f"{case.id} has no accepted phrasings"
        assert case.evidence_contains, f"{case.id} has no evidence spec"


def test_the_holdout_shares_no_rows_with_the_tuning_set():
    """The whole point. A holdout overlapping the set we tuned against would
    report generalisation it hasn't earned, and the overlap is invisible once
    the questions are separated from their row indices."""
    explore = json.loads((CASES_DIR / "explore.provenance.json").read_text())
    holdout = json.loads((CASES_DIR / "holdout.provenance.json").read_text())
    assert set(explore["row_indices"]).isdisjoint(holdout["row_indices"])
    assert holdout["seed"] != explore["seed"]
    assert holdout["excluded_rows"] == len(explore["row_indices"])


# --- core -------------------------------------------------------------------

def test_core_covers_every_mode_the_read_pass_found(core):
    """A superset check, not equality: adding a mode should not require
    editing a test, but silently *losing* one must fail."""
    modes = {d for c in core for d in c.dimensions}
    required = {
        # anchors for behaviour that works today
        "factual", "must-search", "no-search-needed", "multi-hop", "bridge",
        "ambiguous-entity", "query-formulation", "false-premise",
        "negative-existence", "completeness", "unanswerable",
        # the dominant failure mode and its variants
        "body-fact", "infobox-fact", "aggregation",
        # modes the read pass surfaced
        "memory-seeded-query", "persistence", "no-article",
        "comparison", "query-reformulation", "false-premise-control",
    }
    assert required <= modes, f"missing modes: {sorted(required - modes)}"


def test_the_false_premise_case_has_its_matched_control(core):
    """FalseQA's design. Without the control, an agent that rejects any
    odd-sounding premise scores as a success on the false-premise case."""
    dims = {d for c in core for d in c.dimensions}
    assert ("false-premise" in dims) == ("false-premise-control" in dims)


def test_extractive_cases_can_actually_be_scored(core):
    """`extractive` claims the answer is a span in some article. A case
    claiming it with no strings to check is mislabelled, and would sit in the
    scorable denominator contributing nothing."""
    for case in core:
        if case.answer_kind == "extractive":
            assert case.answer_contains, f"{case.id} is extractive but unscorable"
            assert case.evidence_contains, f"{case.id} has no evidence spec"


def test_unanswerable_cases_have_nothing_to_match(core):
    """`none` means no answer exists. A spec here would score an abstention
    against a string it should never contain."""
    for case in core:
        if case.answer_kind == "none":
            assert not case.answer_contains
            assert not case.evidence_contains


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
    needs_gold = {"factual", "multi-hop", "false-premise", "body-fact",
                  "negative-existence", "query-formulation", "completeness"}
    for case in core:
        if needs_gold & set(case.dimensions):
            assert case.gold_articles, f"{case.id} needs a gold article"


def test_cases_without_a_gold_article_are_the_ones_that_cannot_have_one(core):
    """Not an oversight — unanswerable and no-search cases have no gold article
    by definition, and `gold_shown` is None for them rather than False."""
    for case in core:
        if not case.gold_articles:
            assert {"unanswerable", "no-search-needed", "no-article"} & set(
                case.dimensions
            )


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
EXPLORE_DIGEST = "30458d78c5e006ef"


def test_the_random_sample_is_frozen():
    actual = questions_digest(EXPLORE)
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
