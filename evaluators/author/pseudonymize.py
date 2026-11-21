#!/usr/bin/env python3
"""Replace raters' chosen names with neutral codes before results are published.

Writes one copy of each results file with the name replaced by rater-01, rater-02, ... in a
random order, and a private map from codes back to files. The map must never be published.

Usage:
  python -m evaluators.author.pseudonymize --results returned/ --out public/ --out-map author_only/rater_map.json
"""

from __future__ import annotations

import argparse
import json
import secrets
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, required=True, help="Folder of returned results files")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--out-map", type=Path, required=True, help="Private: code to original file and name")
    a = p.parse_args(argv)
    paths = sorted(a.results.glob("*.json"))
    # A random order, so codes say nothing about who returned first or what they called themselves.
    order = sorted(paths, key=lambda _: secrets.randbits(64))
    a.out.mkdir(parents=True, exist_ok=True)
    mapping = {}
    for n, path in enumerate(order, start=1):
        code = f"rater-{n:02d}"
        res = json.loads(path.read_text(encoding="utf-8"))
        mapping[code] = {"file": path.name, "name": res.get("rater")}
        res["rater"] = code
        (a.out / f"{code}_{res.get('bundle_id', 'bundle')}.json").write_text(
            json.dumps(res, indent=2) + "\n", encoding="utf-8"
        )
    a.out_map.parent.mkdir(parents=True, exist_ok=True)
    a.out_map.write_text(json.dumps(mapping, indent=1) + "\n", encoding="utf-8")
    print(f"{len(order)} files written to {a.out}; private map at {a.out_map}")


if __name__ == "__main__":
    main()
