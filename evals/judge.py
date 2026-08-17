"""LLM judge — one dimension it owns, one it audits.

**Ambiguity** is the dimension it owns. It is the only one where a
deterministic proxy was tried and measured to fail: disambiguation-page
retrieval fires on questions that aren't ambiguous and misses the ones that
are.

**Correctness** it only audits. The deterministic string matcher is the
headline number; this is a second opinion whose *disagreements* mark runs for
human review. An auditor needs far less alignment than a scorer — it doesn't
have to be right, only differently wrong — and it is what stops hand-authored
accepted phrasings from quietly overfitting to answers we've already seen.

Two calls rather than one, because of a specific failure mode: if the judge
sees the agent's answer while deciding whether the *question* was ambiguous, a
cleanly-handled answer makes the question look unambiguous, and competence
erases the evidence that it was needed. So the ambiguity call never receives
the answer, and a test enforces it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import anthropic

from wikiagent import agent

from .cases import Case

# Deliberately not the agent's model: same-model judging carries a documented
# self-preference bias, and the agent is the weaker model in exactly the
# judgement being asked of it.
JUDGE_MODEL = "claude-sonnet-5"
assert JUDGE_MODEL != agent.DEFAULT_MODEL

MAX_TOKENS = 1_000
TOOL_NAME = "record_verdict"


@dataclass(frozen=True)
class Rubric:
    """Both judge prompts, versioned together and frozen once calibrated.

    Same discipline as `wikiagent/prompts.py`, for the same reason: a rubric
    edit changes what every verdict means, and the row still says `j1`.
    Calibration numbers belong to a rubric version, so editing one in place
    silently detaches the other. Add a version and re-calibrate instead —
    `test_judge.py` holds a digest that fails if a calibrated rubric moves.
    """

    correctness: str
    ambiguity: str


_J1_CORRECTNESS = """You grade whether an answer is factually correct.

Judge the substance, not the wording. An answer using different phrasing from \
the reference is correct if it says the same thing.

Use `unclear` when the reference itself looks wrong or disputed, or when the \
question has more than one defensible answer. Do not force a verdict — a \
wrong reference is a real and common case, and marking it `unclear` is more \
useful than picking a side.

An answer that declines to answer is `incorrect` only if the information was \
genuinely available; if the answer honestly reports not finding something, \
say `unclear` rather than `incorrect`."""

_J1_AMBIGUITY = """You decide whether a question is ambiguous.

A question is ambiguous if it has more than one reasonable reading that would \
lead to a different answer. Sources of ambiguity include:

- entity: the name refers to more than one thing ("Tesla" - person or company)
- event: more than one instance ("the Tokyo Olympics" - 1964 or 2020)
- answer type: more than one property could be meant ("how big" - area or \
population; "when was it built" - founded or completed)
- scope: the boundary is unstated ("most similar planet" - solar system only?)

You are shown the Wikipedia articles the search returned, because ambiguity is \
often only concrete once you see what exists.

**Err toward flagging.** A question wrongly flagged costs a moment's review; \
an ambiguity missed here is invisible to everything downstream. If a careful \
person could reasonably read the question two ways, say yes."""


# j2 changes ONLY the correctness prompt. j1's correctness folded every honest
# failure into `unclear` - 9 of 11 hedged V0 runs were "the answer declines to
# provide the information", including one where its own rationale said the
# information was genuinely available. That is unusable as a primary score: it
# cannot separate "did not answer" from "the reference is disputed", and both
# land outside the numerator.
#
# The ambiguity text is carried over BYTE-IDENTICAL, so its 19/19 recall
# calibration still describes it. A test asserts that rather than trusting it.
_J2_CORRECTNESS = """You grade whether an answer is factually correct.

Judge the substance, not the wording. An answer using different phrasing from \
the reference is correct if it says the same thing.

Choose exactly one verdict:

- `correct` — states the right answer.
- `incorrect` — states a wrong answer, or states a right answer for a \
different question than the one asked.
- `declined` — does not state an answer at all: reports that it could not find \
the information, or asks the user a question instead of answering. **This is a \
failure to answer, not a wrong claim, and it is NOT `unclear`.** Use it even \
when declining was the honest thing to do.
- `unclear` — use ONLY when the reference answer itself looks wrong or \
disputed, or the question has more than one defensible answer. Never for an \
honest failure to find something.

An answer that declines and then volunteers a related fact is `declined`, \
unless the volunteered fact actually answers the question asked."""

RUBRICS = {
    "j1": Rubric(correctness=_J1_CORRECTNESS, ambiguity=_J1_AMBIGUITY),
    "j2": Rubric(correctness=_J2_CORRECTNESS, ambiguity=_J1_AMBIGUITY),
}

RUBRIC_VERSION = "j2"


def rubric(version: str = RUBRIC_VERSION) -> Rubric:
    if version not in RUBRICS:
        known = ", ".join(sorted(RUBRICS))
        raise KeyError(f"Unknown rubric {version!r}. Known: {known}")
    return RUBRICS[version]


