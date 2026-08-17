"""The sweep runner.

A sweep is ~120 paid agent calls. Almost every test here guards against a way
that spend could be wasted or, worse, quietly misread: rows lost to a crash,
runs silently repeated, two different configs merged into one results file, or
a harness error counted as a retrieval failure.
"""

from __future__ import annotations

import inspect
import json

import pytest

from evals import run
from evals.cases import Case
from wikiagent import agent
from wikiagent.trace import ToolCall, Trace, Turn


def case(i: int, gold=None) -> Case:
    return Case(
        id=f"c{i}",
        question=f"q{i}",
        expected="e",
        dimensions=["factual"],
        gold_articles=gold or [],
    )


def a_trace(question: str, titles=("Marie Curie",), answer="Answer.") -> Trace:
    t = Trace(question=question, model="m", prompt_version="v0", top_k=3)
    turn = Turn(index=0, input_tokens=10, output_tokens=5)
    if titles:
        turn.tool_calls.append(
            ToolCall(
                query=question,
                raw={"results": [{"title": x} for x in titles]},
                rendered="rendered",
                top_k=3,
            )
        )
    t.turns.append(turn)
    t.answer = answer
    return t


class FakeAsk:
    """Stands in for agent.ask. Records every call; can be scripted to fail."""

    def __init__(self, titles=("Marie Curie",), raise_on=None, hard_stop_after=None):
        self.calls: list[dict] = []
        self.titles = titles
        self.raise_on = set(raise_on or ())
        self.hard_stop_after = hard_stop_after

    def __call__(self, question, **kw):
        if self.hard_stop_after is not None and len(self.calls) >= self.hard_stop_after:
            raise KeyboardInterrupt("simulated interruption")
        self.calls.append({"question": question, **kw})
        if question in self.raise_on:
            raise RuntimeError("boom")
        return a_trace(question, self.titles)


CONFIG = run.Config(repeats=2, model="claude-haiku-4-5")


def rows_of(out_dir):
    text = (out_dir / "results.jsonl").read_text()
    return [json.loads(line) for line in text.splitlines() if line.strip()]


# --- the sweep itself -------------------------------------------------------

def test_runs_every_case_the_configured_number_of_times(tmp_path):
    ask = FakeAsk()
    run.sweep([case(1), case(2)], tmp_path, CONFIG, ask=ask)
    assert len(ask.calls) == 4
    assert len(rows_of(tmp_path)) == 4


def test_each_repeat_is_identified(tmp_path):
    run.sweep([case(1)], tmp_path, CONFIG, ask=FakeAsk())
    rows = rows_of(tmp_path)
    assert [r["repeat"] for r in rows] == [0, 1]
    assert {r["run_id"] for r in rows} == {"c1#0", "c1#1"}


def test_rows_carry_the_deterministic_grader_signals(tmp_path):
    run.sweep([case(1, gold=["Marie Curie"])], tmp_path, CONFIG, ask=FakeAsk())
    [row, _] = rows_of(tmp_path)
    assert row["case_id"] == "c1"
    assert row["searched"] is True
    assert row["gold_shown"] is True
    assert row["shown_titles"] == ["Marie Curie"]


def test_every_row_records_the_full_config(tmp_path):
    """Results outlive the command that produced them. A row that doesn't say
    which model and prompt made it can't be compared against anything later."""
    run.sweep([case(1)], tmp_path, CONFIG, ask=FakeAsk())
    cfg = rows_of(tmp_path)[0]["config"]
    assert cfg["model"] == "claude-haiku-4-5"
    assert cfg["prompt_version"] == run.Config().prompt_version
    assert cfg["top_k"] == run.Config().top_k
    assert cfg["use_tools"] is True
    assert cfg["repeats"] == 2


def test_traces_are_saved_one_file_per_run(tmp_path):
    run.sweep([case(1), case(2)], tmp_path, CONFIG, ask=FakeAsk())
    saved = sorted(p.name for p in (tmp_path / "traces").glob("*.json"))
    assert saved == ["c1--r0.json", "c1--r1.json", "c2--r0.json", "c2--r1.json"]
    trace = json.loads((tmp_path / "traces" / "c1--r0.json").read_text())
    assert trace["summary"]["shown_titles"] == ["Marie Curie"]


def test_rows_point_at_their_trace_file(tmp_path):
    run.sweep([case(1)], tmp_path, CONFIG, ask=FakeAsk())
    row = rows_of(tmp_path)[0]
    assert (tmp_path / row["trace"]).exists()


