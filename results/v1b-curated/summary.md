# Sweep summary

**Model** `claude-haiku-4-5` · **prompt** `v1` · **top_k** 3 · **tools** on · **repeats** 3 · **effort** —

**Runs** 54 total, 0 errored (errors are excluded from every rate below).

## Deterministic signals

- Searched at all: 51/54 (94%)
- Gold article shown to the model: 42/45 (93%) — denominator is runs whose case has a gold article
- Gold fetched but past top_k (raising top_k would have helped): 0
- Named a retrieved article: 46/54 (85%)
- Turns: median 2, max 10
- Tokens: 399,011 in / 13,320 out
- Latency: median 3.2s

## Retrieval by case

| case | gold shown | bucket |
|---|---|---|
| switzerland-borders | 0/3 | systematic |
| rosetta-year | 3/3 | solid |
| eiffel-height | 3/3 | solid |
| tosca-nationality | 3/3 | solid |
| bologna-oxford-older | 3/3 | solid |
| tesla-origin | 3/3 | solid |
| straw-doll-village | 3/3 | solid |
| arpanet-first-message | 3/3 | solid |
| einstein-nobel-premise | 3/3 | solid |
| einstein-nobel-control | 3/3 | solid |
| turing-nobel | 3/3 | solid |
| head-of-class-eric | 3/3 | solid |
| lets-make-a-deal-location | 3/3 | solid |
| home-alone-toy-store | 3/3 | solid |
| beat-bobby-flay-wins | 3/3 | solid |

## Not measured here

Judged by `claude-sonnet-5` rubric `j2`; see `results.jsonl`.
