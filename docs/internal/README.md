# Working notes

**Not required reading.** These are the internal artifacts the project ran on:
the living spec, the eval plan, and the per-sweep trace reviews. They are
committed because the claims in the reviewer-facing docs should be checkable,
not because anyone needs to read them end to end.

The three documents worth a reviewer's time are one level up:

| Doc | Length | What it is |
|---|---|---|
| [`../../README.md`](../../README.md) | 8K | Setup, demo, and what the evals found |
| [`../design-rationale.md`](../design-rationale.md) | 22K | Why every choice was made |
| [`../error-analysis.md`](../error-analysis.md) | 17K | The failure taxonomy; §8 is the all-versions summary |

What is in here:

| File | Why it exists |
|---|---|
| `project.md` | Living spec. Every decision recorded as it was taken, including ones later reversed |
| `eval-plan.md` | How the case set and rubric were chosen, with the backlog of candidate fixes |
| `v1-trace-review.md`, `v1b-trace-review.md`, `v2-trace-review.md` | Per-sweep trace analysis. These are what found the failure modes, and several eval bugs. Point-in-time: they predate the current metric contract and say so |
| `prompt-archive.md` | Prompts replaced before they were ever scored, and the defects that replaced them |
| `references.md` | Prior art consulted on eval methodology |
