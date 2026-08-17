# wikiagent

A Claude agent that answers questions using Wikipedia, plus an eval suite that
measures how well it does.

Design decisions and their rationale live in [`docs/project.md`](docs/project.md).

## Setup

Requires Python 3.11+ and an Anthropic API key.

```bash
uv venv --python 3.11
uv pip install -e .
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
```

The agent defaults to `claude-haiku-4-5`. `--effort` is rejected on Haiku with
a clear message rather than a 400 — it's an Opus/Sonnet-5-family parameter, and
the request is built per-model.

## Use

```bash
# Answer one question
wikiagent ask "Who discovered penicillin, and roughly when?"

# See everything: each turn, every query, the raw text the model was shown
wikiagent ask "Which university did the author of 'The Selfish Gene' study at?" --verbose

# Five sample questions covering the behaviours worth watching
wikiagent demo
```

Normal output is the answer plus a provenance footer — what was searched and
what came back. That footer is built by the harness from the tool-call log, so
it is always accurate; the answer's own source attributions are the model's,
naming what it actually drew on.

### Useful flags

| Flag | What it does |
|---|---|
| `--verbose` | Every turn, query, and full raw tool result |
| `--json` | The whole trace as JSON |
| `--save PATH` | Write the trace to disk |
| `--no-tools` | Control arm: answer without Wikipedia at all |
| `--no-cache` | Bypass the response cache and hit the live API |
| `--model` / `--prompt` / `--effort` | Swap model, prompt version, or effort level |

## Tests

```bash
uv pip install -e ".[dev]"
pytest                              # 61 tests, no API key, no network
WIKIAGENT_NETWORK=1 pytest -m network   # 2 more, against the live MediaWiki API
```

Agent tests run against a stub Anthropic client, so the whole suite is free and
offline. The emphasis is on invariants whose failure would be *silent* — a
poisoned cache, a control arm that quietly retrieves, a trace that misreports
what the model saw. Those corrupt eval numbers without ever raising an error.

## How it works

```
question → agent loop ──search_wikipedia(query)──→ MediaWiki API
                     ←──title + article intro ×3──┘   (cached on disk)
         → answer + provenance
```

- **`wikiagent/wikipedia.py`** — MediaWiki API plus an on-disk cache. The cache
  isn't a speed optimization: live Wikipedia changes underneath repeated eval
  runs, so without it a score change can't be attributed to a prompt change.
- **`wikiagent/tools.py`** — the tool schema. The description is prompt
  engineering, and gets iterated like the system prompt.
- **`wikiagent/prompts.py`** — system prompts, versioned.
- **`wikiagent/agent.py`** — an explicit tool-use loop.
- **`wikiagent/trace.py`** — one record per run, holding **full raw tool
  results**. Both `--verbose` and the eval harness read it, so what you see
  while debugging can't drift from what gets scored.
- **`wikiagent/cli.py`** — the CLI.
