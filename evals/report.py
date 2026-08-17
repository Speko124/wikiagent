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


def _rate(hits: int, total: int) -> str:
    return f"{hits}/{total} ({hits / total:.0%})" if total else "n/a"


def _metrics(rows: list[dict]) -> dict:
    ok = [r for r in rows if not r.get("error")]
    scorable = [r for r in ok if r.get("answer_match") is not None]
    with_ev = [r for r in ok if r.get("evidence_match") is not None]
    completeness = [
        r["answer_completeness"] for r in ok if r.get("answer_completeness") is not None
    ]
    judged = [
        r for r in ok
        if (r.get("judge") or {}).get("correctness", {}).get("verdict")
        in ("correct", "incorrect")
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
        "correct": _rate(sum(1 for r in scorable if r["answer_match"]), len(scorable)),
        "evidence_found": _rate(
            sum(1 for r in with_ev if r["evidence_match"]), len(with_ev)
        ),
        "completeness": f"{statistics.mean(completeness):.0%}" if completeness else "n/a",
        "searched": _rate(sum(1 for r in ok if r["searched"]), len(ok)),
        "mean_searches": f"{statistics.mean([r['n_searches'] for r in ok]):.1f}"
        if ok else "n/a",
        "corroboration": f"{statistics.mean([len(r['cited_titles']) for r in ok]):.1f}"
        if ok else "n/a",
        "answer_chars": f"{statistics.mean([len(r['answer']) for r in ok]):.0f}"
        if ok else "n/a",
        "output_tokens": f"{statistics.mean([r['output_tokens'] for r in ok]):.0f}"
        if ok else "n/a",
        "latency_s": f"{statistics.median([r['latency_s'] for r in ok]):.1f}"
        if ok else "n/a",
        "judge_clashes": f"{len(clashes)}/{len(judged)}" if judged else "n/a",
        "_clashes": clashes,
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


FUNNEL_STAGES = (
    "correct, grounded",
    "correct, evidence not checkable",
    "5 grounding: answered from memory",
    "4 synthesis: had the evidence, answered wrong",
    "3 evidence: right article, fact not in the retrieved text",
    "2 retrieval: the answer-bearing article never surfaced",
    "1 query: did not search at all",
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
        answer, evidence = r.get("answer_match"), r.get("evidence_match")
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


def _buckets(rows: list[dict]) -> list[tuple[str, int, int]]:
    by_case: dict[str, list[bool]] = {}
    for r in rows:
        if r.get("answer_match") is not None and not r.get("error"):
            by_case.setdefault(r["case_id"], []).append(bool(r["answer_match"]))
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
        ("Correct (deterministic)", "correct"),
        ("Evidence retrieved", "evidence_found"),
        ("Answer completeness (mean)", "completeness"),
        ("Searched at all", "searched"),
        ("Searches per run", "mean_searches"),
        ("Articles named per answer", "corroboration"),
        ("Answer length (chars)", "answer_chars"),
        ("Output tokens", "output_tokens"),
        ("Latency (median s)", "latency_s"),
        ("Judge/matcher disagreements", "judge_clashes"),
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
            f"- judge/matcher disagreements: {hld['judge_clashes']} "
            "(count only — the cases are not listed)",
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