def _tool(properties: dict) -> dict:
    return {
        "name": TOOL_NAME,
        "description": "Record the verdict.",
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
        },
    }


def _ask(system: str, content: str, tool: dict, client) -> dict:
    client = client or anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=[tool],
            # Forced, so a verdict never has to be parsed out of prose.
            tool_choice={"type": "tool", "name": TOOL_NAME},
            messages=[{"role": "user", "content": content}],
        )
    except anthropic.APIError as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}

    for block in response.content:
        if block.type == "tool_use" and block.name == TOOL_NAME:
            return dict(block.input)
    return {"error": "judge returned no verdict"}


def _stamp(out: dict) -> dict:
    out.setdefault("error", None)
    out["judge_model"] = JUDGE_MODEL
    out["rubric"] = RUBRIC_VERSION
    return out


def correctness(case: Case, answer: str, client=None) -> dict:
    """Second opinion on correctness. Never the headline number.

    Sees the question, the reference and the answer — deliberately not the
    retrieved text, which would turn this into consistency-with-retrieval.
    """
    content = (
        f"QUESTION\n{case.question}\n\n"
        f"REFERENCE ANSWER\n{case.expected}\n\n"
        f"ANSWER TO GRADE\n{answer}"
    )
    tool = _tool({
        "verdict": {"type": "string",
                    "enum": ["correct", "incorrect", "declined", "unclear"]},
        "why": {"type": "string", "description": "One sentence."},
    })
    out = _ask(rubric().correctness, content, tool, client)
    out.setdefault("verdict", None)
    return _stamp(out)


def ambiguity(case: Case, retrieved_titles: list[str], client=None) -> dict:
    """Whether the *question* is ambiguous.

    Receives the question and what search returned, and never the agent's
    answer — see the module docstring. Judged once per question rather than
    once per run, since ambiguity does not vary across repeats.
    """
    titles = "\n".join(f"- {t}" for t in retrieved_titles) or "- (none)"
    content = f"QUESTION\n{case.question}\n\nWIKIPEDIA ARTICLES FOUND\n{titles}"
    tool = _tool({
        "ambiguous": {"type": "boolean"},
        "why": {"type": "string", "description": "One sentence naming the readings."},
    })
    out = _ask(rubric().ambiguity, content, tool, client)
    out.setdefault("ambiguous", None)
    return _stamp(out)


# --- known defects of rubric j1 ---------------------------------------------

# j1 conflates "the answer cannot be determined" with "the question has more
# than one reading". Seen twice in calibration: einstein-nobel-premise (a false
# premise) and am-i-all-alone-writer (no source exists). Both are real false
# positives and both are the same category error.
#
# Flagged rather than fixed. Editing a calibrated rubric detaches it from the
# calibration that describes it, and a new version would have to re-earn the
# recall number that is the whole reason to trust this judge. Annotating costs
# nothing and leaves j1's evidence intact.
#
# Validated on all 19 ambiguous verdicts from both calibration passes: catches
# both known defects, wrongly flags none of the true positives.
_DEFECT_LANGUAGE = re.compile(
    r"no (wikipedia )?(article|source|clear source)|does not (exist|appear)|"
    r"cannot be (determined|verified)|false premise|presuppos|no evidence",
    re.I,
)


def flag_defects(verdict: dict, case: Case | None = None) -> list[str]:
    """Annotate an ambiguity verdict with suspected j1 category errors.

    Returns flags; never edits the verdict. Same rule as the judge not
    overriding the deterministic matcher — an instrument that silently corrects
    another instrument hides the disagreement that was the useful part.
    """
    if not verdict.get("ambiguous"):
        return []
    flags = []
    if _DEFECT_LANGUAGE.search(verdict.get("why") or ""):
        flags.append("suspect:undeterminable-not-ambiguous")
    if case is not None:
        if "false-premise" in case.dimensions:
            flags.append("suspect:false-premise-case")
        if case.answer_kind == "none":
            flags.append("suspect:unanswerable-case")
    return flags


# --- sweep adapter ----------------------------------------------------------


class SweepJudge:
    """What the runner calls: both dimensions, one object.

    Ambiguity is cached per question. It is a property of the question, not of
    a run, so judging it once per repeat would triple the cost and invite three
    different answers to the same question — which would then look like agent
    variance.
    """

    model = JUDGE_MODEL
    version = RUBRIC_VERSION

    def __init__(self, client=None):
        self._client = client
        self._ambiguity: dict[str, dict] = {}

    def __call__(self, case: Case, trace) -> dict:
        verdict = correctness(case, trace.answer, client=self._client)
        if case.id not in self._ambiguity:
            amb = ambiguity(case, trace.shown_titles, client=self._client)
            amb["flags"] = flag_defects(amb, case)
            self._ambiguity[case.id] = amb
        return {"correctness": verdict, "ambiguity": self._ambiguity[case.id]}