def test_the_no_tool_control_arm_is_passed_through(tmp_path):
    """The control arm is only meaningful if it reaches the agent."""
    ask = FakeAsk()
    run.sweep([case(1)], tmp_path, run.Config(repeats=1, use_tools=False), ask=ask)
    assert ask.calls[0]["use_tools"] is False


def test_runner_calls_ask_the_way_the_real_agent_expects(tmp_path):
    """The fake would happily swallow a kwarg the real agent rejects, so bind
    the recorded call against the real signature."""
    ask = FakeAsk()
    run.sweep([case(1)], tmp_path, run.Config(repeats=1), ask=ask)
    call = dict(ask.calls[0])
    question = call.pop("question")
    inspect.signature(agent.ask).bind(question, **call)


# --- durability -------------------------------------------------------------

def test_results_are_written_as_each_run_completes(tmp_path):
    """A sweep that dies at run 90 must not lose runs 1-89."""
    ask = FakeAsk(hard_stop_after=3)
    with pytest.raises(KeyboardInterrupt):
        run.sweep([case(1), case(2)], tmp_path, CONFIG, ask=ask)
    assert len(rows_of(tmp_path)) == 3


def test_resume_skips_completed_runs(tmp_path):
    run.sweep([case(1)], tmp_path, CONFIG, ask=FakeAsk())
    again = FakeAsk()
    run.sweep([case(1)], tmp_path, CONFIG, ask=again)
    assert again.calls == []
    assert len(rows_of(tmp_path)) == 2


def test_resume_runs_only_the_remainder(tmp_path):
    interrupted = FakeAsk(hard_stop_after=3)
    with pytest.raises(KeyboardInterrupt):
        run.sweep([case(1), case(2)], tmp_path, CONFIG, ask=interrupted)

    resumed = FakeAsk()
    run.sweep([case(1), case(2)], tmp_path, CONFIG, ask=resumed)
    assert len(resumed.calls) == 1
    assert len(rows_of(tmp_path)) == 4
    assert len({r["run_id"] for r in rows_of(tmp_path)}) == 4


def test_resume_refuses_a_different_config(tmp_path):
    """Two configs merged into one results file is the expensive kind of wrong:
    the numbers still look fine."""
    run.sweep([case(1)], tmp_path, CONFIG, ask=FakeAsk())
    with pytest.raises(ValueError, match="model"):
        run.sweep([case(1)], tmp_path, run.Config(repeats=2, model="other"),
                  ask=FakeAsk())


def test_the_config_is_recorded_alongside_the_results(tmp_path):
    run.sweep([case(1)], tmp_path, CONFIG, ask=FakeAsk())
    saved = json.loads((tmp_path / "config.json").read_text())
    assert saved["model"] == "claude-haiku-4-5"


def test_one_failing_case_does_not_stop_the_sweep(tmp_path):
    ask = FakeAsk(raise_on=["q1"])
    run.sweep([case(1), case(2)], tmp_path, CONFIG, ask=ask)
    rows = rows_of(tmp_path)
    assert len(rows) == 4
    failed = [r for r in rows if r["case_id"] == "c1"]
    assert all("boom" in r["error"] for r in failed)
    assert all(r["error"] is None for r in rows if r["case_id"] == "c2")


def test_a_failed_run_is_not_treated_as_a_retrieval_miss(tmp_path):
    """A harness crash says nothing about retrieval. Scoring it as a miss would
    make an infrastructure problem look like an agent problem."""
    run.sweep([case(1, gold=["Marie Curie"])], tmp_path,
              run.Config(repeats=1), ask=FakeAsk(raise_on=["q1"]))
    row = rows_of(tmp_path)[0]
    assert row["error"] is not None
    assert row["gold_shown"] is None


def test_a_failed_run_is_retried_on_resume(tmp_path):
    """Errored runs are the ones most likely to be transient; leaving them
    permanently 'done' would bake a network blip into the results."""
    run.sweep([case(1)], tmp_path, run.Config(repeats=1), ask=FakeAsk(raise_on=["q1"]))
    retry = FakeAsk()
    run.sweep([case(1)], tmp_path, run.Config(repeats=1), ask=retry)
    assert len(retry.calls) == 1
    rows = rows_of(tmp_path)
    assert len(rows) == 1
    assert rows[0]["error"] is None


# --- artifacts for reading and bucketing ------------------------------------

def test_rows_are_readable_without_the_case_file(tmp_path):
    """A results row that doesn't carry its own question can't be reviewed
    without joining it back to the case set by hand."""
    run.sweep([case(1)], tmp_path, run.Config(repeats=1), ask=FakeAsk())
    row = rows_of(tmp_path)[0]
    assert row["question"] == "q1"
    assert row["expected"] == "e"
    assert "case_notes" in row


