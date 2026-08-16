"""Command line interface: `wikiagent ask "..."` and `wikiagent demo`."""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from pathlib import Path

from . import agent, prompts, wikipedia
from .trace import Trace

DEMO_QUESTIONS = [
    # Single-hop factual
    "Who discovered penicillin, and roughly when?",
    # Multi-hop: needs two articles joined
    "Which university did the author of 'The Selfish Gene' study at?",
    # Should abstain: not the kind of fact Wikipedia records
    "What did Ada Lovelace eat for breakfast on her tenth birthday?",
    # False premise
    "Why did Albert Einstein win the Nobel Prize for the theory of relativity?",
    # Needs no search at all
    "What is 17 times 23?",
]


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Minimal .env loader. Existing environment variables win, so an exported
    key still overrides the file."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _fmt_provenance(trace: Trace) -> str:
    """What the harness knows for certain: what was searched, what came back.

    Deliberately not labelled "sources used" — only the model knows which of
    these it actually grounded on, and it names those in its prose.
    """
    if not trace.tools_enabled:
        return "(no-tool control run — Wikipedia was not available)"
    if not trace.searched:
        return "(no searches performed)"
    shown = trace.shown_titles
    return "\n".join([
        "Searched: " + " | ".join(f'"{q}"' for q in trace.queries),
        "Retrieved: " + (", ".join(shown) if shown else "nothing"),
    ])


def _print_verbose(trace: Trace) -> None:
    print("=" * 72)
    print(f"QUESTION: {trace.question}")
    print(
        f"model={trace.model}  prompt={trace.prompt_version}  "
        f"effort={trace.effort or 'default'}  tools={'on' if trace.tools_enabled else 'off'}"
    )
    print("=" * 72)

    for turn in trace.turns:
        print(f"\n--- turn {turn.index} "
              f"({turn.latency_s:.1f}s, {turn.output_tokens} out tok, "
              f"stop={turn.stop_reason}) ---")
        if turn.thinking:
            print("\n[thinking]")
            print(textwrap.indent(turn.thinking, "  "))
        if turn.text:
            print("\n[text]")
            print(textwrap.indent(turn.text, "  "))
        for call in turn.tool_calls:
            hit = "cache" if call.raw.get("cache_hit") else "live"
            print(f"\n[search: \"{call.query}\"  ({hit})]")
            if call.raw.get("error"):
                print(f"  ERROR: {call.raw['error']}")
            for rank, r in enumerate(call.raw.get("results", []), 1):
                # Mark results fetched but never shown — the gap between these
                # and the shown ones is what tells us whether raising top_k
                # would have helped.
                mark = " " if rank <= call.top_k else "~"
                print(f"  {mark}{rank}. {r['title']}  "
                      f"({len(r['extract'])} chars)  {r['url']}")
            if len(call.raw.get("results", [])) > call.top_k:
                print(f"     (~ = fetched but not shown to the model, "
                      f"top_k={call.top_k})")
            print("\n  [raw result shown to the model]")
            print(textwrap.indent(call.rendered, "  | "))

    print("\n" + "=" * 72)
    u = trace.usage
    print(
        f"{trace.n_turns} turns  {trace.n_searches} searches "
        f"({trace.cache_hits} cached)  {trace.latency_s:.1f}s  "
        f"{u['input_tokens']} in / {u['output_tokens']} out tok"
    )
    print("=" * 72)


def _print_answer(trace: Trace) -> None:
    if trace.error:
        print(f"[error] {trace.error}", file=sys.stderr)
    if trace.answer:
        print(trace.answer)
    print()
    print(_fmt_provenance(trace))


def _run_one(question: str, args: argparse.Namespace) -> Trace:
    trace = agent.ask(
        question,
        model=args.model,
        prompt_version=args.prompt,
        effort=args.effort,
        use_tools=not args.no_tools,
        use_cache=not args.no_cache,
        top_k=args.top_k,
    )
    if args.json:
        print(json.dumps(trace.to_dict(), indent=2))
    elif args.verbose:
        _print_verbose(trace)
    else:
        _print_answer(trace)
    if args.save:
        path = Path(args.save)
        if path.is_dir() or args.save.endswith("/"):
            path = path / f"trace-{abs(hash(question)) % 10**8}.json"
        print(f"\n[trace saved to {trace.save(path)}]", file=sys.stderr)
    return trace


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--model", default=agent.DEFAULT_MODEL, help="Claude model id")
    p.add_argument(
        "--prompt",
        default=prompts.DEFAULT_VERSION,
        choices=sorted(prompts.PROMPTS),
        help="system prompt version",
    )
    p.add_argument(
        "--effort",
        default=None,
        choices=["low", "medium", "high", "xhigh", "max"],
        help="thinking/effort level (default: the model's own default)",
    )
    p.add_argument("-v", "--verbose", action="store_true",
                   help="show every turn, query, and raw tool result")
    p.add_argument("--json", action="store_true", help="print the full trace as JSON")
    p.add_argument("--save", metavar="PATH", help="write the trace JSON to PATH")
    p.add_argument("--no-tools", action="store_true",
                   help="no-tool control: answer from the model's own knowledge")
    p.add_argument("--no-cache", action="store_true",
                   help="bypass the Wikipedia response cache")
    p.add_argument("--top-k", type=int, default=wikipedia.DEFAULT_TOP_K,
                   help=f"how many search results the model sees "
                        f"(default {wikipedia.DEFAULT_TOP_K}; at least "
                        f"{wikipedia.OVERFETCH} are always fetched and traced, "
                        f"so the surplus is available for offline analysis)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wikiagent",
        description="Answer questions using Claude and Wikipedia.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ask_p = sub.add_parser("ask", help="answer a single question")
    ask_p.add_argument("question", help="the question to answer")
    _add_common(ask_p)

    demo_p = sub.add_parser("demo", help="run a handful of sample questions")
    _add_common(demo_p)

    args = parser.parse_args(argv)
    _load_dotenv()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ANTHROPIC_API_KEY is not set.\n"
            "  Put it in a .env file, or: export ANTHROPIC_API_KEY=sk-ant-...",
            file=sys.stderr,
        )
        return 1

    if args.command == "ask":
        trace = _run_one(args.question, args)
        return 1 if trace.error else 0

    failures = 0
    for i, question in enumerate(DEMO_QUESTIONS):
        if i:
            print("\n" + "-" * 72 + "\n")
        if not args.verbose and not args.json:
            print(f"Q: {question}\n")
        if _run_one(question, args).error:
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
