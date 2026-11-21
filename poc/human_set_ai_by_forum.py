"""Descriptive (not pre-registered): AI judge net preference on the 75 human-set pages, overall, forums only and
without forums.

Same unit, bootstrap (site, 10,000 draws, seed 20261120) and verdict mapping as the AI-judge block of
poc/human_set_analysis.py. Table S6 of evaluations/2026-11-final/SUPPLEMENT.md ("AI judges by subset") quotes it.

  PYTHONPATH=src:. python -m poc.human_set_ai_by_forum [--key KEY.json] [--bundle BUNDLE.json] --out ai_by_forum.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from poc import human_set_analysis as A

NOTE = ("Descriptive (not pre-registered): AI judge net preference on the 75 human-set pages, overall, forums only "
        "and without forums. Same unit, bootstrap and verdict mapping as poc/human_set_analysis.py.")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    A.add_input_args(ap)
    ap.add_argument("--out", type=Path, required=True, help="Output JSON file")
    args = ap.parse_args(argv)
    d = A.prepare(args)
    rep, cal, site, group = d["repeat_of"], d["cal"], d["item_site"], d["item_group"]
    item_of_page = {p: i for i, p in d["key_doc"]["page_of"].items() if i not in rep and i not in cal}
    subsets = (("overall", lambda i: True), ("forums_only", lambda i: group[i] == "forum"),
               ("without_forums", lambda i: group[i] != "forum"))
    out: dict = {"note": NOTE}
    for base in ("trafilatura", "readability"):
        for j in A.JUDGES:
            ai = {}
            for r in d["judges"][j]["judgements"]:
                if r["swapped"] or r["baseline"] != base:
                    continue
                ai[item_of_page[r["id"]]] = {"chromerag": "a", "baseline": "b"}.get(r["winner"], "tie")
            for name, keep in subsets:
                res = A.outcome_ci({i: v for i, v in ai.items() if keep(i)}, site)
                out[f"{base}/{j}/{name}"] = res
                print(f"{base:12s} {j:7s} {name:15s} n={res['n']:3d} {res['wins']}-{res['losses']}-{res['ties']} "
                      f"net {res['net']:+.2f} [{res['net_ci95'][0]:+.2f}, {res['net_ci95'][1]:+.2f}]")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