def test_review_renders_every_run_for_a_human(tmp_path):
    ask = FakeAsk()
    run.sweep([case(1, gold=["Marie Curie"])], tmp_path, CONFIG, ask=ask)
    text = (tmp_path / "review.md").read_text()
    assert "c1#0" in text and "c1#1" in text
    assert "q1" in text          # the question
    assert "Answer." in text     # the answer, in full
    assert "Marie Curie" in text  # what came back


def test_review_shows_whether_the_gold_article_was_shown(tmp_path):
    """The single most useful thing when triaging: did this fail upstream at
    retrieval, or downstream with the right evidence in hand?"""
    run.sweep([case(1, gold=["Nope"])], tmp_path, run.Config(repeats=1),
              ask=FakeAsk())
    assert "MISS" in (tmp_path / "review.md").read_text()


def test_review_surfaces_errors(tmp_path):
    run.sweep([case(1)], tmp_path, run.Config(repeats=1),
              ask=FakeAsk(raise_on=["q1"]))
    assert "boom" in (tmp_path / "review.md").read_text()


def test_review_is_rebuilt_from_the_results_on_resume(tmp_path):
    with pytest.raises(KeyboardInterrupt):
        run.sweep([case(1), case(2)], tmp_path, CONFIG, ask=FakeAsk(hard_stop_after=2))
    run.sweep([case(1), case(2)], tmp_path, CONFIG, ask=FakeAsk())
    text = (tmp_path / "review.md").read_text()
    assert all(f"c{c}#{r}" in text for c in (1, 2) for r in (0, 1))


def test_labels_are_seeded_one_row_per_run(tmp_path):
    """Hand-labelling is the read pass. Seeding the file means the reviewer
    fills blanks instead of transcribing run ids."""
    run.sweep([case(1)], tmp_path, CONFIG, ask=FakeAsk())
    labels = [json.loads(ln) for ln in
              (tmp_path / "labels.jsonl").read_text().splitlines() if ln.strip()]
    assert [row["run_id"] for row in labels] == ["c1#0", "c1#1"]
    assert all(row["verdict"] == "" and row["stage"] == "" for row in labels)


def test_hand_written_labels_are_never_overwritten(tmp_path):
    """The expensive artifact in this project is human judgement. A resumed
    sweep that reseeded the file would silently erase an hour of it."""
    run.sweep([case(1)], tmp_path, run.Config(repeats=1), ask=FakeAsk())
    path = tmp_path / "labels.jsonl"
    path.write_text(json.dumps(
        {"run_id": "c1#0", "verdict": "incorrect", "stage": "evidence",
         "note": "right article, fact not in intro"}) + "\n")

    run.sweep([case(1), case(2)], tmp_path, run.Config(repeats=1), ask=FakeAsk())
    labels = {json.loads(ln)["run_id"]: json.loads(ln)
              for ln in path.read_text().splitlines() if ln.strip()}
    assert labels["c1#0"]["verdict"] == "incorrect"
    assert labels["c1#0"]["note"] == "right article, fact not in intro"
    assert labels["c2#0"]["verdict"] == ""  # new run seeded blank


def test_the_default_output_directory_names_the_case_set():
    """Two sweeps over different sets must not land in directories that differ
    only by a timestamp."""
    out = run._default_out(run.Config(), "evals/cases/core.jsonl")
    assert "core" in out.name


# --- the judge seam ---------------------------------------------------------

def test_rows_say_explicitly_that_no_judge_ran(tmp_path):
    """Absent is not the same as passed. Until the judge is built and aligned,
    every row must say so rather than leave the field missing."""
    run.sweep([case(1)], tmp_path, CONFIG, ask=FakeAsk())
    row = rows_of(tmp_path)[0]
    assert row["judge"] is None
    assert row["config"]["judge_model"] is None


def test_judge_output_is_recorded_with_its_identity(tmp_path):
    class Judge:
        model = "claude-sonnet-5"
        version = "j1"

        def __call__(self, case, trace):
            return {"correctness": "correct"}

    run.sweep([case(1)], tmp_path, run.Config(repeats=1), ask=FakeAsk(), judge=Judge())
    row = rows_of(tmp_path)[0]
    assert row["judge"] == {"correctness": "correct"}
    assert row["config"]["judge_model"] == "claude-sonnet-5"
    assert row["config"]["judge_version"] == "j1"


# --- the summary ------------------------------------------------------------

