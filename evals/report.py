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


OUTCOMES = (
    "confirmed success",
    "wrong answer",
    "answerable non-answer",
    "evaluator unresolved",
    "execution failure",
)


def outcome_of(row: dict) -> str:
    """Classify one run into exactly one outcome.

    Order is precedence, and it matters. A run that never produced a final
    answer has nothing to grade, so execution failure outranks any verdict
    left on the row. `evaluator unresolved` is kept strictly separate from
    `answerable non-answer`: the judge failing to decide is an instrument
    problem, the agent declining is a behaviour, and merging them would hide
    which of the two moved between versions.
    """
    correctness = (row.get("judge") or {}).get("correctness")
    # A malformed or missing judge payload is unresolved, never a crash: one
    # bad row must not take down a whole sweep's aggregation.
    verdict = correctness.get("verdict") if isinstance(correctness, dict) else None
    if row.get("error") or not (row.get("answer") or "").strip():
        return "execution failure"
    if verdict in (None, "unclear"):
        return "evaluator unresolved"
    if verdict == "correct":
        return "confirmed success"
    if verdict == "declined":
        # Declining is the right answer only where the case has none to give.
        return ("confirmed success" if row.get("answer_kind") == "none"
                else "answerable non-answer")
    return "wrong answer"


def outcomes(rows: list[dict]) -> dict[str, int]:
    """Mutually exclusive, exhaustive: the counts sum to every attempted run."""
    counts = dict.fromkeys(OUTCOMES, 0)
    for row in rows:
        counts[outcome_of(row)] += 1
    return counts


# Stage names first, the work each implies as the gloss. One vocabulary across
# the code, the generated reports and the write-up.
DIAGNOSES = (
    "Retrieval / Evidence — no answer-bearing text reached the model",
    "Synthesis — evidence present, answer wrong",
    "Answer — evidence present, declined anyway",
    "Evaluator — judge rubric, reference answer, or ambiguity",
    "Execution — agent loop or infrastructure",
)


def diagnose(rows: list[dict]) -> dict[str, int]:
    """Cross each non-success with whether the evidence reached the model.

    This is what turns a failure count into a work item. The same wrong answer
    means retrieval work when the evidence never arrived and reasoning work
    when it did, and those are not interchangeable. Successes are excluded:
    they need no diagnosis, and including them would let a headline gain hide
    inside a diagnostic table.

    Deliberately not combined into a score. These are five different kinds of
    work, and averaging them would imply they trade off against each other.
    """
    counts = dict.fromkeys(DIAGNOSES, 0)
    for row in rows:
        outcome = outcome_of(row)
        if outcome == "confirmed success":
            continue
        if outcome == "execution failure":
            counts["Execution — agent loop or infrastructure"] += 1
        elif outcome == "evaluator unresolved":
            counts["Evaluator — judge rubric, reference answer, or ambiguity"] += 1
        elif row.get("evidence_match") is not True:
            # Includes evidence never checked: if a case declares no evidence
            # spec we cannot claim the model had what it needed.
            counts["Retrieval / Evidence — no answer-bearing text reached the model"] += 1
        elif outcome == "wrong answer":
            counts["Synthesis — evidence present, answer wrong"] += 1
        else:                                    # answerable non-answer
            counts["Answer — evidence present, declined anyway"] += 1
    return counts


def _rate(hits: int, total: int) -> str:
    return f"{hits}/{total} ({hits / total:.0%})" if total else "n/a"


