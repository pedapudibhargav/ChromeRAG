#!/usr/bin/env python3
"""Build the zip a rater receives: the app, one bundle, and the instructions with its item count.

Usage:
  python -m evaluators.author.package --bundle bundle.json --out page-rating.zip [--practice-notes notes.json]
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


def build(bundle_path: Path, out: Path, practice_notes: Path | None = None) -> int:
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    if practice_notes is not None:
        # A note per practice item, shown after the rater scores it. Practice items are not analysed.
        notes = json.loads(practice_notes.read_text(encoding="utf-8"))
        cal = {it["item_id"]: it for it in bundle["calibration"]}
        unknown = sorted(set(notes) - set(cal))
        if unknown:
            raise SystemExit(f"practice notes for items that are not practice items: {unknown}")
        for iid, note in notes.items():
            cal[iid]["practice_note"] = note
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
        z.writestr("page-rating/evaluators/bundle/bundle.json", json.dumps(bundle))
    return n


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--practice-notes", type=Path, default=None, help="JSON: practice item id to note")
    a = p.parse_args(argv)
    n = build(a.bundle, a.out, a.practice_notes)
    print(f"{a.out}: {n} items, about {hours_text(n)} hours")


if __name__ == "__main__":
    main()
