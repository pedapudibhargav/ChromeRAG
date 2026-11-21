"""How the rating corpus was cut from the collection log. Reads the log only, no tool output.

Pages that passed are shuffled per site and at most two are kept. Seeds 20261104 (first sites)
and 20261106, 20261107 (forums) were used. The result, after the removals in
human_set/removed_after_review.json, is human_set/corpus_pages.json.
"""

from __future__ import annotations

import collections
import json
import random
from pathlib import Path


def cap_per_site(log_path: Path, seed: int, limit: int = 2) -> list[dict]:
    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    by_site: dict[str, list[dict]] = collections.defaultdict(list)
    for row in rows:
        if "id" in row:
            by_site[row["site"]].append(row)
    rng = random.Random(seed)
    kept: list[dict] = []
    for _, pages in sorted(by_site.items()):
        rng.shuffle(pages)
        kept.extend(pages[:limit])
    return kept