def _metrics(rows: list[dict], config: dict | None = None) -> dict:
    ok = [r for r in rows if not r.get("error")]
    # Headline correctness is confirmed-correct over EVERY attempted run.
    # `unclear`, errors, wrong answers and inappropriate declines are all
    # non-successes. Excluding unresolved runs flatters the score: it moved
    # the V0 holdout from 70% to 81%, which is the difference between "the
    # system answered this" and "the system answered this when it answered".
    decomposition = outcomes(rows)
    confirmed = decomposition["confirmed success"]
    unresolved = decomposition["evaluator unresolved"]
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
    # Only multi-requirement cases. On single-requirement cases the fraction is
    # 0.0 or 1.0 and identical to `answer_match`, so averaging over everything
    # produced a number that looked like a fourth dimension and was correctness
    # restated: 39 of 45 curated runs, and zero partial scores in V1 and V2.
    coverage = [
        r["answer_completeness"] for r in ok
        if r.get("answer_completeness") is not None
        and (r.get("n_answer_requirements") or 0) > 1
    ]
    coverage_cases = {
        r["case_id"] for r in ok if (r.get("n_answer_requirements") or 0) > 1
    }
    solid, n_cases, buckets = pass_at_k(rows, repeats=(config or {}).get('repeats'))
    # Ambiguity is judged per question, not per run, so it is counted over
    # distinct cases. Reported alongside how the agent fared on them: a set
    # where a third of questions have more than one reasonable reading is a
    # property of real user questions, and worth seeing next to correctness.
    ambiguous_cases, flagged_cases = {}, set()
    for r in rows:
        verdict = (r.get("judge") or {}).get("ambiguity") or {}
        if verdict.get("ambiguous") is not None:
            ambiguous_cases[r["case_id"]] = verdict["ambiguous"]
        if verdict.get("flags"):
            flagged_cases.add(r["case_id"])
    n_ambiguous = sum(1 for v in ambiguous_cases.values() if v)
    amb_ok = [
        r for r in ok
        if ambiguous_cases.get(r["case_id"]) and judged_correct(r) is not None
    ]
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
        "correct": _rate(confirmed, len(rows)),
        "judge_coverage": _rate(len(rows) - unresolved, len(rows)),
        "unresolved": str(unresolved),
        "_outcomes": decomposition,
        "correct_contains": _rate(
            sum(1 for r in scorable if r["answer_match"]), len(scorable)),
        "guardrail_clash": f"{len(guardrail_clash)}",
        "evidence_found": _rate(
            sum(1 for r in with_ev if r["evidence_match"]), len(with_ev)
        ),
        "coverage": (
            f"{statistics.mean(coverage):.0%} "
            f"({len(coverage_cases)} multi-fact cases, {len(coverage)} runs)"
            if coverage else "n/a (no multi-fact cases)"
        ),
        "pass_at_k": _rate(solid, n_cases),
        "buckets": " · ".join(f"{v} {k}" for k, v in buckets.items()),
        "searched": _rate(sum(1 for r in ok if r["searched"]), len(ok)),
        "mean_searches": f"{statistics.mean([r['n_searches'] for r in ok]):.1f}"
        if ok else "n/a",
        # Turns are the agent's own control loop. The mean says what a typical
        # run costs; the max says whether anything ran away, and a runaway is
        # invisible in an average over 54 runs.
        "turns": (f"{statistics.mean([r['n_turns'] for r in ok]):.1f} / "
                  f"{max(r['n_turns'] for r in ok)}") if ok else "n/a",
        "input_tokens": (f"{statistics.mean([r['input_tokens'] for r in ok]):,.0f}"
                         if ok else "n/a"),
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
        "ambiguous_questions": _rate(n_ambiguous, len(ambiguous_cases)),
        "correct_on_ambiguous": _rate(
            sum(1 for r in amb_ok if judged_correct(r)), len(amb_ok)),
        "ambiguity_flags": str(len(flagged_cases)),
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
    "6 answer: declined with the evidence in hand",
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
        outcome = outcome_of(r)
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
            # A decline is not a wrong answer. Routing it to synthesis claimed
            # the model reasoned badly when it never committed to a claim.
            out["6 answer: declined with the evidence in hand"
                if outcome == "answerable non-answer"
                else "4 synthesis: had the evidence, answered wrong"] += 1
        elif not r.get("searched"):
            out["1 query: did not search at all"] += 1
        elif r.get("gold_shown"):
            out["3 evidence: right article, fact not in the retrieved text"] += 1
        else:
            out["2 retrieval: the answer-bearing article never surfaced"] += 1
    return out


