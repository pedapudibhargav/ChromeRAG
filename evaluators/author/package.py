#!/usr/bin/env python3
"""Build the zip a rater receives: the app, one bundle, and the instructions with its item count.

Usage:
  python -m evaluators.author.package --bundle bundle.json --out page-rating.zip
"""

from __future__ import annotations

import argparse
import json
import math
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "evaluators"
TEXT_FILES = {"START_HERE.txt": EV / "START_HERE.txt", "ABOUT_THIS_STUDY.txt": EV / "ABOUT_THIS_STUDY.txt",
              "HANDOUT.md": EV / "HANDOUT.md"}


def hours_text(n_items: int) -> str:
    """2 to 4 minutes per item, low end rounded, high end rounded up, to half hours."""
    low = max(0.5, round(n_items * 2 / 60 * 2) / 2)
    high = math.ceil(n_items * 4 / 60 * 2) / 2
    fmt = lambda h: f"{h:g}"  # noqa: E731
    return f"{fmt(low)} to {fmt(high)}"


def build(bundle_path: Path, out: Path) -> int:
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    n = len(bundle["items"]) + len(bundle["calibration"])
    fill = {"{N_ITEMS}": str(n), "{HOURS}": hours_text(n)}
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, src in TEXT_FILES.items():
            text = src.read_text(encoding="utf-8")
            for k, v in fill.items():
                text = text.replace(k, v)
            z.writestr(f"page-rating/{name}", text)
        z.write(EV / "run.py", "page-rating/evaluators/run.py")
        for sub in ("static", "demo"):
            for f in sorted((EV / sub).rglob("*")):
                if f.is_file() and f.name != ".DS_Store":
                    z.write(f, f"page-rating/evaluators/{sub}/{f.relative_to(EV / sub)}")
        z.write(bundle_path, "page-rating/evaluators/bundle/bundle.json")
    return n


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    n = build(a.bundle, a.out)
    print(f"{a.out}: {n} items, about {hours_text(n)} hours")


if __name__ == "__main__":
    main()
