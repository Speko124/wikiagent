# Review worksheet

`claude-haiku-4-5` · prompt `v0` · top_k 3 · tools on · 11 runs

Read top to bottom and record verdicts in `labels.jsonl`. Full traces (raw tool results, per-turn thinking) are under `traces/`.

---

## `rosetta-year#0` — factual, single-hop

**Q** In what year was the Rosetta Stone discovered?

**Expected** 1799

*Why this case exists: Regression floor. Should pass 3/3; if it doesn't, every other result is noise.*

**Searched** (1): `Rosetta Stone`

**Shown** (gold SHOWN): Rosetta Stone, Rosetta Stone (software), Rosetta Stone (disambiguation)

**Fetched but not shown** (top_k=3): Rosetta Stone decree, Rosetta Stone (band)

**Answer**

> According to the Wikipedia article "Rosetta Stone," the stone was discovered in **July 1799** by French army officer Pierre-François Bouchard during France's invasion of Egypt.

*named: Rosetta Stone · 2 turns · 2,415 in / 99 out · 1.95s · [trace](traces/rosetta-year--r0.json)*

---

## `tosca-nationality#0` — multi-hop, bridge

**Q** What nationality was the composer of the opera Tosca?

**Expected** Italian (Giacomo Puccini)

*Why this case exists: Bridge join with both hops available in intros, so it isolates synthesis from retrieval.*

**Searched** (2): `Tosca opera` · `Giacomo Puccini composer`

**Shown** (gold SHOWN): Tosca, La Tosca, Tosca (2001 film), Giacomo Puccini, List of compositions by Giacomo Puccini, Domenico Puccini

**Fetched but not shown** (top_k=3): Opera (Tosca album), OperaLancaster, Turandot, Festival Puccini

**Answer**

> Based on the search results, the composer of the opera Tosca was **Giacomo Puccini**, and he was **Italian**. According to the Wikipedia article on Giacomo Puccini, he was "an Italian composer known primarily for his operas."

*named: Tosca, Giacomo Puccini · 3 turns · 5,183 in / 195 out · 4.841s · [trace](traces/tosca-nationality--r0.json)*

---

## `opera-house-seats#0` — deep-fact, abstention

**Q** How many seats does the Concert Hall at the Sydney Opera House have?

**Expected** 2,679. Verified present in the article body and absent from the intro, so with intro-only retrieval the honest answer is that the retrieved text does not say.

*Why this case exists: Intro-only stressor; feeds the fetch_article decision. Replaced a Leaning Tower of Pisa version whose step count turned out to BE in the intro - verified, not assumed.*

**Searched** (1): `Sydney Opera House Concert Hall`

**Shown** (gold SHOWN): Sydney Opera House, Sydney Symphony Orchestra, Sydney Opera House Grand Organ

**Fetched but not shown** (top_k=3): Nancye Hayes, Peter Hall (architect)

**Answer**

> According to the Wikipedia article on the Sydney Symphony Orchestra, the Concert Hall at the Sydney Opera House has a capacity of **2,679 seats**.

*named: Sydney Opera House, Sydney Symphony Orchestra · 2 turns · 2,767 in / 91 out · 3.156s · [trace](traces/opera-house-seats--r0.json)*

---

## `lovelace-breakfast#0` — unanswerable, abstention

**Q** What did Ada Lovelace eat for breakfast on her tenth birthday?

**Expected** Unknowable; Wikipedia does not record this. Correct behaviour is to search, then say so.

*Why this case exists: Posture, plus whether it searches first. Previously abstained from priors without searching.*

**Searched** (0): *did not search*

**Shown** (no gold article): —

**Answer**

> I don't have access to information about what Ada Lovelace ate for breakfast on her tenth birthday. Such personal details about daily meals from centuries ago would not typically be documented in historical records or encyclopedias like Wikipedia.
> 
> While I could search for biographical information about Ada Lovelace, the available historical sources would focus on her major life events, accomplishments, and documented biographical facts—not specific meals she ate on particular days.
> 
> Is there something else about Ada Lovelace's life or work that I could help you find information about?

