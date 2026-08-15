"""Deterministic graders — exact signals, no LLM, no verdict.

Two design rules, both load-bearing:

1. **Signals, not verdicts.** Nothing here decides pass/fail or assigns a funnel
   stage. Staging happens in Phase 5 analysis over the emitted signals, so a
   failure mode we didn't anticipate means relabelling, not rewriting.

2. **`None` is not `False`.** A case with no gold article must not count as a
   retrieval miss — that would inflate the recall denominator. Absent signals
   are `None` and get excluded from their aggregate.
"""

from __future__ import annotations

import re

from wikiagent.trace import Trace

from .cases import Case


def _norm(title: str) -> str:
    return " ".join(title.split()).casefold()


def _find_cited_titles(answer: str, candidates: list[str]) -> list[str]:
    """Which retrieved article titles the agent names in its prose.

    Deliberately matches only against titles that actually came back, so this
    can never invent a citation the agent didn't make. Whole-word matching
    avoids 'Penicillin' matching inside 'History of penicillin'.
    """
    if not answer:
        return []
    found = []
    for title in candidates:
        if re.search(rf"\b{re.escape(title)}\b", answer, flags=re.IGNORECASE):
            found.append(title)
    return found


# NOTE: there is deliberately no `fabricated_citation` signal here.
#
# Detecting an invented citation means deciding whether a phrase in prose refers
# to a real article, and that is a semantic judgement. Two attempts at a
# deterministic version both misfired on real output: title extraction captured
# "The Marie Curie" and flagged an honest answer, and the looser "claims a
# source but names none of the retrieved titles" rule flagged the demo's
# correct penicillin answer, which paraphrased "Discovery of penicillin" as
# "articles on penicillin discovery".
#
# A false positive here is worse than a miss — it sends error analysis chasing
# a bug that doesn't exist. So fabrication belongs to the judge's faithfulness
# dimension, and this layer emits only what it can compute exactly.


def grade(case: Case, trace: Trace) -> dict:
    """Emit every deterministic signal for one run."""
    shown = trace.shown_titles
    fetched = trace.retrieved_titles

    if case.has_gold:
        gold = {_norm(g) for g in case.gold_articles}
        gold_shown = any(_norm(t) in gold for t in shown)
        # Fetched-but-not-shown separates "search can't find it" (fix the query
        # guidance) from "top_k was too small" (raise top_k) — different fixes.
        gold_fetched = any(_norm(t) in gold for t in fetched)
    else:
        gold_shown = gold_fetched = None

    cited = _find_cited_titles(trace.answer, shown)
    usage = trace.usage
    return {
        "case_id": case.id,
        "dimensions": case.dimensions,
        # query formulation
        "searched": trace.searched,
        "n_searches": trace.n_searches,
        "queries": trace.queries,
        # retrieval
        "gold_shown": gold_shown,
        "gold_fetched": gold_fetched,
        "shown_titles": shown,
        "retrieved_titles": fetched,
        # citation integrity — exact matches only; fabrication is the judge's job
        "cited_titles": cited,
        "cites_any_retrieved": bool(cited),
        # health and cost
        "n_turns": trace.n_turns,
        "cache_hits": trace.cache_hits,
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "latency_s": round(trace.latency_s, 3),
        "error": trace.error,
        "answer": trace.answer,
    }
