# V1b trace review — repeat sweep vs V1

Compares `results/v1b-curated/` (54 runs) against the identical prior sweep `results/v1-curated/` (54 runs), with `results/v0-curated/` as the no-fetch baseline. Same model (`claude-haiku-4-5`), same 18 cases x 3 repeats, same top_k=3.

**Caveat on "identical".** Every v1b trace carries `prompt_digest: c243201bc72665bb`. **No v1 trace carries a digest field at all** (`prompt_digest` is absent from all 54 v1 traces and from `results/v1-curated/results.jsonl`). Prompt identity between the two sweeps is therefore asserted by the runner config, not verifiable from the stored artifacts. Everything below assumes it holds.

One thing did change between sweeps and it is not the agent: the `expected` string for `beat-bobby-flay-wins` was rewritten (see §E3). That is the sole source of the headline score movement.

---

## Headline

| | v0 | v1 | v1b |
|---|---|---|---|
| judge `correct` | 29 | 36 | **39** |
| `declined` | 21 | 13 | 13 |
| `incorrect` | 2 | 1 | 1 |
| `unclear` | 2 | 3 | 1 |
| no answer produced | 0 | 1 | 0 |
| deterministic `answer_match` | 28/45 | **39/45** | **39/45** |

`answer_match` is bit-identical between v1 and v1b (39/45). The +3 in judge `correct` is exactly the three `beat-bobby-flay-wins` runs, and it is caused by the reference rewrite, not by the agent.

---

## A. Stable vs noisy, case by case

Per run I compared: judge verdict, the full tool-call sequence (tool + arguments, in order), the byte-level `rendered` text each call returned, and the answer text.

**14 of 18 cases are verdict-stable across both sweeps (42/42 runs).** They are:
`rosetta-year`, `eiffel-height`, `tosca-nationality`, `bologna-oxford-older`, `tesla-origin`, `straw-doll-village`, `einstein-nobel-premise`, `einstein-nobel-control`, `turing-nobel`, `switzerland-borders`, `head-of-class-eric`, `home-alone-toy-store` (all `correct` 3/3 in both), plus `paris-weather` and `beethoven-premiere-attendance` (`declined` 3/3 in both — the intended behaviour for those two).

**4 cases contain the 7 flipped runs.**

| case | run | v1 → v1b | flip is in |
|---|---|---|---|
| `beat-bobby-flay-wins` | r0, r1, r2 | `unclear` → `correct` | **the grader only.** Tool output byte-identical, answers semantically identical. See §E3. |
| `am-i-all-alone-writer` | r1 | `incorrect` → `declined` | tool use (different query string) **and** answer wording |
| `am-i-all-alone-writer` | r2 | `declined` → `unclear` | **answer wording only** — tool sequence and returned bytes are identical |
| `lets-make-a-deal-location` | r0 | `declined` → `incorrect` | tool use (3 calls → 2) **and** answer content (new ungrounded guess) |
| `arpanet-first-message` | r2 | no answer → `declined` | tool use — v1 spent all 10 turns on tools, v1b answered on turn 10 |

Excluding the grader-driven trio, **4 runs flipped for model reasons, and all 4 sit in the three cases where the target answer is not reachable from what the tools returned** (`am-i-all-alone-writer`: no such article exists; `lets-make-a-deal-location`: fact past the 8000-char cap; `arpanet-first-message`: fact never retrieved). The 13 cases with a reachable answer flipped zero times in 39 runs.

### The flip that isolates answer-only variance

`am-i-all-alone-writer` r2 is the cleanest datapoint in the sweep: identical single tool call, identical returned bytes, different answer, different verdict.

- `results/v1-curated/traces/am-i-all-alone-writer--r2.json` → *"I found information about 'All Alone Am I,' which appears to be the closest match to your query. **However, I'm not finding an exact match for 'Am I All Alone or Is It Only Me.'**"* → `declined`
- `results/v1b-curated/traces/am-i-all-alone-writer--r2.json` → *"the song 'All Alone Am I' (**which appears to be what you're asking about**) was **written by Manos Hadjidakis**"* — the no-exact-match caveat is gone entirely → `unclear`

Both runs issued `search_wikipedia("Am I All Alone or Is It Only Me song")` and got back the same five titles (`All Alone Am I`, `I Am Woman`, `All Alone Am I (album)`, `I Am Me`, `Me. I Am Mariah...`). The whole difference is whether the substitution is flagged. Across all six runs of this case the *behaviour* is constant — search, find the near-title, substitute it — and only the hedge strength moves. The case is specced to be scored on `n_searches`, which went 1/1/1 (v1) → **2**/1/1 (v1b): persistence improved in exactly one run out of three.

### Surface wording is never stable

Answer text was **identical in 0 of 54 run pairs**; median character-level similarity 0.39. Any metric that keys off answer phrasing (including an LLM judge) inherits that.

