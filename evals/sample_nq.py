"""Draw a frozen random sample of real user questions from Natural Questions.

Run once. The output is committed; nobody needs to run this again, and the seed
plus the drawn row indices are recorded so the draw can be reproduced.

**Why random, and why from real queries.** The curated cases test failure modes
we already thought of, so they can only confirm our own taxonomy. This sample
comes from a distribution we don't control — real anonymised Google queries,
which AmbigQA found are over 50% ambiguous. Nobody hand-writes a set like that.

**The discipline that makes it work:** every drawn row is kept. Dropping the
boring ones or the malformed ones puts our taxonomy straight back in, and the
boring ones are what give us the base rate. Questions are stored verbatim —
the missing capitals and absent question marks are the point, not noise.

Cases are tagged `explore` and nothing else. Categorising them now would be the
same mistake in a different place: the taxonomy is supposed to come *out* of
reading these, not be imposed on them first.

Source: Natural Questions (Kwiatkowski et al., 2019), `nq_open` config,
CC BY-SA 3.0. Reference answers date from ~2018 and some are stale — fine here,
since this set is read for failure modes rather than scored for accuracy.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import httpx

API = "https://datasets-server.huggingface.co/rows"
DATASET = "google-research-datasets/nq_open"
SPLIT = "train"

CASES = Path(__file__).parent / "cases"

# Each draw is a named, seeded, frozen sample. `exclude` names earlier draws
# whose rows must not reappear: a holdout that shares rows with the set we
# tuned against is not a holdout, and the overlap would be invisible later.
DRAWS = {
    "explore": {"seed": 20260816, "n": 20, "prefix": "nq", "exclude": []},
    "holdout": {"seed": 20260817, "n": 10, "prefix": "hd", "exclude": ["explore"]},
}


def _row(client: httpx.Client, index: int) -> dict:
    r = client.get(
        API,
        params={
            "dataset": DATASET,
            "config": "nq_open",
            "split": SPLIT,
            "offset": index,
            "length": 1,
        },
    )
    r.raise_for_status()
    return r.json()["rows"][0]["row"]


def _already_drawn(names: list[str]) -> set[int]:
    used: set[int] = set()
    for name in names:
        path = CASES / f"{name}.provenance.json"
        if not path.exists():
            raise SystemExit(f"{path} missing - draw {name!r} first")
        used.update(json.loads(path.read_text())["row_indices"])
    return used


def main(name: str = "explore") -> None:
    draw = DRAWS[name]
    seed, n, prefix = draw["seed"], draw["n"], draw["prefix"]
    excluded = _already_drawn(draw["exclude"])
    out = CASES / f"{name}.jsonl"
    provenance = CASES / f"{name}.provenance.json"

    with httpx.Client(timeout=30.0) as client:
        head = client.get(
            API,
            params={"dataset": DATASET, "config": "nq_open", "split": SPLIT,
                    "offset": 0, "length": 1},
        )
        head.raise_for_status()
        total = head.json()["num_rows_total"]

        pool = [i for i in range(total) if i not in excluded]
        indices = sorted(random.Random(seed).sample(pool, n))
        rows = [_row(client, i) for i in indices]

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as fh:
        for i, (index, row) in enumerate(zip(indices, rows), 1):
            fh.write(
                json.dumps(
                    {
                        "id": f"{prefix}-{i:03d}",
                        "question": row["question"],
                        "expected": " | ".join(row["answer"]),
                        # Deliberately untagged beyond `explore`: the taxonomy
                        # comes out of reading these, not imposed before.
                        "dimensions": [name],
                        "gold_articles": [],
                        "notes": (
                            f"NQ-open {SPLIT} row {index}, verbatim. Reference "
                            "answer is c.2018 and may be stale."
                        ),
                    }
                )
                + "\n"
            )

    provenance.write_text(
        json.dumps(
            {
                "dataset": DATASET,
                "config": "nq_open",
                "split": SPLIT,
                "license": "CC BY-SA 3.0",
                "draw": name,
                "seed": seed,
                "n": n,
                "excluded_draws": draw["exclude"],
                "excluded_rows": len(excluded),
                "population_rows": total,
                "row_indices": indices,
                "note": "Every drawn row was kept. No filtering, no substitution.",
            },
            indent=2,
        )
        + "\n"
    )
    print(f"wrote {len(rows)} cases to {out}")


if __name__ == "__main__":
    import sys

    main(sys.argv[1] if len(sys.argv) > 1 else "explore")
