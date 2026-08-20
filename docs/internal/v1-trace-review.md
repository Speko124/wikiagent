# V1 trace review — what `fetch_article` bought and what it cost

> **Note on numbers.** This review was written before the metric contract in
> `project.md` §3.7 was adopted. Its correctness figures use the earlier
> denominator, which excluded unresolved runs and so read a few points high.
> The analysis and the per-run findings are unaffected; for current headline
> numbers see `results/*-summary.md`.

54 curated runs · `claude-haiku-4-5` · prompt `v1` · `top_k` 3 · 3× per case.
Sources: `results/v1-curated/traces/`, `results/v1-curated/results.jsonl`,
compared run-by-run against `results/v0-curated/`. Holdout untouched.

Every claim below is anchored to a trace file and the exact rendered text the
model saw. Where the trace cannot settle a cause, that is stated rather than
guessed.

---

## 0. Headline

| | V0 | V1 |
|---|---|---|
| Judge `correct` | 29/54 | **36/54** |
| Judge `incorrect` | 2 | **1** |
| Cases with 3/3 judged `correct` | 9 | **12** |
| Judge `unclear` | 2 | 3 |
| Judge `declined` | 21 | 13 |
| Search calls | 82 | 79 |
| Fetch calls | 0 | 22 |
| Runs reaching the 10-turn cap | 0 | **1** |
| Input tokens (total) | 210,686 | 395,943 |
| Input tokens excl. `arpanet` | 192,921 | 240,792 |
| Median latency | 3.38 s | **3.14 s** |
| Mean answer length | 496 ch | **439 ch** |

Of the 5 body-fact cases: **2 fully fixed** (`head-of-class-eric`,
`home-alone-toy-store`, both 0/3 → 3/3), **1 answered from the fetched body but
unscorable** because the case spec is wrong (`beat-bobby-flay-wins`, §1.4),
**2 still fail** — one expected (`lets-make-a-deal-location`) and one not
(`arpanet-first-message`, §1.5). The 12 cases that already passed were untouched:
zero fetches between them. The blow-up is confined to `arpanet`, which absorbs
**155,151 of V1's 395,943 input tokens** (39%) across three runs.

Tool-call accounting outside `arpanet`: searches 75 → 60, fetches 0 → 15. A
clean 1:1 swap of a flailing second search for a fetch, converting six failures
into six wins with no net increase in tool calls.

---

## 1. Did the fix work?

### 1.1 `head-of-class-eric` — fixed, 0/3 → 3/3

V0 never saw the fact. `head-of-class-eric--r0.json` (V0) burned four searches,
two of them on invented character names, and ended by asking the user a
question. Turn 2 narration and action do not even match:

> TEXT: `...Let me try searching for "Eric Forman" or other specific character names from the show.`
> CALL: `search_wikipedia("Samuel \"Chip\" Testa Head of the Class\"")`

Neither name exists in the show. That search returned `William Finn`, a
composer. Final answer: *"I cannot definitively answer who played Eric... Would
you like me to search for a different aspect of the show?"*

V1, all three runs: one search, one fetch, correct answer in 3 turns.
`head-of-class-eric--r1.json` turn 1:

> TEXT: `Let me fetch the full article about Head of the Class to find information about the character Eric.`
> CALL: `fetch_article("Head of the Class")` → 7,850 chars

`Brian Robbins` sits at **offset 3,041** of that text — i.e. ~1,500 chars past
where V0's intro was cut:

> `A notable development in the show was the relationship between Simone and Eric Mardian (Brian Robbins), an aspiring writer and, outwardly, the most unlikely member of the IHP.`

Two modes fixed at once. The **memory-seeded query** mode is gone: V1's three
queries are `Head of the Class`, `Head of the Class TV series`,
`Head of the Class TV show`. No invented names in any run. Cost fell too:
r0 went 18.3 s → 4.6 s and 12,004 → 7,133 input tokens.

### 1.2 `home-alone-toy-store` — fixed, 0/3 → 3/3

V0's failure had a second mode stacked on it. `home-alone-toy-store--r2.json`
(V0) is **distractor adoption + hedge-then-assert** in one paragraph:

