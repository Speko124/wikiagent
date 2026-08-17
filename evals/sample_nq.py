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

SEED = 20260816
N = 20

OUT = Path(__file__).parent / "cases" / "explore.jsonl"
PROVENANCE = Path(__file__).parent / "cases" / "explore.provenance.json"


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


def main() -> None:
    with httpx.Client(timeout=30.0) as client:
        head = client.get(
            API,
            params={"dataset": DATASET, "config": "nq_open", "split": SPLIT,
                    "offset": 0, "length": 1},
        )
        head.raise_for_status()
        total = head.json()["num_rows_total"]

        indices = sorted(random.Random(SEED).sample(range(total), N))
        rows = [_row(client, i) for i in indices]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w") as fh:
        for n, (index, row) in enumerate(zip(indices, rows), 1):
            fh.write(
                json.dumps(
                    {
                        "id": f"nq-{n:03d}",
                        "question": row["question"],
                        "expected": " | ".join(row["answer"]),
                        # Deliberately untagged beyond `explore`: the taxonomy
                        # comes out of reading these, not imposed before.
                        "dimensions": ["explore"],
                        "gold_articles": [],
                        "notes": (
                            f"NQ-open {SPLIT} row {index}, verbatim. Reference "
                            "answer is c.2018 and may be stale."
                        ),
                    }
                )
                + "\n"
            )

    PROVENANCE.write_text(
        json.dumps(
            {
                "dataset": DATASET,
                "config": "nq_open",
                "split": SPLIT,
                "license": "CC BY-SA 3.0",
                "seed": SEED,
                "n": N,
                "population_rows": total,
                "row_indices": indices,
                "note": "Every drawn row was kept. No filtering, no substitution.",
            },
            indent=2,
        )
        + "\n"
    )
    print(f"wrote {len(rows)} cases to {OUT}")


if __name__ == "__main__":
    main()
