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
import unicodedata

from wikiagent.trace import Trace

from .cases import Case


def _norm(title: str) -> str:
    return " ".join(title.split()).casefold()


def _normalise(text: str) -> str:
    """Fold the differences that are the matcher's problem, not the agent's.

    Three real ones, each found by measuring rather than by guessing:

    * thousands separators — "2,679" in an article, "2679" in an answer;
    * non-breaking spaces — Natural Questions writes dates as
      `June\xa09,\xa02017`, which never matches a plainly typed date;
    * diacritics — Wikipedia writes `Marin Čilić` and an answer may write
      `Marin Cilic`. Both are the same name, and scoring one as a miss would
      systematically penalise every non-English name in the set.
    """
    text = " ".join((text or "").split())  # folds \xa0 and friends
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"(?<=\d),(?=\d)", "", text).casefold()


def matches(spec: list[list[str]], text: str) -> tuple[bool | None, float | None]:
    """Score an AND-of-ORs spec against text.

    Returns `(satisfied, fraction)`. The fraction is the completeness signal —
    a partial list presented as a complete one is invisible to the boolean.

    An empty spec returns `(None, None)`: unscorable, never a free pass.
    Counting it as satisfied would inflate correctness with cases that were
    never checked.
    """
    if not spec:
        return None, None
    hay = _normalise(text or "")
    hits = 0
    for group in spec:
        for option in group:
            needle = _normalise(option)
            # Word boundaries, or "no" matches inside "Nobel" and every
            # negative-answer case scores itself correct.
            if re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", hay):
                hits += 1
                break
    return hits == len(spec), hits / len(spec)


def _find_cited_titles(answer: str, candidates: list[str]) -> list[str]:
    """Which retrieved article titles the agent names in its prose.

    Deliberately matches only against titles that actually came back, so this
    can never invent a citation the agent didn't make. Whole-word matching
    avoids 'Penicillin' matching inside 'History of penicillin'.
    """
    if not answer:
        return []

    # Spans first, because a short title matches *inside* a longer one:
    # "\bPenicillin\b" is satisfied by "History of penicillin". Comparing
    # spans keeps "Penicillin and History of penicillin" (two real citations)
    # while dropping the phantom in "History of penicillin says..." - a title
    # test alone gets one of those two cases wrong whichever way it is written.
    spans = {
        title: [
            m.span()
            for m in re.finditer(rf"\b{re.escape(title)}\b", answer, flags=re.IGNORECASE)
        ]
        for title in candidates
    }
    found = []
    for title, occurrences in spans.items():
        if not occurrences:
            continue
        longer = [
            span
            for other, other_spans in spans.items()
            if other != title and title.lower() in other.lower()
            for span in other_spans
        ]
        if all(
            any(big[0] <= mine[0] and mine[1] <= big[1] for big in longer)
            for mine in occurrences
        ) and longer:
            continue
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

    # Correctness, deterministically, for cases with a checkable answer.
    answer_match, answer_completeness = matches(case.answer_contains, trace.answer)

    # Retrieval quality: did the text that came back carry the evidence?
    # Scored per tool call rather than over one concatenated blob, so we learn
    # *which* search found it and how many were spent getting there. Over 22K
    # characters of concatenated results, a short string also matches by
    # accident far too easily.
    calls = [c for turn in trace.turns for c in turn.tool_calls]
    evidence_match, evidence_at, evidence_in = None, None, []
    if case.evidence_contains:
        # Accumulated ACROSS calls, not within one. A multi-hop question
        # gathers its evidence in separate searches by design - "which is
        # older, Bologna or Oxford" searches each university once - so
        # requiring every requirement in a single call marks a perfect
        # retrieval as a miss and blames it on grounding.
        outstanding = list(case.evidence_contains)
        evidence_match = False
        for i, call in enumerate(calls):
            outstanding = [g for g in outstanding if not matches([g], call.rendered)[0]]
            if not outstanding:
                # The search at which the evidence became complete.
                evidence_match, evidence_at = True, i
                evidence_in = call.shown_titles
                break

    return {
        "case_id": case.id,
        "dimensions": case.dimensions,
        # query formulation
        "searched": trace.searched,
        "n_searches": trace.n_searches,
        "queries": trace.queries,
        # correctness and retrieval quality — the two exact signals. Crossing
        # them is what separates "never had the evidence" from "had it and
        # didn't use it" from "answered from memory", but that cross-tab is
        # analysis, not a grader's job.
        "answer_match": answer_match,
        "answer_completeness": answer_completeness,
        "evidence_match": evidence_match,
        "evidence_found_at_search": evidence_at,
        "evidence_found_in": evidence_in,
        # retrieval — per search, because a flattened title list across five
        # searches can't say which query produced what.
        "searches": [
            {"query": c.query, "shown": c.shown_titles,
             "beyond_top_k": c.titles[len(c.shown_titles):]}
            for c in calls
        ],
        # Weak article-level fallback, kept only for cases where no string
        # spec can express the answer (aggregation over tables). Not the
        # retrieval metric any more; `evidence_match` is.
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