---

## B. Variance floor

- **Verdict flips between two identical sweeps: 7/54 (13%). Model-driven: 4/54 (7.4%)**, the other 3 being the reference rewrite.
- **Tool-call sequences differ in 22/54 run pairs (41%)** — different query strings, different call counts, or both. 32/54 were identical.
- **Deterministic `answer_match` differed in 0/54.** `answer_completeness` differed in 0/54. The only other deterministic fields that moved were cosmetic: `cites_any_retrieved` (3 runs) and `escalated` (1 run).

**Practical floor.** At 3 repeats/case a case that moves 1 of 3 runs is indistinguishable from noise — that is precisely the observed pattern. A claimed improvement needs to exceed **~4 runs (7%) of net movement**, i.e. roughly **two whole cases flipping all three repeats**, before it can be attributed to the change rather than to sampling. Below that, report it as unresolved.

**Where the floor is not uniform.** Variance is concentrated, not spread: 0/39 flips on cases with a reachable answer, 4/12 flips on cases without one. So a change targeting easy retrieval can be measured at 3 repeats; a change targeting abstention/unanswerable behaviour cannot, and needs more repeats or an answer-shape rubric rather than a free-text judge.

---

## C. New failure modes in v1b

Two genuinely new instances, and one escalation of a v1 mode. All three sit on the same root cause: the agent does not treat the `[...]` marker as information.

### C1. Affirmatively false claim of having read a full article (new)

`results/v1b-curated/traces/arpanet-first-message--r2.json`, final answer:

> "However, **the opening sections and even the full articles I accessed** do not contain information about the specific content of the first message transmitted."

Both fetches in that run were truncated. Turn 3 `fetch_article("ARPANET")` returned 7,916 chars ending `"...came to the attention of the ARPA investigators at this conference. [...]"`; turn 7 `fetch_article("History of the Internet")` returned 8,012 chars ending `"...such as PLATO at the University of Illinois Chicago. [...]"`. The model never saw a full article, and says it did.

No v1 answer makes this claim. The nearest v1 statement is correctly hedged — `results/v1-curated/traces/arpanet-first-message--r0.json`: *"my searches haven't turned up an article with that level of detail in the opening sections **or accessible portions** of the History of the Internet or ARPANET articles."*

### C2. Truncation noticed mid-trace, then dropped from the answer (new)

`results/v1b-curated/traces/arpanet-first-message--r0.json`, turn 7 assistant text:

> "**The article was cut short.** Let me search for more specific information about the first ARPANET transmission or message."

This is the **only** truncation acknowledgement anywhere in either sweep — a regex for `cut short|cut off|truncat|\[...\]|partial|excerpt` over all 108 traces' turn texts and answers returns nothing else. And it does not survive: the same run's final answer says *"the specific content of the first message is not mentioned in the Wikipedia articles I found"* with no caveat. The model can see the cut; it just doesn't carry it into the conclusion. Note the tool offers no continuation or offset argument, so even a model that fully registers the cut has no move available.

### C3. Ungrounded named-entity guess appended to a decline (escalation, not new)

`results/v1b-curated/traces/lets-make-a-deal-location--r0.json`:

> "Based on what's commonly known about the show, it has been filmed at **CBS Television City in Los Angeles** during its recent years, but I cannot confirm this specifically for 2018 based on the Wikipedia sources available."

`"CBS Television City"`, `"Television City"` and `"Los Angeles"` appear in the answer and in **none** of the run's tool output. It is also wrong (gold: Raleigh Studios Hollywood), which is why the verdict moved `declined` → `incorrect`.

The mode itself existed in v1 — `results/v1-curated/traces/lets-make-a-deal-location--r1.json`: *"In general, the show has been filmed in **Los Angeles** in recent years, but I cannot confirm this specifically for 2018"*, likewise absent from that run's evidence. v1b escalated from a vague region to a named studio. Report this as one mode present in both sweeps at 1/3 frequency, not as a regression.

### Categories with zero instances in v1b

Checked explicitly, all empty: **no** turn-budget exhaustion (0/54, vs 1/54 in v1); **no** API errors (0, vs 1 in v1); **no** failed fetches (0 in both); **no** duplicate queries within a run (0 in both); **no** runaway or oscillating loops; **no** cited article outside the retrieved set (0 in both); **no** case where the agent skipped searching other than `paris-weather` (3/3 in both sweeps, which is correct); **no** hallucinated figures outside `lets-make-a-deal-location` r0 — spot-checks of `switzerland-borders` (Liechtenstein, Italy, Austria, 572 km, 362 km) and `straw-doll-village` (350 dolls, 400 dolls, 25 residents, January 2026, Tsukimi Ayano) found every claim present verbatim in the rendered evidence.

---