> `FAO Schwarz is a real toy store in New York City where scenes from Home Alone 2 were filmed. This appears to be the toy store featured in the movie. However, the search results don't explicitly confirm this connection in the text provided. ... The answer is **FAO Schwarz**`

V1, all three runs: one search, `fetch_article("Home Alone 2: Lost in New York")`
(8,025 chars), correct. `Duncan` first appears at **offset 2,860**:

> `The next day, Kevin visits Duncan's Toy Chest, a big toy store and meets its kind-hearted owner Mr. Duncan.`

The distractor adoption did not recur. Answers are shorter than V0's
(193–217 output tokens vs 239–303).

### 1.3 `lets-make-a-deal-location` — still fails, but the trace does **not** prove infobox-only is the reason

Expected to fail, and it does, 0/3. `Raleigh` appears nowhere in the fetched
text of any of the three runs — verified by string search over
`lets-make-a-deal-location--r{0,1,2}.json`.

**But the stated cause is not what the trace shows.** The fetch returned
**7,542 chars ending in `[...]`** — it was cut at the `ARTICLE_CHARS = 8_000`
cap, mid-way through `== Broadcast history ==`, which is the *first* section of
the article. The model never reached Gameplay, Production, or anything after.
So the trace is consistent with two different causes:

- (a) the answer is infobox-only, as `core.jsonl` asserts, or
- (b) the answer is in prose past the 8,000-char cap.

The trace cannot distinguish them, and `cache/` stores only the post-truncation
extract, so it cannot either. The case is currently doing its job by accident:
it marks "the fix's limit", but which limit — extract format or byte cap — is
undetermined. **Recommend**: re-verify by hand against the live article before
citing this case as the infobox boundary.

### 1.4 `beat-bobby-flay-wins` — the case premise is wrong; V1 answers it

`core.jsonl` says *"Not stated anywhere as a figure; it would have to be counted
across per-season episode tables."* That is false. The fetched article body
states it outright, in all three runs (`beat-bobby-flay-wins--r{0,1,2}.json`):

> `Through 528 competitions, Bobby Flay's record for the show is 330-198, a win percentage of 62.5%.`

