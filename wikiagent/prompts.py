"""Everything the model reads, versioned together.

A prompt version pins **both** the system prompt and the tool description. They
are one surface: the system prompt says when to search, the tool description
says how, and changing either one changes behaviour. Versioning them separately
would let a tool-description edit silently invalidate a previous sweep's results
while `prompt_version` in the trace still claimed they were comparable.

Keep these short. Every line should be traceable to a failure we've seen, and
short prompts leave room to hill-climb where the evals say it's needed.

**Versions that have been run are frozen.** Once a sweep is scored against a
version, editing it retroactively makes those results uninterpretable — the
trace still names the version. Add a new one instead; `test_prompts.py` holds a
digest that fails if a frozen version moves.

An earlier draft was never run against anything, so it was never a baseline.
It's kept in `docs/prompt-archive.md` rather than here: an unrunnable version
sitting in the version table is just clutter that invites someone to select it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .wikipedia import TRUNCATION_MARKER


@dataclass(frozen=True)
class PromptSet:
    system: str
    tool_description: str  # `{n}` is filled in with the result count


# The baseline. Three properties are load-bearing and easy to lose in an edit:
#
# 1. The **result count appears only in the tool description**, which is built
#    from the real `top_k`. Stating it here too means `--top-k 5` ships a system
#    prompt that says three.
# 2. **Exact titles**, because `cited_titles` matches retrieved titles exactly.
#    Paraphrase ("articles on penicillin discovery" for "Discovery of
#    penicillin") makes the citation signal unreadable.
# 3. The **truncation marker is explained**, so "the article doesn't say" and
#    "the text stopped here" aren't the same observation to the model.
#
# Structure is three labelled blocks matching funnel stages, so a failure at a
# stage points at one block to edit.
V0 = PromptSet(
    system="""You answer questions using English Wikipedia, through the \
search_wikipedia tool.

## Searching
- Search before answering anything that depends on facts about the world.
- Search for one subject at a time. If the answer needs two facts, search for \
each of them.
- If a search misses, try again with different wording, a broader topic, or a \
related entity.

## Answering
- Answer only from what the search results say. Never fill a gap from memory.
- Name the articles you used, by their exact titles as they appear in the \
results.
- Be direct and brief.

## When Wikipedia doesn't answer it
- If the results don't support an answer, say so plainly and say what you did \
find. Don't guess.
- If the question assumes something false, say what's wrong with the \
assumption instead of answering as asked.""",
    tool_description=(
        "Search English Wikipedia and return the {n} best-matching articles, "
        "each as its title followed by the opening section of that article.\n\n"
        "Only the opening section is returned, not the whole article. It "
        "answers questions about a subject's main facts well, and questions "
        "about details buried deeper in an article poorly. A long opening "
        f"section is cut short, marked with {TRUNCATION_MARKER} — the article "
        "continues past that point.\n\n"
        "Search for the name of the thing you want — a person, place, event, "
        "or concept — not a full question. One subject per search: to connect "
        "two subjects, search for each of them."
    ),
)

PROMPTS = {"v0": V0}

DEFAULT_VERSION = "v0"


def get(version: str = DEFAULT_VERSION) -> PromptSet:
    if version not in PROMPTS:
        known = ", ".join(sorted(PROMPTS))
        raise KeyError(f"Unknown prompt version {version!r}. Known versions: {known}")
    return PROMPTS[version]
