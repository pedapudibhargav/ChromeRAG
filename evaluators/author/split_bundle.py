#!/usr/bin/env python3
"""Split a built bundle into smaller part bundles that share a few anchor pages.

Every part keeps the same item ids, outputs and labels as the full bundle, so one key and one
analysis cover the full bundle and all parts together. Each part holds the practice items, the
anchor pages (rated by everyone), its own share of the other main pages (balanced by page type),
and any repeat item whose page is in that part.

Usage:
  python -m evaluators.author.split_bundle --bundle bundle.json --key key.json --seed N \\
    --parts 3 --anchors 5 --out-dir parts/ --out-plan author_only/part_plan.json
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path


def split_bundle(bundle: dict, key_doc: dict, *, seed: int, n_parts: int, n_anchors: int) -> tuple[list[dict], dict]:
    page_of = key_doc["page_of"]
    repeat_of = key_doc.get("repeat_of") or {}
    types = key_doc.get("page_types") or {}
    rng = random.Random(f"{seed}:parts")

    main = [it for it in bundle["items"] if it["item_id"] not in repeat_of]
    by_type: dict[str, list[dict]] = defaultdict(list)
    for it in sorted(main, key=lambda it: it["item_id"]):
        by_type[types.get(it["item_id"], "")].append(it)
    for t in sorted(by_type):
        rng.shuffle(by_type[t])

    # Anchors: one page from each of the largest types in turn, so they span page types.
    anchors: list[dict] = []
    order = sorted(by_type, key=lambda t: (-len(by_type[t]), t))
    while len(anchors) < n_anchors and any(by_type.values()):
        for t in order:
            if by_type[t] and len(anchors) < n_anchors:
                anchors.append(by_type[t].pop(0))

    # Deal the rest type by type, continuing the rotation, so each part gets a similar mix.
    own: list[list[dict]] = [[] for _ in range(n_parts)]
    turn = 0
    for t in order:
        for it in by_type[t]:
            own[turn % n_parts].append(it)
            turn += 1

    anchor_pages = {page_of[it["item_id"]] for it in anchors}
    parts = []
    plan = {"bundle_id": bundle["bundle_id"], "seed_note": "seed of the full bundle, salted ':parts'",
            "anchors": [it["item_id"] for it in anchors], "parts": {}}
    for i, items in enumerate(own, start=1):
        pages = anchor_pages | {page_of[it["item_id"]] for it in items}
        reps = [it for it in bundle["items"] if it["item_id"] in repeat_of and page_of[it["item_id"]] in pages]
        part = {
            "bundle_id": f"{bundle['bundle_id']}-part{i}",
            "calibration": bundle["calibration"],
            "items": anchors + items + reps,
        }
        parts.append(part)
        plan["parts"][f"part{i}"] = {
            "bundle_id": part["bundle_id"],
            "own": [it["item_id"] for it in items],
            "repeats": [it["item_id"] for it in reps],
            "n_items": len(part["calibration"]) + len(part["items"]),
        }
    return parts, plan


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--key", type=Path, required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--parts", type=int, default=3)
    p.add_argument("--anchors", type=int, default=5)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--out-plan", type=Path, required=True, help="Private: which items went to which part")
    a = p.parse_args(argv)
    bundle = json.loads(a.bundle.read_text(encoding="utf-8"))
    key_doc = json.loads(a.key.read_text(encoding="utf-8"))
    parts, plan = split_bundle(bundle, key_doc, seed=a.seed, n_parts=a.parts, n_anchors=a.anchors)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    for i, part in enumerate(parts, start=1):
        (a.out_dir / f"part{i}.json").write_text(json.dumps(part, ensure_ascii=False), encoding="utf-8")
    a.out_plan.parent.mkdir(parents=True, exist_ok=True)
    a.out_plan.write_text(json.dumps(plan, indent=1), encoding="utf-8")
    for name, info in plan["parts"].items():
        print(name, info["n_items"], "items;", len(info["own"]), "own pages;", len(info["repeats"]), "repeats")


if __name__ == "__main__":
    main()