def pass_at_k(rows: list[dict], repeats: int | None = None) -> tuple[int, int, dict]:
    """pass^k: cases correct on *every* one of k repeats.

    A per-run rate hides the shape — 50% could be one case that always works
    beside one that never does, or two that flip a coin, and those need
    completely different responses.

    **Strict about unscored runs.** A run the judge would not score (`unclear`)
    or that errored is not a demonstrated pass, so it blocks a `solid` claim
    rather than being dropped from the denominator. Dropping it silently
    shrinks k: `tesla-origin` at v0 was [correct, unclear, unclear] and was
    reported as passing every repeat on the strength of a single run.
    """
    by_case: dict[str, list[bool | None]] = {}
    for row in rows:
        by_case.setdefault(row["case_id"], []).append(
            None if row.get("error") else judged_correct(row)
        )
    if not by_case:
        return 0, 0, {"solid (k/k)": 0, "flaky": 0, "systematic (0/k)": 0,
                      "incomplete": 0, "unresolved": 0}

    buckets = {"solid (k/k)": 0, "flaky": 0, "systematic (0/k)": 0,
               "incomplete": 0, "unresolved": 0}
    solid = 0
    for verdicts in by_case.values():
        scored = [v for v in verdicts if v is not None]
        expected = repeats or len(verdicts)
        if not scored:
            # Nothing could be said about this question. That is a question
            # the system failed to resolve, so it stays in the denominator
            # rather than quietly leaving the set.
            buckets["unresolved"] += 1
        elif len(scored) < expected:
            buckets["incomplete"] += 1     # cannot claim k/k on fewer than k
        elif all(scored):
            buckets["solid (k/k)"] += 1
            solid += 1
        elif not any(scored):
            buckets["systematic (0/k)"] += 1
        else:
            buckets["flaky"] += 1
    return solid, len(by_case), buckets


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
    cur = _metrics(cur_rows, cur_cfg)
    hld = _metrics(hld_rows, hld_cfg) if hld_rows else None

    out = [
        f"# Sweep report — prompt `{cur_cfg.get('prompt_version', '?')}`",
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

    # Three tiers, per the metric contract. Headline answers "how good is it";
    # supporting explains a version tradeoff; appendix is instrument health,
    # which matters but is not the result.
    headline = [
        ("**Correct** (all attempted runs)", "correct"),
        ("**pass^k** (correct on every repeat)", "pass_at_k"),
        ("  of which", "buckets"),
        ("**Evidence available** (eligible runs)", "evidence_found"),
    ]
    supporting = [
        ("Turns (mean / max)", "turns"),
        ("Input tokens / run", "input_tokens"),
        ("Searched at all", "searched"),
        ("Searches / run", "mean_searches"),
        ("Runs that opened an article", "fetch_rate"),
        ("Fetches / run (spread)", "fetch_spread"),
        ("Turns by fetch count", "turns_by_fetch"),
        ("Failed fetches", "failed_fetches"),
        ("Fetches with no prior search", "unescalated_fetches"),
        ("Latency median (s)", "latency_s"),
        ("Answer length (chars)", "answer_chars"),
        ("Output tokens", "output_tokens"),
    ]
    appendix = [
        ("Judge coverage (resolved / attempted)", "judge_coverage"),
        ("Unresolved runs", "unresolved"),
        ("Judge/matcher disagreements", "judge_clashes"),
        ("Judge unclear, matcher confident", "judge_hedged"),
        ("Correct (contains matcher, guardrail)", "correct_contains"),
        ("Articles named per answer", "corroboration"),
        ("Questions judged ambiguous", "ambiguous_questions"),
        ("  correct on those", "correct_on_ambiguous"),
        ("  flagged as suspect rubric calls", "ambiguity_flags"),
        ("Multi-fact coverage", "coverage"),
        ("Errors", "errors"),
    ]

    def block(title, keys, note=""):
        lines = [f"## {title}", ""]
        if note:
            lines += [note, ""]
        lines += ["| Metric | Curated | Holdout |", "|---|---|---|"]
        for label, key in keys:
            lines.append(f"| {label} | {cur[key]} | {hld[key] if hld else '—'} |")
        return lines + [""]

    out += [f"**Runs** {cur['runs']} curated"
            + (f", {hld['runs']} holdout" if hld else "") + "", ""]
    out += block("Headline",
                 headline,
                 "Correctness counts confirmed successes over **every attempted "
                 "run**: unclear verdicts, errors, wrong answers and declines on "
                 "answerable questions are all non-successes. pass^k keeps "
                 "unresolved questions in the denominator. Evidence shows its "
                 "eligible denominator, since it is only checkable where a case "
                 "declares what the evidence should contain.")
    out += ["## Outcome decomposition", "",
            "Mutually exclusive and exhaustive: these sum to every attempted "
            "run. `evaluator unresolved` is deliberately kept apart from "
            "`answerable non-answer` - the judge failing to decide is an "
            "instrument problem, the agent declining is a behaviour, and "
            "merging them would hide which one moved.", "",
            "| Outcome | Curated | Holdout |", "|---|---|---|"]
    for name in OUTCOMES:
        c = cur["_outcomes"][name]
        h = hld["_outcomes"][name] if hld else "—"
        label = f"**{name}**" if name == "confirmed success" else name
        out.append(f"| {label} | {c} | {h} |")
    out += [f"| *total* | *{sum(cur['_outcomes'].values())}* | "
            f"*{sum(hld['_outcomes'].values()) if hld else '—'}* |", ""]

    cur_diag, hld_diag = diagnose(cur_rows), diagnose(hld_rows) if hld_rows else {}
    out += ["## What each failure implies", "",
            "Every non-success crossed with whether the answer-bearing evidence "
            "reached the model. Not a score: these are five different kinds of "
            "work and they do not trade off against each other.", "",
            "| Failure implies | Curated | Holdout |", "|---|---|---|"]
    for name in DIAGNOSES:
        out.append(f"| {name} | {cur_diag[name]} | {hld_diag.get(name, '—')} |")
    out += [f"| *total failures* | *{sum(cur_diag.values())}* | "
            f"*{sum(hld_diag.values()) if hld_diag else '—'}* |", ""]

    out += block("Supporting (cost and behaviour)", supporting,
                 "Used to explain tradeoffs between versions, not to claim one.")
    out += block("Appendix (instrument health)", appendix,
                 "How much the measurement itself can be trusted.")

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
            "Adjudicated by hand — neither signal overrides the other.", "",
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