*named: none · 1 turns · 922 in / 117 out · 1.844s · [trace](traces/lovelace-breakfast--r0.json)*

---

## `einstein-nobel-premise#0` — false-premise

**Q** Why did Albert Einstein win the Nobel Prize for the theory of relativity?

**Expected** False premise: the 1921 prize was awarded for the photoelectric effect, not relativity.

*Why this case exists: No matched control yet; see docs. An agent that rejects any odd-sounding premise would pass this.*

**Searched** (1): `Albert Einstein Nobel Prize`

**Shown** (gold MISS): Albert Einstein House, Albert Einstein Award, List of awards and honors received by Albert Einstein

**Fetched but not shown** (top_k=3): Outline of Albert Einstein, Mileva Marić

**Answer**

> According to the Wikipedia article "List of awards and honors received by Albert Einstein," Einstein did **not** win the Nobel Prize specifically for the theory of relativity. 
> 
> In 1922, Einstein was awarded the 1921 Nobel Prize in Physics "for his services to Theoretical Physics, and especially for his discovery of the law of the photoelectric effect." This refers to his 1905 paper on the photoelectric effect.
> 
> However, the presentation speech did mention that "his theory of relativity [had] been the subject of lively debate in philosophical circles [and] also has astrophysical implications which are being rigorously examined at the present time," so the theory of relativity was acknowledged, but the prize was formally awarded for his work on the photoelectric effect, not relativity.

*named: List of awards and honors received by Albert Einstein · 2 turns · 2,475 in / 228 out · 2.502s · [trace](traces/einstein-nobel-premise--r0.json)*

---

## `tesla-origin#0` — ambiguous-entity

**Q** Where is Tesla from?

**Expected** Ambiguous. Tesla, Inc. is American; Nikola Tesla was born in Smiljan (Austrian Empire, now Croatia). Correct behaviour names the ambiguity rather than silently picking one.

*Why this case exists: Term ambiguity: both readings answer the question sensibly.*

**Searched** (1): `Tesla`

**Shown** (gold SHOWN): Nikola Tesla, Tesla, Inc., Tesla Cybertruck

**Fetched but not shown** (top_k=3): Tesla, Tesla Roadster (first generation)

**Answer**

> The search results show information about both Nikola Tesla and Tesla, Inc., so I can answer both possibilities:
> 
> **Nikola Tesla** was from the **Austro-Hungarian Empire**, where he was born and raised. He was a Serbian-American engineer and inventor (1856-1943).
> 
> **Tesla, Inc.** (the electric vehicle company) is headquartered in **Austin, Texas**. It was incorporated in 2003 and is named as a tribute to inventor Nikola Tesla.

*named: Nikola Tesla · 2 turns · 2,833 in / 177 out · 2.698s · [trace](traces/tesla-origin--r0.json)*

---

## `eiffel-height#0` — factual, must-search

**Q** How tall is the Eiffel Tower?

**Expected** About 330 m (1,083 ft) including antennas.

*Why this case exists: The model certainly knows this. The graded signal is whether it searches anyway - if not, every grounding claim in the system is void.*

**Searched** (1): `Eiffel Tower`

**Shown** (gold SHOWN): Eiffel Tower, Gustave Eiffel, List of names on the Eiffel Tower

**Fetched but not shown** (top_k=3): Eiffel Tower replicas and derivatives, Eiffel Tower (disambiguation)

**Answer**

> According to the Wikipedia article "Eiffel Tower," the tower is **330 metres (1,083 feet) tall**. It's about the same height as an 81-storey building and is the tallest structure in Paris.

*named: Eiffel Tower · 2 turns · 2,799 in / 113 out · 2.668s · [trace](traces/eiffel-height--r0.json)*

---

## `turing-nobel#0` — negative-existence

**Q** Did Alan Turing ever receive a Nobel Prize?

**Expected** No.

*Why this case exists: Requires distinguishing 'not mentioned in the retrieved text' from 'did not happen'.*

**Searched** (1): `Alan Turing`

**Shown** (gold SHOWN): Alan Turing, Turing Award, Alan Turing: The Enigma

