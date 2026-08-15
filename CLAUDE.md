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
- Add docs references where needed like design doc / execution plan (some you might need to create)

# Dev process
- TDD - we first write tests that fit the design and outcome
