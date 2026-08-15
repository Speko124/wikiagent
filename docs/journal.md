# Decision Journal

Append-only. Entries are never edited or deleted, only superseded by later
entries. This is the complement to `project.md`: that doc is *living* and always
states the current design, which means it destroys its own history. This one
keeps the history, including the parts that turned out wrong.

Logged here: decisions taken, options rejected, corrections made mid-flight,
and findings that changed what came next. Not logged here: implementation notes,
which belong in code comments, or current design, which belongs in `project.md`.

Keep entries short. A heavy template is why the previous attempt at this
(`misc-dont-read/lessons.md`) stayed empty.

> **Provenance note.** J001 to J004 were reconstructed on 2026-08-15 from
> `project.md`, the code, and session transcripts. The decisions are accurately
> reported but the dates are approximate. J005 onward were written live.

---

### J001 — Rejected running the agent through `claude -p`

**2026-08-14 · rejection**

Considered driving the agent via the Claude Code CLI to avoid API spend against
a plan subscription.

Rejected. It required wrapping the search tool as an MCP server, actively
suppressing Claude Code's built-in WebSearch and WebFetch (which the assignment
forbids), and neutralising ambient `CLAUDE.md`, skills, and hooks. Worst of all
it would make the CLI version part of the system under test. The cost saving did
not justify adding confounds to the project's central deliverable. Removed the
MCP server and the dependency.

---

### J002 — `OVERFETCH` is deliberately not a parameter

**2026-08-14 · decision**

Search always fetches at least 5 results, however many `top_k` shows. The
surplus is cached, never rendered into the prompt, and costs nothing, but it
makes "would showing more have retrieved the gold article?" answerable from
traces already collected, with zero extra agent calls.

Chose not to expose it as a flag. It is the width of a diagnostic margin, not a
behaviour anyone should tune, and pinning it keeps the cache key stable so
changing `top_k` reuses the cache instead of invalidating it. Adding a knob is
easier than declining to, and most of the time it is the wrong call.

---

### J003 — Model capability gating is real, and silent if unhandled

**2026-08-15 · finding**

Adaptive thinking and `output_config.effort` are Opus/Sonnet-5-family
parameters. Haiku 4.5 returns a 400 for both. The request is now built per-model
(`agent._supports_adaptive_thinking`), and `--effort` on Haiku raises a clear
error instead of a wire-level failure.

Consequence worth stating plainly: **no thinking text in Haiku traces**, so
debugging on the default model leans entirely on tool calls and answers. This
is an argument for Sonnet as the agent that has nothing to do with capability.

---

### J004 — The multi-hop failure is stage 3, confirmed not inferred

**2026-08-15 · finding**

Asked which university *The Selfish Gene*'s author attended. The agent ran five
searches and did retrieve `Balliol College, Oxford`, the correct article, and
still answered wrong.

Checked the cached extracts directly rather than assuming: the `Richard Dawkins`
intro never mentions Balliol, and the `Balliol` intro never mentions Dawkins.
Retrieval succeeded. The answer-bearing fact was not in either opening section.
It is in the full article. So this is an evidence failure, not a retrieval
failure, and those have opposite fixes.

**Deliberately not acting on it.** One case is no basis for adding a
`fetch_article` tool. The question is now evidence-backed rather than
speculative, and the decision waits for a measured stage-3 rate.

Two secondary observations, both candidate eval dimensions: five searches on the
failure versus one on each success, so over-searching is a distress signal and
not just a cost. And the unanswerable case abstained correctly *without ever
searching*, which is the right answer by the wrong process, and argues for
scoring abstention and retrieval as separate signals.

---

### J005 — TDD was the wrong default for harness code

**2026-08-15 · correction**

`CLAUDE.md` carried a blanket "TDD, we first write tests that fit the design"
instruction. Followed it uniformly. Result: roughly 800 lines of tests across
`wikiagent/` and the eval scaffolding, 63 green, while `evals/cases/` is still
empty and no eval has ever been run.

The instruction was not wrong, its scope was. Corrected:

- **`wikiagent/` keeps TDD.** It is the system under test. Its failure modes are
  silent (a poisoned cache, a control arm that quietly retrieves, a trace that
  misreports what the model saw) and each one corrupts every downstream number
  without ever raising. Tests there are cheap insurance against a wasted phase.
- **`evals/` does not.** The harness is disposable and its correctness is
  checked by the eval results themselves. A wrong grader shows up as a
  nonsensical score, loudly, on the first run.

Cost of finding this late: the eval phase, which is the actual subject of the
assignment, started with a fraction of the time it deserved.

The general lesson is not about TDD. It is that a standing process instruction
given to an agent will be followed past the point where it serves the goal,
because the agent has no view of the budget. Scope rules need the budget baked
in, or a checkpoint that asks whether the rule is still earning its cost.

---
