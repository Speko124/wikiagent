"""Shared fixtures: a stub Anthropic client and canned Wikipedia payloads.

The stub mimics the shape of SDK content blocks closely enough that the agent
can't tell the difference, which is what lets every agent test run with no
network and no API key.
"""

from __future__ import annotations

import os

import pytest

from wikiagent import wikipedia


# --- fake SDK content blocks ------------------------------------------------

class Block:
    def __init__(self, type: str, **kw):
        self.type = type
        for k, v in kw.items():
            setattr(self, k, v)


def text(t: str) -> Block:
    return Block("text", text=t)


def thinking(t: str) -> Block:
    return Block("thinking", thinking=t, signature="sig")


def tool_use(query: str, id: str = "toolu_1", name: str = "search_wikipedia") -> Block:
    return Block("tool_use", id=id, name=name, input={"query": query})


class Usage:
    def __init__(self, input_tokens=100, output_tokens=50, cache_read_input_tokens=0):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_read_input_tokens = cache_read_input_tokens


class Response:
    def __init__(self, content, stop_reason="end_turn", usage=None):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = usage or Usage()


class StubMessages:
    def __init__(self, responses, repeat_last=False):
        self._responses = list(responses)
        self._repeat_last = repeat_last
        self.calls: list[dict] = []

    def create(self, **kw):
        self.calls.append(kw)
        if not self._responses:
            raise AssertionError("agent made more API calls than the test scripted")
        if self._repeat_last and len(self._responses) == 1:
            return self._responses[0]
        return self._responses.pop(0)


class StubClient:
    """Scripted Anthropic client. `repeat_last=True` makes the final response
    repeat forever, for exercising the runaway-loop guard."""

    def __init__(self, responses, repeat_last=False):
        self.messages = StubMessages(responses, repeat_last=repeat_last)

    @property
    def calls(self):
        return self.messages.calls


@pytest.fixture
def stub():
    return StubClient


# --- Wikipedia helpers ------------------------------------------------------

def article(title: str, extract: str = "Some text.") -> wikipedia.Article:
    return wikipedia.Article(
        title=title,
        url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
        extract=extract,
        pageid=abs(hash(title)) % 100000,
    )


@pytest.fixture
def cache_dir(tmp_path):
    """An isolated cache, so tests never read or write the real one."""
    return tmp_path / "cache"


@pytest.fixture
def fake_search(monkeypatch):
    """Replace the network layer. Returns a recorder of the calls made."""
    calls = []

    def install(results, error=None):
        def _fetch(query, fetch_k, timeout):
            calls.append({"query": query, "fetch_k": fetch_k})
            if error:
                raise RuntimeError(error)
            return [article(t) for t in results][:fetch_k]

        monkeypatch.setattr(wikipedia, "_fetch", _fetch)
        return calls

    return install


def requires_network(fn):
    return pytest.mark.skipif(
        os.environ.get("WIKIAGENT_NETWORK") != "1",
        reason="live Wikipedia test; set WIKIAGENT_NETWORK=1 to run",
    )(pytest.mark.network(fn))
