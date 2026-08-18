"""Re-grade a completed sweep from its saved traces. No API calls.

A grader bug should not cost a re-run. Traces hold everything the deterministic
graders read — every query, the exact rendered tool output, the answer — so a
fixed grader can be applied to sweeps already paid for.

That mattered immediately: the V0 baseline reported `bologna-oxford-older` as
"answered from memory" because evidence matching required every requirement
inside a single tool call, while a multi-hop question gathers its evidence
across several by design. Without this, correcting that would have meant
re-running and re-paying for 84 runs to fix a bug in our arithmetic.

**Judge verdicts are carried over untouched** when only grader code changed:
they cost money, they are non-deterministic, and re-rolling them would move
the judge/matcher agreement the audit depends on.

**But a verdict is dropped when the reference it was judged against changed.**
The judge is shown `question` and `expected`; if either is rewritten, the old
verdict answers a question that is no longer being asked. Carrying it over
looked harmless and produced a fabricated +3 improvement between two identical
sweeps — the agent's answers and tool output were unchanged, only the reference
had moved. That is the exact shape of silent corruption this harness exists to
prevent, so a stale verdict is now dropped and the row is marked for
re-judging.
"""

from __future__ import annotations

import json
from pathlib import Path

from wikiagent.trace import Trace

from . import cases as cases_mod
from . import graders


def regrade(out_dir: str | Path, cases_path: str | Path) -> tuple[int, int]:
    """Rewrite `results.jsonl` from the traces. Returns (rows, changed)."""
    out_dir = Path(out_dir)
    by_id = {c.id: c for c in cases_mod.load(cases_path)}
    results = out_dir / "results.jsonl"
    rows = [json.loads(ln) for ln in results.read_text().splitlines() if ln.strip()]

    rewritten, changed = [], 0
    for row in rows:
        case = by_id.get(row["case_id"])
        trace_path = out_dir / row["trace"]
        if case is None or not trace_path.exists():
            rewritten.append(row)
            continue

        fresh = graders.grade(case, Trace.load(trace_path))
        # Everything the graders don't own is preserved verbatim, except a
        # judge verdict whose reference has since been rewritten.
        stale_judgement = (
            row.get("judge") is not None
            and (row.get("expected") != case.expected
                 or row.get("question") != case.question)
        )
        merged = {
            **fresh,
            **{k: row[k] for k in
               ("run_id", "repeat", "trace", "config") if k in row},
            "question": case.question,
            "expected": case.expected,
            "case_notes": case.notes,
            "judge": None if stale_judgement else row.get("judge"),
            "judge_stale": stale_judgement,
        }
        if merged != row:
            changed += 1
        rewritten.append(merged)

    results.write_text("".join(json.dumps(r) + "\n" for r in rewritten))
    return len(rewritten), changed


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Re-grade a sweep from its traces.")
    p.add_argument("out_dir")
    p.add_argument("--cases", required=True)
    args = p.parse_args(argv)

    total, changed = regrade(args.out_dir, args.cases)
    print(f"{args.out_dir}: {total} rows, {changed} changed")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
