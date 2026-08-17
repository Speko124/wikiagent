# Prompt archive

Drafts that were replaced before any sweep ran against them. Kept for the
record of what changed and why, not for use — nothing here is selectable, and
no result in `results/` was produced by any of it.

---

## Pre-baseline draft (never run)

Written during Phase 2 and used only for a five-question demo. It was briefly
called `v0`, which was misleading: no eval was ever scored against it, so it
was never a baseline. Renamed away and archived when the real baseline was
promoted to `v0`.

**System prompt**

```
You answer questions using Wikipedia.

You have one tool, search_wikipedia, which returns the three best-matching articles and the opening section of each.

- Search before answering anything that depends on external facts.
- If a search misses, try again with different wording, a broader topic, or a related entity before giving up.
- Answer from what the search results actually say. Do not fill gaps from memory.
- Name the article or articles you drew on, in the text of your answer.
- If the results don't support an answer, say so plainly and say what you did find. Don't guess.
- If a question assumes something false, say what's wrong with the assumption instead of answering as asked.

Be direct and brief.
```

**Tool description**

```
Search English Wikipedia and return the {n} best-matching articles, each as its title followed by the opening section of that article.

Returns only the opening section, not the full article, so it answers questions about a topic's main facts better than questions about narrow details buried deep in an article.

Search terms work best as the name of the thing you are looking for — a person, place, event, or concept — rather than as a full question. If a search misses, try again with different or broader terms.
```

### Why it was replaced

Three defects, all of which would have distorted measurement rather than just
producing worse answers:

1. **It hardcoded the result count.** "the three best-matching articles" is
   stated in the system prompt while `top_k` is a tunable knob, so `--top-k 5`
   would have shipped a prompt that lies to the model about its own tool. The
   count now appears only in the tool description, which is built from the real
   value.

2. **"Name the article" didn't say how.** The model paraphrased — "articles on
   penicillin discovery" for *Discovery of penicillin* — and `cited_titles`
   matches retrieved titles exactly. This is why the deterministic
   fabricated-citation grader had to be dropped: it flagged honest answers.
   The baseline asks for exact titles as shown.

3. **The truncation marker was unexplained.** Extracts are cut at 1500
   characters and marked `[...]`, but nothing told the model what the marker
   meant, so "the article doesn't say" and "the text stopped here" were the
   same observation. One leads to false abstention, the other to a guess.

The replacement also reorganised a flat bullet list into three labelled blocks
matching funnel stages, so a failure at a stage points at one block to edit,
and added one behavioural line — *one subject per search* — from the single
multi-hop failure seen in the demo.
