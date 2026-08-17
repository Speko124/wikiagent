"""The sweep runner: cases -> agent -> graders -> results + traces.

A sweep is ~120 paid agent calls, which drives most of the design here:

* **Append as you go, resume from disk.** Results are written after every run
  and a re-run skips what already completed, so an interruption at run 90
  costs one run, not ninety.
* **Failures are recorded, not raised.** One bad case must not end the sweep.
* **A failed run yields no signals.** Its retrieval fields are `None`, not
  `False`; an infrastructure error is not a retrieval miss.
* **The config is written into every row and into the run directory,** and a
  resume refuses to continue into a directory built with a different config.
  Merging two configs' rows would produce numbers that still look plausible.

The Wikipedia cache stays on during a sweep on purpose: repeats are meant to
measure model variance, so the corpus underneath them has to be pinned.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from wikiagent import agent, cli, prompts, wikipedia
from wikiagent.trace import Trace

from . import cases as cases_mod
from . import graders


@dataclass
class Config:
    model: str = agent.DEFAULT_MODEL
    prompt_version: str = prompts.DEFAULT_VERSION
    effort: str | None = None
    use_tools: bool = True
    use_cache: bool = True
    top_k: int = wikipedia.DEFAULT_TOP_K
    repeats: int = 3
    # Suppresses the reading artifacts. Error analysis over a holdout is what
    # turns it into training data, so the affordance is removed rather than
    # merely discouraged - and it lives in the config so a resume cannot flip
    # it silently.
    holdout: bool = False
    # Recorded even when absent, so a results file can never be mistaken for
    # one that was judged. Filled in from the judge object when there is one.
    judge_model: str | None = None
    judge_version: str | None = None


RESULTS = "results.jsonl"
CONFIG_FILE = "config.json"
TRACES = "traces"


def _run_id(case_id: str, repeat: int) -> str:
    return f"{case_id}#{repeat}"


def _completed(out_dir: Path) -> dict[str, dict]:
    """Rows worth keeping from a previous attempt.

    Errored runs are dropped so they get retried — an error is more often a
    network blip than a property of the case, and freezing one into the results
    would quietly understate the agent.
    """
    path = out_dir / RESULTS
    if not path.exists():
        return {}
    keep: dict[str, dict] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("error") is None:
            keep[row["run_id"]] = row
    return keep


def _check_config(out_dir: Path, config: Config) -> None:
    path = out_dir / CONFIG_FILE
    if not path.exists():
        path.write_text(json.dumps(asdict(config), indent=2))
        return
    previous = json.loads(path.read_text())
    current = asdict(config)
    differing = [k for k in current if previous.get(k) != current[k]]
    if differing:
        raise ValueError(
            f"{out_dir} was produced with a different config "
            f"({', '.join(differing)} differ). Use a new output directory — "
            "mixing configs in one results file makes the numbers unreadable."
        )


def _error_trace(question: str, config: Config, message: str) -> Trace:
    return Trace(
        question=question,
        model=config.model,
        prompt_version=config.prompt_version,
        effort=config.effort,
        tools_enabled=config.use_tools,
        top_k=config.top_k,
        error=message,
    )


def sweep(
    cases: list[cases_mod.Case],
    out_dir: str | Path,
    config: Config | None = None,
    ask: Callable[..., Trace] = agent.ask,
    judge: Callable | None = None,
    cache_dir: Path | None = None,
    on_result: Callable[[dict], None] | None = None,
) -> Path:
    """Run every case `config.repeats` times. Returns the output directory."""
    config = config or Config()
    if judge is not None:
        config.judge_model = getattr(judge, "model", None)
        config.judge_version = getattr(judge, "version", None)

    out_dir = Path(out_dir)
    (out_dir / TRACES).mkdir(parents=True, exist_ok=True)
    _check_config(out_dir, config)

    done = _completed(out_dir)
    results_path = out_dir / RESULTS
    # Rewritten rather than appended to, so dropped error rows really disappear.
    results_path.write_text(
        "".join(json.dumps(done[k]) + "\n" for k in sorted(done))
    )

    frozen = asdict(config)
    for case in cases:
        for repeat in range(config.repeats):
            run_id = _run_id(case.id, repeat)
            if run_id in done:
                continue

            trace_name = f"{TRACES}/{case.id}--r{repeat}.json"
            started = time.monotonic()
            try:
                trace = ask(
                    case.question,
                    model=config.model,
                    prompt_version=config.prompt_version,
                    effort=config.effort,
                    use_tools=config.use_tools,
                    use_cache=config.use_cache,
                    top_k=config.top_k,
                    cache_dir=cache_dir,
                )
                row = graders.grade(case, trace)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as exc:  # noqa: BLE001 - one bad case ends one run
                trace = _error_trace(
                    case.question, config, f"{type(exc).__name__}: {exc}"
                )
                trace.latency_s = time.monotonic() - started
                row = graders.grade(case, trace)
                # The run never happened, so it has no retrieval signals to
                # report. False here would read as a retrieval failure.
                row["gold_shown"] = row["gold_fetched"] = None

            trace.save(out_dir / trace_name)
            row.update(
                run_id=run_id,
                repeat=repeat,
                trace=trace_name,
                # Carried on the row so it can be read on its own, without
                # joining back to the case file by hand.
                question=case.question,
                expected=case.expected,
                case_notes=case.notes,
                config=frozen,
                judge=judge(case, trace) if judge and row["error"] is None else None,
            )
            with results_path.open("a") as fh:
                fh.write(json.dumps(row) + "\n")
            if on_result:
                on_result(row)

    rows = [json.loads(ln) for ln in results_path.read_text().splitlines() if ln.strip()]
    (out_dir / "summary.md").write_text(summarize(rows, config))
    if not config.holdout:
        (out_dir / "review.md").write_text(review(rows, config))
        _seed_labels(out_dir / "labels.jsonl", rows)
    return out_dir


# --- artifacts for reading and bucketing ------------------------------------


def _seed_labels(path: Path, rows: list[dict]) -> None:
    """Seed a blank label per run, preserving anything already written.

    Hand labels are the expensive artifact in this project — a sweep that
    reseeded the file would erase an afternoon of judgement in a millisecond,
    and the file would still look perfectly well-formed afterwards.
    """
    existing: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                label = json.loads(line)
                existing[label["run_id"]] = label

    with path.open("w") as fh:
        for row in rows:
            label = existing.get(
                row["run_id"],
                # `stage` is free text on purpose. The funnel is a hypothesis;
                # a fixed set of options here would quietly become the answer.
                {"run_id": row["run_id"], "verdict": "", "stage": "", "note": ""},
            )
            fh.write(json.dumps(label) + "\n")


def _gold_flag(row: dict) -> str:
    return {True: "gold SHOWN", False: "gold MISS", None: "no gold article"}[
        row.get("gold_shown")
    ]


def review(rows: list[dict], config: Config) -> str:
    """Every run rendered for a human to read top to bottom.

    Built from `results.jsonl` rather than from the traces, so it covers a
    resumed sweep in full. Repeats of a case sit together, which is what makes
    flakiness visible without cross-referencing anything.
    """
    out = [
        "# Review worksheet",
        "",
        f"`{config.model}` · prompt `{config.prompt_version}` · top_k "
        f"{config.top_k} · {'tools on' if config.use_tools else 'NO TOOLS'} · "
        f"{len(rows)} runs",
        "",
        "Read top to bottom and record verdicts in `labels.jsonl`. Full traces "
        "(raw tool results, per-turn thinking) are under `traces/`.",
        "",
    ]
    for row in rows:
        out += [
            "---",
            "",
            f"## `{row['run_id']}` — {', '.join(row.get('dimensions', []))}",
            "",
            f"**Q** {row.get('question', '')}",
            "",
            f"**Expected** {row.get('expected', '')}",
            "",
        ]
        if row.get("case_notes"):
            out += [f"*Why this case exists: {row['case_notes']}*", ""]
        if row.get("error"):
            out += [f"> **ERROR** {row['error']}", ""]
        queries = row.get("queries") or []
        out += [
            f"**Searched** ({len(queries)}): "
            + (" · ".join(f"`{q}`" for q in queries) or "*did not search*"),
            "",
            f"**Shown** ({_gold_flag(row)}): "
            + (", ".join(row.get("shown_titles") or []) or "—"),
            "",
        ]
        beyond = [
            t for t in row.get("retrieved_titles") or []
            if t not in (row.get("shown_titles") or [])
        ]
        if beyond:
            out += [f"**Fetched but not shown** (top_k={config.top_k}): "
                    + ", ".join(beyond), ""]
        out += [
            "**Answer**",
            "",
            "> " + (row.get("answer") or "*(none)*").replace("\n", "\n> "),
            "",
            f"*named: {', '.join(row.get('cited_titles') or []) or 'none'} · "
            f"{row.get('n_turns')} turns · {row.get('input_tokens', 0):,} in / "
            f"{row.get('output_tokens', 0):,} out · {row.get('latency_s')}s · "
            f"[trace]({row.get('trace', '')})*",
            "",
        ]
    return "\n".join(out)


# --- summary ----------------------------------------------------------------


def _rate(hits: int, total: int) -> str:
    if not total:
        return "n/a (0 runs)"
    return f"{hits}/{total} ({hits / total:.0%})"


def summarize(rows: list[dict], config: Config) -> str:
    """Deterministic signals only — this file is never an answer-quality score.

    Errored runs are counted and then excluded from every rate below, so a
    flaky network shows up as a run count, not as a worse agent.
    """
    errored = [r for r in rows if r.get("error")]
    ok = [r for r in rows if not r.get("error")]
    gold = [r for r in ok if r.get("gold_shown") is not None]

    out = [
        "# Sweep summary",
        "",
        *((
            "> **HOLDOUT — metrics only.** Do not open the traces for error "
            "analysis until the comparison this set exists to make has been "
            "made. Reading them turns the holdout into training data, and "
            "nothing downstream can detect that it happened.",
            "",
        ) if config.holdout else ()),
        f"**Model** `{config.model}` · **prompt** `{config.prompt_version}` · "
        f"**top_k** {config.top_k} · **tools** "
        f"{'on' if config.use_tools else 'OFF (control arm)'} · "
        f"**repeats** {config.repeats} · **effort** {config.effort or '—'}",
        "",
        f"**Runs** {len(rows)} total, {len(errored)} errored "
        "(errors are excluded from every rate below).",
        "",
        "## Deterministic signals",
        "",
    ]

    if not ok:
        out += ["No completed runs.", ""]
    else:
        shown = sum(1 for r in gold if r["gold_shown"])
        only_fetched = sum(
            1 for r in gold if not r["gold_shown"] and r.get("gold_fetched")
        )
        out += [
            f"- Searched at all: {_rate(sum(1 for r in ok if r['searched']), len(ok))}",
            f"- Gold article shown to the model: {_rate(shown, len(gold))} "
            "— denominator is runs whose case has a gold article",
            f"- Gold fetched but past top_k (raising top_k would have helped): "
            f"{only_fetched}",
            f"- Named a retrieved article: "
            f"{_rate(sum(1 for r in ok if r['cited_titles']), len(ok))}",
            f"- Turns: median {statistics.median(r['n_turns'] for r in ok):.0f}, "
            f"max {max(r['n_turns'] for r in ok)}",
            f"- Tokens: {sum(r['input_tokens'] for r in ok):,} in / "
            f"{sum(r['output_tokens'] for r in ok):,} out",
            f"- Latency: median {statistics.median(r['latency_s'] for r in ok):.1f}s",
            "",
        ]

    out += _retrieval_by_case(gold)

    out += [
        "## Not measured here",
        "",
        (
            "Correctness, faithfulness and posture are **not measured** — no "
            "judge ran for this sweep. Nothing above is an answer-quality score."
            if not config.judge_model
            else f"Judged by `{config.judge_model}` rubric "
            f"`{config.judge_version}`; see `results.jsonl`."
        ),
        "",
    ]
    return "\n".join(out)


def _retrieval_by_case(gold_rows: list[dict]) -> list[str]:
    """Per-case buckets: 0/n is systematic and gets fixed first; 1..n-1/n is
    flaky and usually means query wording; n/n is solid."""
    if not gold_rows:
        return []
    by_case: dict[str, list[bool]] = {}
    for row in gold_rows:
        by_case.setdefault(row["case_id"], []).append(bool(row["gold_shown"]))

    lines = [
        "## Retrieval by case",
        "",
        "| case | gold shown | bucket |",
        "|---|---|---|",
    ]
    for case_id, hits in sorted(by_case.items(), key=lambda kv: sum(kv[1]) / len(kv[1])):
        n, k = len(hits), sum(hits)
        bucket = "solid" if k == n else ("systematic" if k == 0 else "flaky")
        lines.append(f"| {case_id} | {k}/{n} | {bucket} |")
    return lines + [""]


# --- CLI --------------------------------------------------------------------


def _default_out(config: Config, cases_path: str) -> Path:
    """Names the case set as well as the config — two sweeps over different
    sets must not land in directories that differ only by a timestamp."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    arm = "notools" if not config.use_tools else config.prompt_version
    stem = Path(cases_path).stem or "cases"
    return Path("results") / f"{stamp}-{stem}-{config.model}-{arm}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run the eval sweep.")
    p.add_argument("--cases", default="evals/cases", help="file or directory of .jsonl")
    p.add_argument("--out", help="output directory (existing one resumes)")
    p.add_argument("--model", default=Config.model)
    p.add_argument("--prompt", default=Config.prompt_version)
    p.add_argument("--effort")
    p.add_argument("--top-k", type=int, default=Config.top_k)
    p.add_argument("--repeats", type=int, default=Config.repeats)
    p.add_argument("--no-tools", action="store_true", help="control arm")
    p.add_argument("--holdout", action="store_true",
                   help="metrics only: no review worksheet, no label file")
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--limit", type=int, help="run only the first N cases")
    args = p.parse_args(argv)
    cli._load_dotenv()

    config = Config(
        model=args.model,
        prompt_version=args.prompt,
        effort=args.effort,
        use_tools=not args.no_tools,
        use_cache=not args.no_cache,
        top_k=args.top_k,
        repeats=args.repeats,
        holdout=args.holdout,
    )
    loaded = cases_mod.load(args.cases)
    if args.limit:
        loaded = loaded[: args.limit]
    out_dir = Path(args.out) if args.out else _default_out(config, args.cases)

    total = len(loaded) * config.repeats
    state = {"n": 0}

    def report(row: dict) -> None:
        state["n"] += 1
        gold = {True: "gold", False: "MISS", None: "—"}[row["gold_shown"]]
        flag = f" ERROR {row['error']}" if row["error"] else ""
        print(
            f"[{state['n']}/{total}] {row['run_id']:<14} "
            f"{row['n_searches']} search · {gold} · {row['latency_s']:.1f}s{flag}",
            flush=True,
        )

    print(f"{len(loaded)} cases x {config.repeats} -> {out_dir}", flush=True)
    sweep(loaded, out_dir, config, on_result=report)
    print(f"\n{(out_dir / 'summary.md').read_text()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