def test_a_summary_is_written(tmp_path):
    run.sweep([case(1)], tmp_path, CONFIG, ask=FakeAsk())
    assert (tmp_path / "summary.md").exists()


def test_the_summary_is_rebuilt_from_the_results_on_resume(tmp_path):
    """Regenerating from the file, not from in-memory state, is what makes a
    resumed sweep's summary cover the whole sweep."""
    with pytest.raises(KeyboardInterrupt):
        run.sweep([case(1), case(2)], tmp_path, CONFIG, ask=FakeAsk(hard_stop_after=2))
    run.sweep([case(1), case(2)], tmp_path, CONFIG, ask=FakeAsk())
    assert "4" in (tmp_path / "summary.md").read_text()


def test_retrieval_recall_states_its_denominator():
    """Recall over 'cases with a gold article', never over all cases."""
    rows = [
        {"case_id": "c1", "gold_shown": True, "gold_fetched": True, "error": None,
         "searched": True, "n_turns": 2, "input_tokens": 1, "output_tokens": 1,
         "latency_s": 0.1, "cited_titles": ["A"]},
        {"case_id": "c2", "gold_shown": None, "gold_fetched": None, "error": None,
         "searched": True, "n_turns": 2, "input_tokens": 1, "output_tokens": 1,
         "latency_s": 0.1, "cited_titles": []},
    ]
    text = run.summarize(rows, CONFIG)
    line = next(ln for ln in text.splitlines() if "shown" in ln.lower())
    # 1/2 would mean the case with no gold article had been counted as a miss.
    assert "1/1" in line


def test_the_summary_separates_fetched_from_shown():
    """The over-fetch margin is only useful if the summary surfaces it."""
    rows = [
        {"case_id": "c1", "gold_shown": False, "gold_fetched": True, "error": None,
         "searched": True, "n_turns": 2, "input_tokens": 1, "output_tokens": 1,
         "latency_s": 0.1, "cited_titles": []},
    ]
    text = run.summarize(rows, CONFIG)
    assert "top_k" in text


def test_the_summary_buckets_cases_by_how_often_retrieval_worked():
    """3/3, 1-2/3 and 0/3 need different responses: solid, flaky, systematic."""
    rows = [
        {"case_id": "solid", "gold_shown": True, "gold_fetched": True, "error": None,
         "searched": True, "n_turns": 2, "input_tokens": 1, "output_tokens": 1,
         "latency_s": 0.1, "cited_titles": []},
        {"case_id": "flaky", "gold_shown": True, "gold_fetched": True, "error": None,
         "searched": True, "n_turns": 2, "input_tokens": 1, "output_tokens": 1,
         "latency_s": 0.1, "cited_titles": []},
        {"case_id": "flaky", "gold_shown": False, "gold_fetched": False, "error": None,
         "searched": True, "n_turns": 2, "input_tokens": 1, "output_tokens": 1,
         "latency_s": 0.1, "cited_titles": []},
        {"case_id": "broken", "gold_shown": False, "gold_fetched": False, "error": None,
         "searched": True, "n_turns": 2, "input_tokens": 1, "output_tokens": 1,
         "latency_s": 0.1, "cited_titles": []},
    ]
    text = run.summarize(rows, CONFIG)
    assert "flaky" in text
    assert "broken" in text


def test_the_summary_reports_errors_and_excludes_them_from_rates():
    rows = [
        {"case_id": "c1", "gold_shown": None, "gold_fetched": None,
         "error": "RuntimeError: boom", "searched": False, "n_turns": 0,
         "input_tokens": 0, "output_tokens": 0, "latency_s": 0.0, "cited_titles": []},
        {"case_id": "c2", "gold_shown": True, "gold_fetched": True, "error": None,
         "searched": True, "n_turns": 2, "input_tokens": 1, "output_tokens": 1,
         "latency_s": 0.1, "cited_titles": []},
    ]
    text = run.summarize(rows, CONFIG)
    assert "1" in text
    assert "1/1" in text  # searched rate over the one run that completed


def test_the_summary_says_correctness_is_unmeasured_without_a_judge():
    """The most dangerous summary is one that reads like a score when nothing
    scored the answers."""
    rows = [
        {"case_id": "c1", "gold_shown": True, "gold_fetched": True, "error": None,
         "searched": True, "n_turns": 2, "input_tokens": 1, "output_tokens": 1,
         "latency_s": 0.1, "cited_titles": []},
    ]
    text = run.summarize(rows, CONFIG).lower()
    assert "no judge" in text or "not measured" in text


def test_summarize_handles_an_empty_sweep():
    assert run.summarize([], CONFIG)
