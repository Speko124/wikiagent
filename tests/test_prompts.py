"""The prompt surface: system prompt + tool description, versioned together.

These are the two levers with the most influence on behaviour and the least
type-safety, so the tests here guard the ways they can go wrong quietly: a
version that pins only half of what the model reads, a description that stops
tracking `top_k`, a marker the model is told to expect but never sees, and an
old version edited out from under results that were scored against it.
"""

from __future__ import annotations

import hashlib
import re

import pytest

from conftest import Response, StubClient, text
from wikiagent import agent, prompts, tools, wikipedia


def test_get_returns_both_halves_of_the_prompt_surface():
    for version in prompts.PROMPTS:
        pset = prompts.get(version)
        assert pset.system.strip()
        assert pset.tool_description.strip()


def test_unknown_version_names_the_known_ones():
    with pytest.raises(KeyError, match="v0"):
        prompts.get("v99")


@pytest.mark.parametrize("version", sorted(prompts.PROMPTS))
def test_every_description_still_states_the_result_count(version):
    """Losing the `{n}` placeholder is silent: the description stays readable
    and simply stops telling the model how many results it gets."""
    assert "{n}" in prompts.get(version).tool_description
    assert "three" in tools.schema(3, version=version)["description"]


@pytest.fixture
def other_version(monkeypatch):
    """A second version, injected. Tests the pinning mechanism rather than
    relying on two real versions happening to exist."""
    other = prompts.PromptSet(system="OTHER SYSTEM", tool_description="OTHER {n} DESC")
    monkeypatch.setitem(prompts.PROMPTS, "vX", other)
    return other


def test_the_version_pins_the_tool_description_too(other_version):
    """The reason both live in one version. If the tool description could
    change independently, `prompt_version` in a trace would be a half-truth and
    two sweeps recorded as `v0` could have been run against different tools."""
    assert tools.schema(version="vX")["description"] != tools.schema()["description"]
    assert "OTHER" in tools.schema(version="vX")["description"]


def test_the_agent_sends_the_requested_version_of_both(other_version):
    client = StubClient([Response([text("answer")])])
    agent.ask("q", prompt_version="vX", client=client)
    sent = client.calls[0]
    assert sent["system"] == other_version.system
    assert sent["tools"][0]["description"] == tools.schema(version="vX")["description"]
    assert sent["system"] != prompts.get().system


def test_the_description_explains_the_marker_the_search_actually_emits():
    """The model is told a cut-off intro is marked. If the marker in the
    description and the one in the search results ever diverge, the model is
    watching for a signal that never arrives — and 'the article doesn't say it'
    becomes indistinguishable from 'the text stopped here'."""
    long_text = "Sentence. " * 400
    truncated = wikipedia._truncate(long_text)
    assert truncated.endswith(wikipedia.TRUNCATION_MARKER)
    assert wikipedia.TRUNCATION_MARKER in tools.schema()["description"]


def test_the_default_system_prompt_does_not_state_a_result_count():
    """`top_k` is a knob; the count belongs to the tool description, which is
    built from the real value. Stating it in the system prompt too means
    `--top-k 5` silently ships a prompt that says three."""
    counted = re.compile(
        r"\b(one|two|three|four|five|\d+)\b[^.]{0,20}\b(articles|results)\b",
        re.IGNORECASE,
    )
    assert not counted.search(prompts.get().system)


def test_the_default_prompt_asks_for_exact_titles():
    """Otherwise the model paraphrases titles and `cited_titles` — an exact
    match against retrieved titles — reads as a citation failure."""
    assert "exact title" in prompts.get().system.lower()


# --- frozen versions --------------------------------------------------------

# Canary, not a checksum for its own sake. Editing a version that a sweep has
# already been scored against silently makes those results uninterpretable —
# the trace still says `v0`. Seeing this test fail is the reminder to add a new
# version instead. If the change really is intended, update the digest here.
FROZEN = {"v0": "7bd4894e018a175b", "v1": "c243201bc72665bb", "v2": "7cb5b7e9905b9f76"}


@pytest.mark.parametrize("version,digest", sorted(FROZEN.items()))
def test_frozen_versions_are_not_edited_in_place(version, digest):
    pset = prompts.get(version)
    actual = hashlib.sha256(
        "\x00".join(
            (pset.system, pset.tool_description, pset.fetch_description)
        ).encode()
    ).hexdigest()[:16]
    assert actual == digest, (
        f"Prompt {version} changed. Results already scored against it can no "
        "longer be compared. Add a new version instead of editing this one."
    )


def test_every_trace_records_what_the_prompt_actually_contained():
    """`prompt_version` is a promise; the digest is evidence.

    A version can be edited after a sweep while every row still names it. This
    had to be settled once already by comparing file timestamps to trace
    mtimes - which works, but only while the files sit on one machine.
    """
    client = StubClient([Response([text("answer")])])
    trace = agent.ask("q", prompt_version="v1", client=client)
    assert trace.prompt_digest == prompts.get("v1").digest
    assert trace.to_dict()["prompt_digest"] == prompts.get("v1").digest


def test_two_versions_have_different_digests():
    assert prompts.get("v0").digest != prompts.get("v1").digest