The judge then marked all three `unclear`, correctly reasoning against a stale
reference (`beat-bobby-flay-wins#2`: *"the reference itself appears incomplete
or outdated"*). This is an **eval-spec bug, not a model failure** — the case
should be re-specced with `answer_contains: [["330"]]` or similar.

Note the article's per-season tables render as empty headers in the plaintext
extract — `=== Season 1 === === Season 2 === ... === Season 43 ===` with no
content — so the fetch is only 2,236 chars. The **aggregation over tables**
limitation is real and visible; it just is not what makes this question
unanswerable.

Secondary finding: 2 of 3 runs resolve "how many times has **he** won" to the
*contestants*, not to Flay. r0 leads with *"Bobby Flay has **lost 198 times**"*;
r2 with *"**contestants have won 198 times**"*. Only r1 covers both readings.
Ambiguity silently resolved, and to the less natural reading.

### 1.5 `arpanet-first-message` — still 0/3, and much more expensive

The premise in `core.jsonl` is *"this should fail at V0 and be fixed by a
full-page fetch."* The fetch is **not** a full page. `fetch_article("ARPANET")`
returned **7,916 chars ending in `[...]`** in all three runs. `Kline` and `"lo"`
are absent from every byte the model saw. The escalation reached the right
article, opened it, and the cap put the answer out of reach anyway.

What happened instead was a thrash. Turn counts: **9, 9, 10**. Every other run
in the sweep, V0 and V1, is 1–4 turns.

- **r0** (`arpanet-first-message--r0.json`): 6 searches + 2 fetches. Turns 3, 6
  and 7 re-search and get the ARPANET intro back — the article it had already
  opened at turn 2. It never notices the loop.
- **r1**: 6 searches + 2 fetches. The one place the fetch earned its keep:
  `fetch_article("Project Genie")` supplied `The first message sent on the
  internet (then ARAPNET) was sent by Charley Kline, a student of Leonard
  Kleinrock at UCLA using a Sigma 7 computer in October 1969.` The answer is
  correctly grounded and correctly attributed — it just isn't `"lo"`.
- **r2**: **hit `MAX_TURNS = 10` and produced no answer at all.**
  `trace.error = "Stopped after 10 turns without a final answer."` The judge row
  has `verdict: null`. This is a new class of outcome: not a wrong answer, no
  answer.

Cost: 3,210–9,077 → 47,275–59,240 input tokens per run (≈10×); 3.3–7.5 s →
15.8–16.2 s latency. Not justified — it bought zero correctness.

---

## 2. What the new tool introduced or broke

### 2.1 Escalation precision is excellent — the one unambiguous win

**Zero wasted fetches.** All 22 fetch calls landed on the 6 cases whose intros
demonstrably lacked the answer (5 body-fact + `beethoven`). The 12 cases that
already passed in V0 issued **0 fetches between them**. Verified per run: for
every fetch, the target string was absent from all preceding search output.

| Case | target string | in prior search text | in fetch |
|---|---|---|---|
| head-of-class-eric ×3 | `Brian Robbins` | no | **yes** |
| home-alone-toy-store ×3 | `Duncan` | no | **yes** |
| beat-bobby-flay-wins ×3 | `330-198` | no | **yes** |
| beethoven ×3 | `mammoth` | no | **yes** |
| lets-make-a-deal ×3 | `Raleigh` | no | no |

The one-line prompt delta did what it said: escalate only when the right article
is named and its intro is insufficient.

### 2.2 NEW MODE — absence asserted from a truncated fetch

This is the most important thing the tool introduced, and it is a *grounding*
regression, not a retrieval one.

**6 of the 9 distinct articles fetched came back cut at the 8,000-char cap**
(`ARPANET` 7,916 · `History of the Internet` 8,012 · `Head of the Class` 7,850 ·
`Home Alone 2` 8,025 · `Let's Make a Deal` 7,542 · `Symphony No. 5` 7,721 — all
ending in `[...]`).

**8 runs then asserted the fact is absent from *the article*, with no mention
that the text was cut.** Examples:

- `lets-make-a-deal-location--r0.json`: *"The Wikipedia article doesn't contain
  specific information about the filming location for 2018"* — after reading 7,542
  of an article that visibly continued.
- `arpanet-first-message--r2.json` turn 3: *"The ARPANET article doesn't contain
  specific details about the first message."* Per `core.jsonl`, it does. The model
  read 7,916 chars and reported on the whole article.

In V0 the model was *precise* about this — it consistently blamed "the opening
section" (11 statements across 7 V0 runs, e.g. `home-alone-toy-store--r0.json`:
*"doesn't specify the toy store name in the opening section"*). V1 lost that
precision the moment "the article" became something it believed it had read.

The closest V1 ever gets to acknowledging the cut is oblique and only on
`arpanet`:

- r0 turn 6: *"The History of the Internet article is very long."*
- r0 final: *"...that level of detail in the opening sections or accessible portions of the History of the Internet or ARPANET articles."*
- r2 turn 7: *"The History of the Internet article is long but doesn't seem to have the specific details..."*

"Long" is being used as a reason to give up, not as a signal that more text
exists. The `[...]` marker is still **never** explicitly named — the V0 finding
stands, and now has higher stakes because the escalation ladder has no rung
above `fetch_article`.

### 2.3 NEW MODE — turn-budget exhaustion with no answer

`arpanet-first-message--r2.json` is the first run in either sweep to hit
`MAX_TURNS = 10`. `MAX_TURNS` did not change between V0 and V1; the turn
distribution did:

| n_turns | 1 | 2 | 3 | 4 | 5 | 9 | 10 |
|---|---|---|---|---|---|---|---|
| V0 | 3 | 30 | 18 | 2 | 1 | – | – |
| V1 | 3 | 28 | 18 | 2 | – | **2** | **1** |

Identical everywhere except the three `arpanet` runs. The second tool doubles
the branching factor when neither tool is working, and there is nothing in the
prompt telling the model when to stop escalating.

### 2.4 NEW MODE — tool confusion in narration

One instance. `arpanet-first-message--r2.json` turn 9:

> TEXT: `Let me try searching for the Timeline of internet history, which might have more specific details.`
> CALL: `fetch_article("Timeline of the history of the Internet")`

Says search, calls fetch. Zero instances of the reverse. Small, but it is the
narration/action mismatch mode reappearing *specifically at the tool-selection
boundary the fix created*.

