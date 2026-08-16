"""Everything the model reads, versioned together.

A prompt version pins **both** the system prompt and the tool description. They
are one surface: the system prompt says when to search, the tool description
says how, and changing either one changes behaviour. Versioning them separately
would let a tool-description edit silently invalidate a previous sweep's results
while `prompt_version` in the trace still claimed they were comparable.

Keep these short. Every line should be traceable to a failure we've seen, and
short prompts leave room to hill-climb where the evals say it's needed.

**Old versions are frozen.** Once a sweep has run against a version, editing it
retroactively makes past results uninterpretable. Add a new version instead.
"""

from __future__ import annotations

from dataclasses import dataclass

from .wikipedia import TRUNCATION_MARKER


@dataclass(frozen=True)
class PromptSet:
    system: str
    tool_description: str  # `{n}` is filled in with the result count


V0 = PromptSet(
    system="""You answer questions using Wikipedia.

You have one tool, search_wikipedia, which returns the three best-matching \
articles and the opening section of each.

- Search before answering anything that depends on external facts.
- If a search misses, try again with different wording, a broader topic, or a \
related entity before giving up.
- Answer from what the search results actually say. Do not fill gaps from \
memory.
- Name the article or articles you drew on, in the text of your answer.
- If the results don't support an answer, say so plainly and say what you did \
find. Don't guess.
- If a question assumes something false, say what's wrong with the assumption \
instead of answering as asked.

Be direct and brief.""",
    tool_description=(
        "Search English Wikipedia and return the {n} best-matching articles, each "
        "as its title followed by the opening section of that article.\n\n"
        "Returns only the opening section, not the full article, so it answers "
        "questions about a topic's main facts better than questions about narrow "
        "details buried deep in an article.\n\n"
        "Search terms work best as the name of the thing you are looking for — a "
        "person, place, event, or concept — rather than as a full question. If a "
        "search misses, try again with different or broader terms."
    ),
)

# v1 fixes three defects in v0 rather than adding behaviour:
#
# 1. v0 hardcoded "three best-matching articles" while `top_k` is a knob, so
#    `--top-k 5` made the system prompt lie. The count now lives only in the
#    tool description, which is built from the actual value.
# 2. v0 asked the model to "name the article" without saying how, and it
#    paraphrased ("articles on penicillin discovery" for "Discovery of
#    penicillin"). Exact titles make the citation signal mean something.
# 3. Extracts are cut short and marked, but nothing told the model what the
#    marker meant — so "not in the article" and "cut off" looked identical.
#
# The one behavioural addition is "one subject per search", which comes from
# the one multi-hop failure observed in the demo: both articles were retrieved,
# neither intro mentioned the other, and the answer was invented in the join.
V1 = PromptSet(
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

PROMPTS = {"v0": V0, "v1": V1}

DEFAULT_VERSION = "v1"


def get(version: str = DEFAULT_VERSION) -> PromptSet:
    if version not in PROMPTS:
        known = ", ".join(sorted(PROMPTS))
        raise KeyError(f"Unknown prompt version {version!r}. Known versions: {known}")
    return PROMPTS[version]
