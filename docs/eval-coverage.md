# Curated eval coverage

The 18 curated questions and what each one is for.

**These cases are diagnostic, not representative.** Each anchors a core
capability or an observed failure mode, and the set is deliberately weighted
toward things that were seen to break. Its absolute numbers are pessimistic by
construction; its value is that a change moves a specific mode. The transfer
check is the disjoint 10-question holdout, which is random rather than curated.

Five of these were promoted from real user questions after the discovery pass,
because the hand-written cases had missed the failure that turned out to
dominate every version.

| Question | What it tests |
|---|---|
| In what year was the Rosetta Stone discovered? | Clean single-hop lookup; regression floor |
| How tall is the Eiffel Tower? | Requires search and evidence for a familiar fact instead of relying on memory |
| What nationality was the composer of the opera Tosca? | Multi-hop bridge synthesis with introduction-level evidence |
| Which is older, the University of Bologna or the University of Oxford? | Compares evidence from two articles; the final answer is derived and appears in neither |
| Where is Tesla from? | Detects entity ambiguity and covers both plausible readings |
| Which Japanese village is known for having more life-size straw dolls than residents? | Forms a useful query when the question gives no entity name |
| What was the first message sent over the internet? | Reformulates a weak query and retrieves a fact from the article body |
| Why did Albert Einstein win the Nobel Prize for the theory of relativity? | Rejects and corrects a false premise |
| Why did Albert Einstein win the Nobel Prize in Physics? | Matched control: answers a true premise rather than over-correcting |
| Did Alan Turing ever receive a Nobel Prize? | Corroborates a negative claim instead of treating absence as proof |
| Which countries border Switzerland? | Returns a complete multi-item answer |
| How many people attended the premiere of Beethoven's Fifth Symphony? | Searches before abstaining on an answerable-looking but unrecorded fact |
| What's the weather in Paris right now? | Recognises live data as outside Wikipedia without unnecessary search |
| who played eric in head of the class | Recovers from a memory-seeded query and retrieves a body fact |
| where is let's make a deal filmed 2018 | Exposes evidence beyond the 8K fetch cap |
| name of toy store in home alone 2 | Isolates the value of full-article retrieval for a clean body fact |
| beat bobby flay how many times has he won | Extracts a stated count from retrieved body text |
| who wrote am i all alone or is it only me | Refines the search after an initial miss, then abstains when Wikipedia has no relevant article |

Lowercase questions are verbatim from Natural Questions. The missing
capitalisation is deliberate: real users type that way, and it exercises query
formulation in a way hand-written questions do not.

Machine-readable form, including accepted answer phrasings and the evidence
each case requires: [`evals/cases/core.jsonl`](../evals/cases/core.jsonl).