### 2.5 Regression: `am-i-all-alone-writer` r1 — distractor fully adopted

The one V0-correct → V1-incorrect flip. **Not fetch-related** — `n_fetches: 0`
in all three runs — so it is either the prompt delta or sampling noise; the
trace cannot separate them.

V0, all three runs, explicitly rejected the near-title distractor:

> `Neither of these is "Am I All Alone or Is It Only Me."` (`--r2`, V0)
> `However, that's not quite the same title as what you're asking about.` (`--r1`, V0)

V1 r1 states the distractor as the answer with **no hedge at all**:

> `Based on the search results, the song "All Alone Am I" was **written by Manos Hadjidakis**, a Greek composer.`

Judge: *"addresses a different song ... and fabricates an answer instead of
reporting it wasn't found."* r0 and r2 hedge but still **lead** with the
distractor before disclaiming — softer than V0's ordering, which led with the
rejection.

Persistence also fell: V0 issued 1, 2, 1 searches (r0 tried a second query);
V1 issued 1, 1, 1. This case is scored on `n_searches`, so it got worse on its
own metric.

### 2.6 Regression: one ungrounded memory claim

`lets-make-a-deal-location--r1.json` final answer:

> `In general, the show has been filmed in Los Angeles in recent years, but I cannot confirm this specifically for 2018`

`Los Angeles`, `Angeles`, `California` and `Hollywood` appear in **no tool output
in that run**. Direct violation of *"Answer only from what the search results
say. Never fill a gap from memory."* V0's equivalent runs made
Los-Angeles claims too but grounded them — `Los Angeles` is present in the tool
output of both V0 `--r1` (via `The Prospect Studios`) and V0 `--r2` (via `CBS`).
This is the only ungrounded proper noun in the 12 fetch-bearing V1 runs, and the
verbatim-quote check over all 54 V1 runs turned up nothing else.

### 2.7 Not a regression, though the scoreboard says otherwise

`beethoven-premiere-attendance` r0 flipped `correct` → `declined`. Judge label
noise on identical substance: V0 *"correctly reports that attendance figures are
not recorded"*, V1 *"correctly reports that no attendance figure is recorded ...
but this counts as a decline."* Behaviour actually **improved** — V0 took 2–3
searches and drifted to a different article, V1 takes 1 search + 1 fetch and
answers in 3 turns from the gold article, and V0's false-success preamble
leakage (*"Good! I found information about the premiere concert. ... Let me
search that article title more specifically."* leaked verbatim into the V0 r0
final answer) is gone.

### 2.8 Cost and latency

| | V0 | V1 | Δ |
|---|---|---|---|
| Input tokens, all | 210,686 | 395,943 | +88% |
| Input tokens, excl. `arpanet` | 192,921 | 240,792 | +25% |
| Output tokens, excl. `arpanet` | 11,118 | 10,804 | **−3%** |
| Median latency, all | 3.38 s | 3.14 s | **−7%** |
| Total wall time, excl. `arpanet` | 193.8 s | 163.0 s | **−16%** |

Two separable costs:

1. **Fixed overhead, paid on all 54 runs** for the extra tool schema + prompt
   line, whether or not it is used: `paris-weather` 916 → 1,180 (+264);
   `rosetta-year` 2,415 → 2,963 (+548); `switzerland-borders` 2,333 → 2,882
   (+549). ~+300–550 input tokens/run. Cheap, and justified.
2. **`arpanet`**, which alone accounts for 155,151 input tokens (39% of the V1
   total) and 48 s of the 211 s wall clock, for zero correctness. Not justified.

Everything else got cheaper and faster, because a successful fetch replaces two
or three failing searches. `head-of-class-eric#0`: 18.3 s → 4.6 s, 12,004 →
7,133 input tokens.

---

## 3. New modes not previously catalogued

1. **Absence asserted from a truncated fetch** (§2.2) — 8 runs. The headline new
   mode. V0 was precise about reading only intros; V1 reports on "the article"
   after reading 8,000 of its bytes.
2. **Turn-budget exhaustion producing no answer** (§2.3) — 1 run
   (`arpanet--r2`). New outcome class: the harness records
   `error: "Stopped after 10 turns without a final answer."` and the judge row
   carries `verdict: null`, so it does not appear as a failure in any
   correctness count. It silently shrinks the denominator.
