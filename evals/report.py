"""Cross-arm report: curated and holdout side by side, one file.

The two arms are reported **asymmetrically on purpose**.

The curated arm is reported case by case, because that is what error analysis
needs — which case failed, which query found the evidence, where the judge and
the matcher disagreed.

The holdout arm is reported as **aggregate values only**. No case ids, no
answers, no judge rationales. A named failing holdout case is a lead, and
following a lead is how a holdout quietly becomes training data — with nothing
downstream able to detect that it happened. Tests enforce the asymmetry rather
than trusting anyone to remember it.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

CONFIG_KEYS = ("model", "prompt_version", "top_k", "effort", "use_tools")


def _load(d: Path | None) -> tuple[list[dict], dict]:
    if d is None:
        return [], {}
    d = Path(d)
    rows = [
        json.loads(ln)
        for ln in (d / "results.jsonl").read_text().splitlines()
        if ln.strip()
    ]
    return rows, json.loads((d / "config.json").read_text())


def judged_correct(row: dict) -> bool | None:
    """Primary correctness: the judge's verdict, scored against the case.

    The deterministic matcher is a guardrail rather than the score. On the V0
    curated runs it produced three false passes — an accepted phrasing matching
    text that did not answer the question — each of them silent and confident.
    The judge flagged all three. Its failure mode is abstention, which is
    visible; the matcher's is a false pass, which is not.

    `declined` is scored against the case, and that is what finally closes the
    abstention gap: on a case with no answer to give, declining IS the correct
    answer. On any other case it is a failure to answer.
    """
    verdict = (row.get("judge") or {}).get("correctness", {}).get("verdict")
    if verdict in (None, "unclear"):
        return None          # excluded and surfaced, never silently a failure
    if verdict == "correct":
        return True
    if verdict == "declined":
        return row.get("answer_kind") == "none"
    return False


def _rate(hits: int, total: int) -> str:
    return f"{hits}/{total} ({hits / total:.0%})" if total else "n/a"


def _metrics(rows: list[dict]) -> dict:
    ok = [r for r in rows if not r.get("error")]
    judged_ok = [r for r in ok if judged_correct(r) is not None]
    scorable = [r for r in ok if r.get("answer_match") is not None]
    # Where the guardrail and the primary signal disagree, one of them is
    # wrong and a human should look. Both are reported; neither overrides.
    guardrail_clash = [
        r for r in ok
        if judged_correct(r) is not None and r.get("answer_match") is not None
        and judged_correct(r) != bool(r["answer_match"])
    ]
    with_ev = [r for r in ok if r.get("evidence_match") is not None]
    completeness = [
        r["answer_completeness"] for r in ok if r.get("answer_completeness") is not None
    ]
    solid, n_cases, buckets = pass_at_k(rows)
    judged = [
        r for r in ok
        if (r.get("judge") or {}).get("correctness", {}).get("verdict")
        in ("correct", "incorrect")
    ]
    # `unclear` is not a non-answer. "The judge would not commit and the matcher
    # was confident" is the highest-value cell in this cross-tab: it is what
    # flagged arpanet-first-message, where an accepted phrasing matched
    # unrelated text and certified two failures as passes. Dropping these from
    # the audit reported 0 disagreements while the audit was working.
    hedged = [
        r for r in ok
        if (r.get("judge") or {}).get("correctness", {}).get("verdict") == "unclear"
        and r.get("answer_match") is not None
    ]
    # Only rows the matcher actually scored can disagree with the judge.
    # `bool(None)` is False, so an unscorable abstention case would otherwise
    # read as "matcher said wrong, judge said right" on every single run - the
    # None-is-not-False rule, violated in the one place it was being reported.
    clashes = [
        r for r in judged
        if r.get("answer_match") is not None
        and (r["judge"]["correctness"]["verdict"] == "correct") != r["answer_match"]
    ]
    return {
        "runs": len(rows),
        "errors": len(rows) - len(ok),
        "correct": _rate(sum(1 for r in judged_ok if judged_correct(r)), len(judged_ok)),
        "correct_contains": _rate(
            sum(1 for r in scorable if r["answer_match"]), len(scorable)),
        "guardrail_clash": f"{len(guardrail_clash)}",
        "evidence_found": _rate(
            sum(1 for r in with_ev if r["evidence_match"]), len(with_ev)
        ),
        "completeness": f"{statistics.mean(completeness):.0%}" if completeness else "n/a",
        "pass_at_k": _rate(solid, n_cases),
        "buckets": " · ".join(f"{v} {k}" for k, v in buckets.items()),
        "searched": _rate(sum(1 for r in ok if r["searched"]), len(ok)),
        "mean_searches": f"{statistics.mean([r['n_searches'] for r in ok]):.1f}"
        if ok else "n/a",
        # Turns are the agent's own control loop. The mean says what a typical
        # run costs; the max says whether anything ran away, and a runaway is
        # invisible in an average over 54 runs.
        "turns": (f"{statistics.mean([r['n_turns'] for r in ok]):.1f} mean, "
                  f"{max(r['n_turns'] for r in ok)} max") if ok else "n/a",
        "fetch_rate": _rate(sum(1 for r in ok if r.get("n_fetches")), len(ok)),
        "mean_fetches": (f"{statistics.mean([r.get('n_fetches', 0) for r in ok]):.2f}"
                         if ok else "n/a"),
        "failed_fetches": str(sum(r.get("failed_fetches", 0) for r in ok)),
        # Distribution, not just the mean. One fetch is the intended
        # escalation and costs exactly one turn; two means the agent is lost,
        # and an average over 54 runs hides which of those is happening.
        "fetch_spread": " · ".join(
            f"{n}x{sum(1 for r in ok if r.get('n_fetches', 0) == n)}"
            for n in sorted({r.get("n_fetches", 0) for r in ok})
        ) or "n/a",
        "turns_by_fetch": " · ".join(
            f"{n} fetch: {statistics.mean([r['n_turns'] for r in ok if r.get('n_fetches', 0) == n]):.1f}t"
            for n in sorted({r.get("n_fetches", 0) for r in ok})
        ) or "n/a",
        "unescalated_fetches": str(sum(
            1 for r in ok if r.get("n_fetches") and not r.get("escalated"))),
        "corroboration": f"{statistics.mean([len(r['cited_titles']) for r in ok]):.1f}"
        if ok else "n/a",
        "answer_chars": f"{statistics.mean([len(r['answer']) for r in ok]):.0f}"
        if ok else "n/a",
        "output_tokens": f"{statistics.mean([r['output_tokens'] for r in ok]):.0f}"
        if ok else "n/a",
        "latency_s": f"{statistics.median([r['latency_s'] for r in ok]):.1f}"
        if ok else "n/a",
        "judge_clashes": f"{len(clashes)}/{len(judged)}" if judged else "n/a",
        "judge_hedged": f"{len(hedged)}",
        "_clashes": clashes,
        "_hedged": hedged,
        "_guardrail_clash": guardrail_clash,
        "_cross": _cross_tab(ok),
    }


def _cross_tab(rows: list[dict]) -> dict[str, int]:
    """Answer × evidence. Four cells, four different problems.

    The off-diagonals are the useful ones: an answer that is right while the
    evidence never came back was answered from memory, and evidence that came
    back and produced no answer is a synthesis failure, not a retrieval one.
    """
    cells = {"grounded": 0, "from memory": 0, "evidence unused": 0, "neither": 0}
    for r in rows:
        a, e = r.get("answer_match"), r.get("evidence_match")
        if a is None or e is None:
            continue
        cells[
            "grounded" if a and e
            else "from memory" if a and not e
            else "evidence unused" if e else "neither"
        ] += 1
    return cells


# Ordered upstream to downstream, so the table reads the way the failure
# propagates: a stage-2 miss guarantees everything below it fails, and seeing
# stage 1 at the top makes that ordering obvious rather than something the
# reader has to reconstruct.
FUNNEL_STAGES = (
    "1 query: did not search at all",
    "2 retrieval: the answer-bearing article never surfaced",
    "3 evidence: right article, fact not in the retrieved text",
    "4 synthesis: had the evidence, answered wrong",
    "5 grounding: answered from memory",
    "correct, grounded",
    "correct, evidence not checkable",
    "not scorable (abstention cases)",
)


def funnel(rows: list[dict]) -> dict[str, int]:
    """Attribute each run to a funnel stage, from exact signals only.

    Iteration 0 needed a human to read 31 traces to produce this. It is now
    three booleans, which is what makes it repeatable every sweep instead of
    once per phase.

    `gold_shown` earns its keep here and nowhere else: it is what separates
    "the right article never came back" (stage 2) from "it came back and the
    fact wasn't in the part we fetched" (stage 3) — the distinction the whole
    read pass turned on, and the two have completely different fixes.
    """
    out = dict.fromkeys(FUNNEL_STAGES, 0)
    for r in rows:
        if r.get("error"):
            continue
        answer, evidence = judged_correct(r), r.get("evidence_match")
        if answer is None:
            out["not scorable (abstention cases)"] += 1
        elif answer and evidence:
            out["correct, grounded"] += 1
        elif answer and evidence is None:
            # No evidence spec exists for this case - turing-nobel's evidence
            # is an absence. Unknown grounding, NOT ungrounded: calling it
            # "from memory" would invent a failure out of a missing check.
            out["correct, evidence not checkable"] += 1
        elif answer:
            out["5 grounding: answered from memory"] += 1
        elif evidence:
            out["4 synthesis: had the evidence, answered wrong"] += 1
        elif not r.get("searched"):
            out["1 query: did not search at all"] += 1
        elif r.get("gold_shown"):
            out["3 evidence: right article, fact not in the retrieved text"] += 1
        else:
            out["2 retrieval: the answer-bearing article never surfaced"] += 1
    return out


def pass_at_k(rows: list[dict]) -> tuple[int, int, dict[str, int]]:
    """pass^k: cases correct on *every* repeat, not runs correct on average.

    A per-run rate hides the shape. Two cases at 50% could be one case that
    always works and one that never does, or two that flip a coin - and those
    need completely different responses. pass^k collapses to the strict
    reading, and the buckets say which kind of failure each case is.
    """
    by_case: dict[str, list[bool]] = {}
    for r in rows:
        correct = judged_correct(r)
        if correct is not None and not r.get("error"):
            by_case.setdefault(r["case_id"], []).append(correct)
    buckets = {"solid (k/k)": 0, "flaky": 0, "systematic (0/k)": 0}
    for hits in by_case.values():
        buckets["solid (k/k)" if hits and all(hits)
                else "systematic (0/k)" if not any(hits)
                else "flaky"] += 1
    return buckets["solid (k/k)"], len(by_case), buckets


def _buckets(rows: list[dict]) -> list[tuple[str, int, int]]:
    by_case: dict[str, list[bool]] = {}
    for r in rows:
        correct = judged_correct(r)
        if correct is not None and not r.get("error"):
            by_case.setdefault(r["case_id"], []).append(correct)
    return sorted(
        ((c, sum(v), len(v)) for c, v in by_case.items()),
        key=lambda t: (t[1] / t[2], t[0]),
    )


def compare(curated_dir, holdout_dir=None) -> str:
    cur_rows, cur_cfg = _load(curated_dir)
    hld_rows, hld_cfg = _load(holdout_dir)
    cur, hld = _metrics(cur_rows), _metrics(hld_rows) if hld_rows else None

    out = [
        "# V0 baseline",
        "",
        f"`{cur_cfg.get('model')}` · prompt `{cur_cfg.get('prompt_version')}` · "
        f"top_k {cur_cfg.get('top_k')} · {cur_cfg.get('repeats')}x per case",
        "",
    ]

    if hld_cfg:
        differing = [k for k in CONFIG_KEYS if cur_cfg.get(k) != hld_cfg.get(k)]
        if differing:
            out += [
                f"> **The two arms differ in {', '.join(differing)}** — this is "
                "not a comparison. Re-run one arm to match before reading the "
                "numbers below.",
                "",
            ]

    rows_ = [
        ("**Correct** (judge, primary)", "correct"),
        ("Correct (contains, guardrail)", "correct_contains"),
        ("Guardrail disagrees with judge", "guardrail_clash"),
        ("**pass^k** (correct on every repeat)", "pass_at_k"),
        ("  of which", "buckets"),
        ("Evidence retrieved", "evidence_found"),
        ("Answer completeness (mean)", "completeness"),
        ("Searched at all", "searched"),
        ("Searches per run", "mean_searches"),
        ("Turns", "turns"),
        ("Runs that opened an article", "fetch_rate"),
        ("Fetches per run", "mean_fetches"),
        ("Fetches per run (spread)", "fetch_spread"),
        ("Turns by fetch count", "turns_by_fetch"),
        ("Failed fetches", "failed_fetches"),
        ("Fetches with no prior search", "unescalated_fetches"),
        ("Articles named per answer", "corroboration"),
        ("Answer length (chars)", "answer_chars"),
        ("Output tokens", "output_tokens"),
        ("Latency (median s)", "latency_s"),
        ("Judge/matcher disagreements", "judge_clashes"),
        ("Judge unclear, matcher confident", "judge_hedged"),
        ("Errors", "errors"),
    ]
    out += [
        "| Metric | Curated | Holdout |",
        "|---|---|---|",
        f"| Runs | {cur['runs']} | {hld['runs'] if hld else '—'} |",
    ]
    for label, key in rows_:
        out.append(f"| {label} | {cur[key]} | {hld[key] if hld else '—'} |")
    out += [""]

    out += ["## Answer × evidence", "",
            "| Cell | Meaning | Curated | Holdout |", "|---|---|---|---|"]
    meanings = {
        "grounded": "right, and the evidence was there",
        "from memory": "**right without the evidence — not grounded**",
        "evidence unused": "**had the evidence, still wrong**",
        "neither": "never had the evidence",
    }
    for cell, meaning in meanings.items():
        h = hld["_cross"][cell] if hld else "—"
        out.append(f"| {cell} | {meaning} | {cur['_cross'][cell]} | {h} |")
    out += [""]

    out += ["## Funnel", "",
            "Computed from `answer_match`, `evidence_match` and `searched` — the "
            "same attribution the read pass needed a human to make.", "",
            "| Stage | Curated | Holdout |", "|---|---|---|"]
    cur_f, hld_f = funnel(cur_rows), funnel(hld_rows) if hld_rows else {}
    for stage in FUNNEL_STAGES:
        out.append(f"| {stage} | {cur_f[stage]} | {hld_f.get(stage, '—')} |")
    out += [""]

    # --- curated only, by case ---
    out += ["## Curated, by case", "", "| case | correct | bucket |", "|---|---|---|"]
    for case_id, hits, n in _buckets(cur_rows):
        bucket = "solid" if hits == n else ("systematic" if hits == 0 else "flaky")
        out.append(f"| {case_id} | {hits}/{n} | {bucket} |")
    out += [""]

    if cur["_hedged"]:
        out += [
            "## Judge declined, matcher was confident (curated)", "",
            "The audit's most useful cell. A confident deterministic verdict "
            "the judge would not endorse is where an accepted phrasing is "
            "matching text that does not answer the question.", "",
        ]
        for r in cur["_hedged"]:
            out.append(
                f"- `{r['run_id']}` — matcher `{bool(r['answer_match'])}`, judge "
                f"`unclear`: {r['judge']['correctness'].get('why', '')}"
            )
        out += [""]

    if cur["_clashes"]:
        out += [
            "## Judge/matcher disagreements (curated)", "",
            "Where the accepted phrasings may be overfitted, or the judge wrong. "
            "Adjudicated by hand; the deterministic score stays the headline.", "",
        ]
        for r in cur["_clashes"]:
            v = r["judge"]["correctness"]
            out.append(
                f"- `{r['run_id']}` — matcher `{bool(r['answer_match'])}`, "
                f"judge `{v['verdict']}`: {v.get('why', '')}"
            )
        out += [""]

    # --- holdout: values only ---
    out += ["## Holdout", ""]
    if not hld:
        out += ["Not run yet.", ""]
    else:
        out += [
            "**Aggregate values only, deliberately.** No case ids, answers or "
            "judge rationales appear here. A named failing holdout case is a "
            "lead, and following it turns the holdout into training data with "
            "nothing downstream able to detect it. Read the numbers in the "
            "table above; open nothing else until the V0 → V1 comparison this "
            "arm exists to make has been made.",
            "",
            f"- {hld['runs']} runs, {hld['errors']} errors",
            f"- judge/matcher disagreements: {hld['judge_clashes']}; "
            f"judge unclear while matcher confident: {hld['judge_hedged']} "
            "(counts only — the cases are not listed)",
            "",
        ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Compare curated and holdout arms.")
    p.add_argument("curated")
    p.add_argument("holdout", nargs="?")
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)

    text = compare(args.curated, args.holdout)
    if args.out:
        Path(args.out).write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
