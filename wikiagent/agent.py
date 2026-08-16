"""The agent loop.

Written as an explicit loop rather than with the SDK's tool runner: the whole
point of this project is being able to see and score exactly what happened on
each turn, and an explicit loop puts that in one readable place.
"""

from __future__ import annotations

import time
from pathlib import Path

import anthropic

from . import prompts, tools, wikipedia
from .trace import ToolCall, Trace, Turn

DEFAULT_MODEL = "claude-haiku-4-5"
MAX_TOKENS = 8_000

# A guard, not a design parameter. Hitting it means the agent is looping, which
# is itself a finding worth seeing in the trace.
MAX_TURNS = 10


def _supports_adaptive_thinking(model: str) -> bool:
    """Adaptive thinking and `effort` are Opus/Sonnet-5-family features.

    Haiku 4.5 and other older models reject both with a 400, so the request has
    to be built per-model rather than assuming the newest surface.
    """
    return not any(m in model for m in ("haiku-4-5", "sonnet-4-5", "opus-4-5"))


def _text_of(content) -> str:
    return "\n".join(b.text for b in content if b.type == "text").strip()


def _thinking_of(content) -> str | None:
    parts = [b.thinking for b in content if b.type == "thinking" and b.thinking]
    return "\n".join(parts).strip() or None


def ask(
    question: str,
    model: str = DEFAULT_MODEL,
    prompt_version: str = prompts.DEFAULT_VERSION,
    effort: str | None = None,
    use_tools: bool = True,
    use_cache: bool = True,
    top_k: int = wikipedia.DEFAULT_TOP_K,
    cache_dir: Path | None = None,
    client: anthropic.Anthropic | None = None,
) -> Trace:
    """Answer one question. Returns a Trace; the answer is `trace.answer`.

    `use_tools=False` is the no-tool control arm: same question, no Wikipedia,
    which tells us whether an eval case actually requires retrieval at all.
    """
    client = client or anthropic.Anthropic()
    trace = Trace(
        question=question,
        model=model,
        prompt_version=prompt_version,
        effort=effort,
        tools_enabled=use_tools,
        top_k=top_k,
    )

    request: dict = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": prompts.get(prompt_version).system,
    }
    if _supports_adaptive_thinking(model):
        # display=summarized so reasoning lands in the trace; it costs nothing
        # extra and it's often where a wrong answer becomes explicable.
        request["thinking"] = {"type": "adaptive", "display": "summarized"}
        if effort:
            request["output_config"] = {"effort": effort}
    elif effort:
        raise ValueError(
            f"--effort is not supported on {model}; it is an Opus/Sonnet-5 "
            "family parameter and returns a 400 on older models."
        )
    if use_tools:
        request["tools"] = [tools.schema(top_k, version=prompt_version)]

    messages: list[dict] = [{"role": "user", "content": question}]
    started = time.monotonic()

    try:
        for i in range(MAX_TURNS):
            turn_started = time.monotonic()
            response = client.messages.create(messages=messages, **request)
            turn = Turn(
                index=i,
                thinking=_thinking_of(response.content),
                text=_text_of(response.content) or None,
                stop_reason=response.stop_reason,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cache_read_tokens=getattr(response.usage, "cache_read_input_tokens", 0) or 0,
                latency_s=time.monotonic() - turn_started,
            )
            trace.turns.append(turn)

            if response.stop_reason == "refusal":
                trace.error = "Model declined to answer (stop_reason=refusal)."
                break

            # Guarded on use_tools so the control arm cannot retrieve even if
            # a tool_use block somehow appears — the arm is only meaningful if
            # retrieval is structurally impossible, not merely undeclared.
            tool_uses = (
                [b for b in response.content if b.type == "tool_use"]
                if use_tools
                else []
            )
            if not tool_uses:
                trace.answer = turn.text or ""
                break

            # Echo the assistant turn back whole — thinking blocks included and
            # unmodified, which the API requires when continuing on the same model.
            messages.append({"role": "assistant", "content": response.content})

            results = []
            for block in tool_uses:
                found = tools.dispatch(
                    block.name,
                    block.input,
                    top_k=top_k,
                    cache_dir=cache_dir,
                    use_cache=use_cache,
                )
                rendered = found.render()
                turn.tool_calls.append(
                    ToolCall(
                        query=found.query,
                        raw=found.to_dict(),
                        rendered=rendered,
                        top_k=top_k,
                    )
                )
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": rendered,
                        "is_error": found.error is not None,
                    }
                )

            # All results for a turn go back in one user message; splitting them
            # trains the model out of making parallel calls.
            messages.append({"role": "user", "content": results})
        else:
            trace.error = f"Stopped after {MAX_TURNS} turns without a final answer."

    except anthropic.APIError as exc:
        trace.error = f"{type(exc).__name__}: {exc}"

    trace.latency_s = time.monotonic() - started
    return trace
