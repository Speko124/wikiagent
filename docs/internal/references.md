This file include some references about some of the best practices in evals and prompt engineering.
Treat this as methodology guidance but not ground truth!
Load only what is needed to avoid context bloating. (Ask WebFetch to extract only the section or guidance relevant to that question.)

# Evals best practices
Link- https://hamel.dev/blog/posts/evals-faq/

It covers topics including:
  error analysis and failure categorization
  sampling and trace review
  evaluation design
  binary pass/fail vs rating scales
  automated evaluators and LLM-as-judge
  uncertainty, abstention, and hallucination
  prompt iteration
  guardrails vs evaluators
  retrieval / RAG evaluation
  multi-step and agentic evaluation
  When to use

# Prompt Engineering
Prefer simple, explicit prompts first. Add techniques such as examples, additional structure, or chaining only when they solve an observed problem.

Link- https://claude.com/blog/best-practices-for-prompt-engineering

It covers topics including:
  clear, explicit, and specific instructions
  providing relevant context and motivation
  using examples / few-shot prompting when useful
  defining constraints and desired output formats
  handling uncertainty instead of encouraging guessing
  prompt chaining for complex tasks
  reasoning / thinking guidance for complex tasks
  structuring long or complex context
  role prompting and XML structure, including when they are unnecessary
  avoiding over-engineered prompts
  iterating and evaluating prompts based on actual outputs
