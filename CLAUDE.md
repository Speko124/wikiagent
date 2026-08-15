# The Project
This is a home assignment as part of an Anthropic interview process for a Staff+ SWE, Safeguards Evals role.

The task: Build a system that uses Claude and Wikipedia to answer questions, and evaluate how well it works.

# Guidelines
- Keep the solution simple and scoped to the assignment.
- Avoid unnecessary abstractions, dependencies, or infrastructure.
- Ask before making major decisions that materially affect scope, architecture, or evaluation strategy.
- Be crisp and to the point.
- When suggesting different approaches, explain the tradeoffs and why you recommend one.

# Evals and prompting
Start with simple prompting and evals. Observe actual model behavior and failure modes before adding complexity.

Use failures to drive iteration: observe → categorize → fix → evaluate.

# Additional docs and references
More details are under `docs/`. Load them only when needed to avoid context bloat.
- `assignment.md` — full assignment details
- `reference.md` — prompt engineering and eval methodology references
- `project.md` - this where the spec live and we keep it up to date with decision we take
- `journal.md` - append-only decision log. Never edit or delete an entry, only add.
  Append one when we take a real decision, reject an option, correct course, or hit a
  finding that changes the plan. Keep it to a few lines. Rationale lives here; current
  design lives in `project.md`.
- Add docs references where needed like design doc / execution plan (some you might need to create)

# Dev process
- TDD for `wikiagent/` only. It is the system under test and its failure modes are silent
  (poisoned cache, a control arm that quietly retrieves, a trace that misreports what the
  model saw), so a bug there corrupts every downstream number without ever raising.
- Not TDD for `evals/`. The harness is disposable and its correctness is checked by the eval
  results themselves. A wrong grader shows up as a nonsensical score on the first run.
- Before adding coverage or abstraction anywhere, ask whether it is buying insurance against a
  silent failure. If not, skip it and spend the time on evals.