**Fetched but not shown** (top_k=3): Alan Turing law, Turing machine

**Answer**

> Based on the Wikipedia article about Alan Turing, there is no mention that he received a Nobel Prize. The article details his major accomplishments in theoretical computer science, cryptanalysis, and computing, but does not list a Nobel Prize among his honors.
> 
> It's worth noting that Alan Turing died in 1954, and the ACM A. M. Turing Award (often called the "Nobel Prize of Computing") was named after him and first awarded in 1966 — after his death. So he could not have received that award.

*named: Alan Turing, Turing Award · 2 turns · 2,739 in / 176 out · 2.554s · [trace](traces/turing-nobel--r0.json)*

---

## `straw-doll-village#0` — query-formulation, obscure

**Q** Which Japanese village is known for having more life-size straw dolls than residents?

**Expected** Nagoro (Iya Valley, Tokushima Prefecture).

*Why this case exists: No entity name in the question, so the agent has to construct the query rather than copy it.*

**Searched** (1): `Japanese village straw dolls residents`

**Shown** (gold SHOWN): Nagoro, Cremation in Japan, Fukushima Prefecture

**Fetched but not shown** (top_k=3): One Piece season 20, List of Hell Girl episodes

**Answer**

> The village is **Nagoro**, located in the Iya Valley in Miyoshi, Tokushima Prefecture on the island of Shikoku, Japan. According to the Wikipedia article on Nagoro, the village is now known as "Nagoro Doll Village" (Nagoro Kakashi-no-sato, meaning 'Nagoro Scarecrow village'). 
> 
> The dolls were created primarily by Tsukimi Ayano, who moved back to the village in the early 2000s and has made more than 400 life-size realistic dolls, with about 350 positioned throughout the village. This is particularly striking because the village's population has dwindled to just 25 residents as of January 2026, meaning there are far more dolls than people living there.

*named: Nagoro · 2 turns · 2,753 in / 243 out · 3.844s · [trace](traces/straw-doll-village--r0.json)*

---

## `paris-weather#0` — no-search-needed

**Q** What's the weather in Paris right now?

**Expected** Not answerable: this needs live data Wikipedia does not carry. Correct behaviour is to say so without searching.

*Why this case exists: Opposite pole to eiffel-height. Together they catch a prompt mis-tuned in either direction.*

**Searched** (0): *did not search*

**Shown** (no gold article): —

**Answer**

> I don't have access to real-time weather data. The search_wikipedia tool I have available searches for information in English Wikipedia, which contains encyclopedic articles but not current weather conditions.
> 
> To find the current weather in Paris, I'd recommend:
> - **Weather.com** or **Weather.gov** for detailed forecasts
> - **Google Weather** (search "weather Paris")
> - **Local news websites** for Paris weather
> - **Weather apps** on your phone
> 
> Is there something about Paris itself or weather patterns/climate in general that I could help you with using Wikipedia?

*named: none · 1 turns · 916 in / 126 out · 1.765s · [trace](traces/paris-weather--r0.json)*

---

## `switzerland-borders#0` — completeness, list

**Q** Which countries border Switzerland?

**Expected** All five: Germany, France, Italy, Austria, Liechtenstein.

*Why this case exists: Completeness, which binary correctness cannot see - a partial list presented as complete reads as a correct answer.*

**Searched** (1): `Switzerland borders`

**Shown** (gold MISS): France–Switzerland border, Germany–Switzerland border, Switzerland–European Union relations

**Fetched but not shown** (top_k=3): Italy–Switzerland border, Austria–Switzerland border

**Answer**

> Based on the Wikipedia article "Switzerland–European Union relations," Switzerland borders **five countries**:
> 
> 1. **France**
> 2. **Germany**
> 3. **Italy**
> 4. **Austria**
> 5. **Liechtenstein**
> 
> The search results confirm that Switzerland borders these four EU member states (Austria, France, Germany, and Italy) plus Liechtenstein, which is a microstate.

*named: Switzerland–European Union relations · 2 turns · 2,333 in / 145 out · 2.735s · [trace](traces/switzerland-borders--r0.json)*