## D. Cost and turn structure

| | v0 | v1 | v1b |
|---|---|---|---|
| searches | 82 | 79 | 79 |
| fetches | 0 | 22 | 22 |
| runs with ≥1 fetch | 0 | 18 | 19 |
| turns median / mean / max | 2 / 2.41 / 5 | 2 / 2.76 / 10 | 2 / 2.81 / 10 |
| input tokens | 210,686 | 395,943 | 399,011 |
| output tokens | 12,045 | 13,226 | 13,320 |
| latency median | 3.38 s | 3.14 s | 3.21 s |

Cost is flat between the two sweeps (+0.8% input tokens). The real cost step is v0 → v1: **adding `fetch_article` nearly doubled input tokens (+88%) for +11 `answer_match`.**

**Turns by fetch count (v1b).** 0 fetches: 35 runs, mean 2.11 turns. 1 fetch: 16 runs, mean 3.12. 2 fetches: 3 runs, mean **9.33**. The distribution is bimodal, not graded — a run either resolves in 2–3 turns or blows out to 9–10. All three of the 9–10-turn runs are `arpanet-first-message`, in both sweeps.

**Turn budget.** `arpanet-first-message` sits on the ceiling in all six runs across both sweeps: 9, 9, 10 turns in v1 and 9, 9, 10 in v1b. In v1 r2 all ten turns had `stop_reason: tool_use` and the run produced no answer. In v1b r2 the tenth turn was `end_turn` — it answered on the last turn it had. The failure did not recur, but the margin is zero: one extra tool call in that run and it exhausts again.

**Fetches per run:** 0 in 35 runs, 1 in 16, 2 in 3. Of 22 fetches, **19 came back truncated** (v1: 17/22). The three untruncated ones are all `beat-bobby-flay-wins` (2,236 chars).

**Wasted / redundant work.** Zero exact-duplicate queries in either sweep, and zero searches returning no new title in v1b (v1 had one: `arpanet-first-message` r2, `"UCLA Stanford first ARPANET connection 1969"`). The waste is subtler — **re-delivery of already-seen snippets**: 24 of 237 shown result slots in v1b (10%; v1: 27/237) repeat a title already shown to the model in the same run, costing 29,545 of 235,234 evidence chars (13%). Concentrated in `arpanet-first-message`: 6/18, 5/18, 9/21 repeat slots. The `ARPANET` intro alone is re-shown 4–6 times per run there.

**The unexplored lead.** In all six `arpanet-first-message` runs across both sweeps, `Leonard Kleinrock` was returned as a **top-3 search result** (1–3 separate times per run) and was **never fetched**. Fetches went to `ARPANET` and `History of the Internet` (and in v1 also `Project Genie`, `Timeline of the history of the Internet`). Whether that article would have contained the answer cannot be determined from these traces — the trace only stores the capped extract of what was actually fetched — but the agent's escalation policy is demonstrably "fetch the article whose title matches the topic", not "fetch the person who did the thing".

---

## E. The five prior findings, re-checked

### E1. Absence asserted from truncated text — REPRODUCES, slightly worse

Counting rule: the run made ≥1 `fetch_article` whose `rendered` contained `[...]`, and the final answer asserts the fact is absent from "the article"/"Wikipedia".

- **v1: 8 runs** — `beethoven-premiere-attendance` r0/r1/r2, `lets-make-a-deal-location` r0/r1/r2, `arpanet-first-message` r0 (hedged) and r1. (r2 produced no answer, so it cannot be counted.) This matches the prior finding's count of 8.
- **v1b: 9 runs** — the same six `beethoven` + `lets-make-a-deal` runs, plus all three `arpanet` runs (r2 now produces an answer, and it is the false-full-article claim of §C1).

Only **1 of the 9** contains any truncation acknowledgement, and it is wrong in the other direction: `arpanet` r1's *"more detailed historical sources that Wikipedia doesn't include in these opening sections"* — it did full-fetch, truncated, not just read openings.

A tenth technical instance in v1b: `turing-nobel` r1 fetched `Alan Turing` (7,956 chars, truncated) and concludes no Nobel. It is the case's correct answer and the reasoning is designed to rest on absence, so I list it separately rather than folding it in.

Adjacent and worth naming: `turing-nobel` r0 and r2 in v1b assert *"Based on the Wikipedia article on Alan Turing, **there is no mention** of him receiving a Nobel Prize"* having seen **only the 1500-char search intro** — no fetch at all. Same epistemic error, weaker evidence base, present identically in v1.

### E2. Turn-budget exhaustion — DOES NOT RECUR

0/54 in v1b. `results/v1b-curated/traces/arpanet-first-message--r2.json` reached MAX_TURNS=10 but the tenth turn was `end_turn` and produced an 806-char answer; the v1 run of the same case had `tool_use` on all ten. No other case exceeded 4 turns in either sweep. As noted in §D the margin is one tool call, and it is the same case both times.

