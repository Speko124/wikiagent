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

import hashlib
from dataclasses import dataclass

from .wikipedia import TRUNCATION_MARKER


@dataclass(frozen=True)
class PromptSet:
    system: str
    tool_description: str  # `{n}` is filled in with the result count
    fetch_description: str = ""  # empty means the agent has search only

    @property
    def digest(self) -> str:
        """Fingerprint of everything the model reads.

        Recorded in every trace because `prompt_version` alone is a promise,
        not evidence: a version can be edited after a sweep and the rows still
        name it. With the digest on the row, "which wording produced these
        numbers?" is answerable from the results rather than from file
        timestamps — which is how it had to be answered once already.
        """
        joined = "\x00".join(
            (self.system, self.tool_description, self.fetch_description)
        )
        return hashlib.sha256(joined.encode()).hexdigest()[:16]


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

# v1 adds `fetch_article`. The prompt delta is deliberately two lines: the
# intervention is the tool, and a large prompt rewrite alongside it would make
# the V0 -> V1 delta unattributable.
#
# The escalation rule is stated as a condition rather than an encouragement -
# "the results name the right article but do not contain the answer" - because
# the V0 failures were not a reluctance to search, they were an inability to
# read further. An open invitation to fetch would buy latency and tokens on the
# 28 runs that already work.
V1 = PromptSet(
    system=V0.system.replace(
        """- If a search misses, try again with different wording, a broader topic, or a \
related entity.""",
        """- If a search misses, try again with different wording, a broader topic, or a \
related entity.
- If the results name the right article but its opening section does not \
contain the answer, open that article with fetch_article rather than guessing \
or giving up.""",
    ),
    tool_description=V0.tool_description,
    fetch_description=(
        "Read one Wikipedia article in full, given its exact title.\n\n"
        "Use it when search returned the right article but the opening section "
        "did not contain the answer — details like cast members, specific "
        "figures and dates usually live further down. Titles must be copied "
        "exactly from search results; this does not search, so a title it does "
        "not recognise returns nothing.\n\n"
        "Returns the article's prose only. **Infoboxes, sidebars and tables are "
        "not included**, so data that appears only in those is unavailable by "
        "any means. Very long articles are cut short, marked with "
        f"{TRUNCATION_MARKER}."
    ),
)

# v2 generalises v1's escalation rule instead of adding to it.
#
# v1 said: open the article when *its* opening section lacks the answer. The
# traces show the agent obeyed that literally and narrowly - it fetched the
# article whose title matched the topic, and never the article about the person
# who did the thing. Across six `arpanet-first-message` runs, `Leonard
# Kleinrock` was returned as a top-3 result every time and fetched zero times,
# while the agent re-read `ARPANET` up to six times per run.
#
# So v2 hands the choice back to the model: decide *which* article is most
# likely to carry the answer, and say that it may not be the one matching the
# question's subject. The specific-to-general direction is deliberate - if this
# proves flaky, narrowing again is a smaller change than widening was.
V2 = PromptSet(
    system=V1.system.replace(
        """- If the results name the right article but its opening section does not \
contain the answer, open that article with fetch_article rather than guessing \
or giving up.""",
        """- If the search results don't contain the answer, decide which article is \
most likely to carry it and open that one with fetch_article. It is often not \
the article matching the question's subject — a detail about a thing is \
frequently recorded in the article about the person, work or event involved.""",
    ),
    tool_description=V1.tool_description,
    fetch_description=(
        "Read one Wikipedia article in full, given its exact title or its id "
        "from a search result.\n\n"
        "Search returns only opening sections. Specific details — who did what, "
        "when, where, how many — usually live further down the article, so open "
        "the article rather than concluding the fact is unrecorded.\n\n"
        "Returns the article's prose only. **Infoboxes, sidebars and tables are "
        "not included.** Long articles are cut short, marked with "
        f"{TRUNCATION_MARKER}; text after that point was not returned, so it "
        "cannot be called absent."
    ),
)

PROMPTS = {"v0": V0, "v1": V1, "v2": V2}

# v1 by default, on measured evidence rather than on it being newest: 89% vs
# 71% correct on the curated set and 93% vs 81% on the held-out set, confirmed
# by an identical repeat sweep. v0 stays selectable (`--prompt v0`) and still
# declares search only, so the V0 baseline in results/ remains reproducible.
DEFAULT_VERSION = "v1"


def get(version: str = DEFAULT_VERSION) -> PromptSet:
    if version not in PROMPTS:
        known = ", ".join(sorted(PROMPTS))
        raise KeyError(f"Unknown prompt version {version!r}. Known versions: {known}")
    return PROMPTS[version]
