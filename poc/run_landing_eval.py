"""Score every extractor on the landing-page corpus (company marketing sites).

Usage:
  python -m poc.landing_corpus --plan --fetch    # network
  python -m poc.run_landing_eval
  python -m poc.run_landing_eval --split dev
  python -m poc.run_landing_eval --split heldout --final
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from poc.landing_corpus import RAW, URLS
from poc.run_corpus_comparison import OUT, run

ROOT = Path(__file__).resolve().parents[1]
LANDING_OUT = OUT / "landing"
SPLIT_PATH = ROOT / "poc" / "landing_split.json"


def _companies_for_split(split: str) -> set[str] | None:
    if split == "all":
        return None
    split_data = json.loads(SPLIT_PATH.read_text(encoding="utf-8"))
    return set(split_data[split])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev", choices=["dev", "heldout", "all"])
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()

    if args.split == "heldout" and not args.final:
        parser.error("--split heldout requires --final")

    if args.split == "heldout":
        print("WARNING: final heldout evaluation — do not tune on this split.", file=sys.stderr)

    companies = _companies_for_split(args.split)
    listed = sum(
        len(c["pages"])
        for name, c in json.loads(URLS.read_text(encoding="utf-8"))["companies"].items()
        if companies is None or name in companies
    )
    report_name = f"landing_comparison_{args.split}"
    run(
        fetch=False,
        raw=RAW,
        out=LANDING_OUT,
        report_name=report_name,
        listed=listed,
        companies=companies,
    )


if __name__ == "__main__":
    main()