### E3. `beat-bobby-flay-wins` — the agent did NOT change; the reference did

The prior write-up ("in v1 all 3 runs declined anyway", "the agent had the figure on screen and still declined") is not what the traces show. **All three v1 runs extracted the figure**:

- v1 r0: *"through 528 competitions, Bobby Flay's record is 330-198, meaning he has won 330 times"*
- v1 r1: *"Bobby Flay has won **330 times** (with a win percentage of 62.5%)"*
- v1 r2: *"The article states: 'Through 528 competitions, Bobby Flay's record for the show is 330-198, a win percentage of 62.5%.'"*

`answer_match` was already **true in all three v1 runs**. The v1 verdict was `unclear`, never `declined`.

**Tool output is byte-identical between sweeps.** All six runs: one search then `fetch_article("Beat Bobby Flay")` returning **2,236 chars, untruncated**, MD5-identical across sweeps, containing *"Through 528 competitions, Bobby Flay's record for the show is 330-198, a win percentage of 62.5%."* Total evidence seen: 3,614 chars in all six runs. (v1b r0 used the query `"Beat Bobby Flay"` where v1 r0 used `"Beat Bobby Flay television show"` — different string, same top-3, same bytes.)

**What actually changed is the case's `expected` field:**

- v1: `"Not stated anywhere as a figure; it would have to be counted across per-season episode tables."`
- v1b: `"330 wins (record 330-198 through 528 competitions, a 62.5% win percentage), stated in the article body."`

The v1 judge said so in as many words — *"The reference claims no figure exists, but the answer provides a specific sourced statistic (330-198) which may actually be accurate... making this a case where the reference itself appears incomplete or outdated."* The v1 `unclear` was a **correct judge response to a wrong reference**, and the v1b `correct` is the same answer graded against a fixed one.

**Consequence:** this case is not evidence of an extraction failure, and it is not evidence of an improvement. The prior sweep's "the agent declined with the figure on screen" claim, and the case note in `evals/cases/core.jsonl` that says *"The agent had the figure on screen and still declined, so this is an extraction failure"*, are both contradicted by the traces and should be corrected. The +3 correct is a grader fix; the model's score on this case should be read as 3/3 in **both** sweeps.

### E4. `am-i-all-alone-writer` — 2 runs flipped, one on wording alone

Covered in §A. r2 flipped with a byte-identical tool trace, driven purely by whether the substitution was flagged. r1 flipped with a different query string and a caveat that appears in v1b and was absent in v1. Underlying behaviour — substitute the near-title `All Alone Am I` — is constant in 6/6 runs across both sweeps. `n_searches` moved 1/1/1 → 2/1/1.

### E5. `lets-make-a-deal-location` — CONFIRMED, and it is a hard cap failure

`"Raleigh"` appears **zero times** in the complete rendered tool output of **all six runs across both sweeps**. Each run's `fetch_article("Let's Make a Deal")` returned exactly 7,542 chars ending:

> "...where as of 2025 it serves as the lead out program for the serial Beyond the Gates. **[...]**"

Total evidence seen per run: 10,559 chars (2-call runs) or 14,616 chars (3-call runs), with 2 or 4 `[...]` markers respectively. The answer is genuinely absent from what the model saw. This case is a clean measurement of the 8000-char cap and nothing else — no prompt or reasoning change can fix it. (Same structure applies to `arpanet-first-message`: `"lo"` appears zero times in what any of the six runs saw; the five `"login"` hits are all the unrelated *"enabled remote login and file transfer"* sentence in the ARPANET intro.)

---

## Recommended reading of this sweep

1. **The +3 correct is not an improvement.** v1 and v1b are the same agent performing identically (`answer_match` 39/45 in both). Report v1b as a variance measurement, not a result.
2. **Fix the case record.** `beat-bobby-flay-wins` in `evals/cases/core.jsonl` still carries the contradicted "extraction failure" note and "Its V1 score of 0/3 stands". Both are wrong; it was 3/3 on `answer_match` in v1.
3. **Two live agent defects, both reproducing.** (a) Absence claimed from truncated text, 9/54 runs, only 1 with any caveat and that one misdescribed. (b) Ungrounded memory fallback appended to declines, 1/3 runs of `lets-make-a-deal-location` in both sweeps, escalating in specificity.
4. **Two constraints that no prompt change reaches.** The 8000-char cap (`lets-make-a-deal-location`, 6/6) and the retrieval miss (`arpanet-first-message`, 6/6). Both need a tool change — continuation/offset fetch, or targeted in-article search.
5. **Design future comparisons around a 4-run (7%) floor**, and around the observation that the floor is ~0 on answerable cases and ~1-in-3 on unanswerable ones.
