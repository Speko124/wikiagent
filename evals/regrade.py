"""Re-grade a completed sweep from its saved traces. No API calls.

A grader bug should not cost a re-run. Traces hold everything the deterministic
graders read — every query, the exact rendered tool output, the answer — so a
fixed grader can be applied to sweeps already paid for.

That mattered immediately: the V0 baseline reported `bologna-oxford-older` as
"answered from memory" because evidence matching required every requirement
inside a single tool call, while a multi-hop question gathers its evidence
across several by design. Without this, correcting that would have meant
re-running and re-paying for 84 runs to fix a bug in our arithmetic.

**Judge verdicts are carried over untouched**, never re-requested. They cost
money, they are non-deterministic, and re-rolling them would silently change
the judge/matcher agreement numbers that the audit depends on.
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
        # Everything the graders don't own is preserved verbatim — above all
        # the judge verdict, which is paid for and non-deterministic.
        merged = {
            **fresh,
            **{k: row[k] for k in
               ("run_id", "repeat", "trace", "question", "expected",
                "case_notes", "config", "judge") if k in row},
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