3. **Tool confusion in narration** (§2.4) — 1 run. Says "search", calls
   `fetch_article`.
4. **Escalation loop with no stopping rule** (§2.3) — `arpanet` r0/r1/r2 all
   re-search queries whose top hit is an article they have already fetched.
   Nothing in the prompt says "you have already opened this; stop".
5. **Renderer inconsistency across fetch results** — `Home Alone 2` came back
   with `pageid: -1` (stale cache entry, `cache_hit: true`, `latency_s: 0.0`),
   which takes the `render()` branch that omits the `[N] Title (id N)` header.
   The model saw `Home Alone 2: Lost in New York\n<text>` where every other
   fetch showed `[1] Title (id N)\n<text>`. No behavioural harm observed, but
   the model sees two different shapes from one tool.
6. **Trace schema gap** — `ToolCall.query` holds the *title* for a fetch and the
   `pageid` argument is never recorded (`wikiagent/trace.py:20`). The whole
   point of the `pageid` parameter is immunity to capitalisation, and there is
   no way to audit from the traces whether the model ever uses it.

---

## 4. Explicit negatives — categories checked, zero instances

- **Fetch with no preceding search.** Zero. All 22 fetches used a title that had
  appeared in a search result earlier in the same run (checked exhaustively).
- **Failed fetches.** Zero. `failed_fetches: 0` on all 54 rows; no fetch
  rendered `Search failed:` or `No Wikipedia articles matched`.
- **Hallucinated / mis-capitalised titles.** Zero. Every fetched title is a
  byte-exact copy of a shown search-result title.
- **Wasted fetches** (intro already had the answer). Zero — table in §2.1.
- **Over-fetching outside `arpanet`.** Zero. Every non-`arpanet` run that
  fetched, fetched exactly once.
- **Over-trusting long article text.** Zero fabrications. Every proper noun and
  number in the 12 fetch-bearing runs' answers was present in that run's tool
  output, with one exception (`Los Angeles`, §2.6) — and that run's claim was
  explicitly flagged by the model as unconfirmed. All quoted strings verified
  verbatim across all 54 runs; the only mismatches are a curly apostrophe
  (`world’s` vs `world's`, `bologna-oxford-older`) and the model silently fixing
  a typo in the source (`Nagaro Scarecrow village` → `Nagoro`,
  `straw-doll-village--r0`). Both also present in V0.
- **Answered without searching.** Only `paris-weather` (×3), which is correct
  behaviour for that case. Same as V0.
- **8,000-char text crowding out the model / degrading answers.** No evidence.
  Mean answer length fell 496 → 439 chars; output tokens excl. `arpanet` fell
  3%. Long fetches produced *shorter, more direct* answers.

### Known V0 modes — changed / unchanged

| Mode | Status in V1 |
|---|---|
| Body-fact failure | **Fixed** where the fact is within 8,000 chars (2 of 3 cases) |
| Memory-seeded queries | **Gone** on `head-of-class-eric`; no instances anywhere in V1 |
| Distractor adoption | **Gone** on `home-alone`; **worse** on `am-i-all-alone-writer` (§2.5) |
| Hedge-then-assert | Gone on `home-alone`; persists on `am-i-all-alone-writer` r0/r2 |
| Infobox-only data | Unresolved, and its evidence is now confounded by the byte cap (§1.3) |
| Aggregation over tables | Real and visible (empty `=== Season N ===` headers), but not what breaks `beat-bobby-flay` (§1.4) |
| Ambiguity silently resolved | Persists — `beat-bobby-flay` r0/r2 pick "contestants" for "he" |
| Off-mission verbosity | Persists — `paris-weather` ×3 still lists Weather.com / AccuWeather |
| Ending by asking the user a question | 4 → 5 runs. Gone from `head-of-class-eric`; new on `tesla-origin#0` (*"Which Tesla were you asking about?"*) |
| False-success preambles | Roughly flat, redistributed. Final answers 2 → 3 (`straw-doll` r0/r1 *"Perfect! The answer is..."*, `einstein-nobel-control#1` *"Perfect! I found the answer."*); mid-turn 1 → 4, all 4 on `arpanet` and all attached to fetch decisions |
| Attribution imprecision | Persists — `switzerland-borders#0` attributes the full five-country list to `Switzerland–European Union relations`; `home-alone#2` cites `Home Alone` for `Home Alone 2: Lost in New York` |
| `[...]` marker never acknowledged | Persists, and now matters more (§2.2) |
| Answered from memory | 1 new instance (§2.6); 0 in V0 curated |

---

## 5. Runs worth a human read

1. **`arpanet-first-message--r2.json`** — the 10-turn no-answer run. Read it end
   to end. It is the single clearest picture of what the second tool does when
   neither tool can succeed.
2. **`beat-bobby-flay-wins--r0.json`** (any repeat) — the fetched text contains
   `Through 528 competitions, Bobby Flay's record for the show is 330-198`. The
   case spec says no such figure exists. Fix the spec.
3. **`lets-make-a-deal-location--r0.json`** — check whether `Raleigh` is in the
   article prose past 7,542 chars or only in the infobox. The whole "this case
   marks the limit of the fix" claim rests on the answer.
4. **`am-i-all-alone-writer--r1.json`** vs its V0 counterpart — the only
   correct→incorrect flip, and the only run where a distractor is asserted with
   no hedge whatsoever.
5. **`lets-make-a-deal-location--r1.json`** — the `Los Angeles` sentence. One
   ungrounded claim in 54 runs, but it is the failure mode the whole system is
   built to prevent.
6. **`arpanet-first-message--r1.json`** — the counter-example worth keeping:
   escalation working correctly (`Project Genie` → `Charley Kline`), grounded and
   correctly attributed, still the wrong answer. Shows that "fetch found
   something real" and "the question got answered" are separate events.

---

## 6. What this implies for V2

Stated as leads, not decisions.

1. **The 8,000-char cap is now the binding constraint**, not the tool's
   existence. 6 of 9 fetched articles hit it. `arpanet` fails *because* of it.
   Options: raise it, make it section-addressable, or return a section index
   first. Any of these is a bigger change than V1 was — worth a separate
   decision.
2. **Teach the model what `[...]` on a fetch means.** The prompt already says
   "Very long articles are cut short, marked with `[...]`" in
   `fetch_description`, and the model still asserts absence from truncated text
   in 8 runs. The tool description is not enough; the *answering* block needs a
   rule: never say "the article does not contain X" when the text you read ended
   in `[...]`.
3. **Add a stopping rule.** Nothing tells the model it has already opened an
   article. Three runs re-searched their way back to a page they had fetched.
4. **`MAX_TURNS` exhaustion must surface as a failure**, not as a `null` judge
   verdict that silently leaves the denominator.
5. **Two case specs are wrong**: `beat-bobby-flay-wins` (the figure exists),
   and `lets-make-a-deal-location`'s stated cause (confounded by the byte cap).


---

## Verified after the review (by the maintainer, not the reviewing agent)

Two of this review's claims were checked against live Wikipedia because both
contradicted something previously recorded as verified. Both held, and both
overturn a case note.

**`lets-make-a-deal-location` is not an infobox case.** "Raleigh Studios"
appears in the article *prose*, at offset ~15,650 of a 44,579-character
article — past the 8,000-char fetch cap. The test that "asserted" the infobox
claim was circular: it checked that the string was absent from text `fetch`
had already truncated, so it would have passed wherever the fact lived. A test
that cannot fail for the stated reason is not evidence.

**`beat-bobby-flay-wins` does not require aggregation.** The fetched article
states it outright — *"Through 528 competitions, Bobby Flay's record for the
show is 330-198, a win percentage of 62.5%"* — in all three V1 runs, in text
that was **not** truncated (2,236 chars). The agent had the figure on screen
and declined anyway. Its 0/3 stands, as an extraction failure rather than a
retrieval limit.

Both case specs and dimensions were corrected, and both arms re-graded from
saved traces so V0 and V1 are scored against the same corrected definitions.

**What this changes about the V1 conclusion.** The two remaining systematic
failures were recorded as *outside* the fix's reach by design. Neither is. One
is the char cap, one is extraction. Both are addressable — which makes the V1
result better than reported and the remaining work clearer.
