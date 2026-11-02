"""Safety filter for the human rating set. Reads saved page text and addresses only, no tool output.

A page leaves the rating set if its address or text points to gambling, adult or piracy content,
or its site uses a domain ending we treat as high risk. The rule was written before it was applied.
Pages it removes stay in the other evaluations; this protects volunteers and nothing else.

  python -m poc.final_rater_safety_filter
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from poc.final_page_filter import visible_text

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "evaluations" / "2026-11-final"
# Our judgement of endings often used for throwaway sites; not a published list.
RISKY_ENDINGS = frozenset("xyz top club icu buzz site online click link work gq tk ml cf ga loan win bid mom".split())
DOMAIN_TERMS = re.compile(
    r"casino|bet\d|\dbet|betting|gambl|poker|slot|lotto|porn|xxx|sex|escort|hentai|jav|torrent|warez|pharma|pills?\b|\d{2,}"
)
TEXT_TERMS = {
    "gambling": "casino casinos betting sportsbook jackpot poker roulette baccarat gambling",
    "adult": "porn porno xxx nude nudes escort escorts hentai onlyfans",
    "piracy": "torrent torrents warez keygen cracked",
}
TEXT_HITS_MIN = 3


def text_category(text: str) -> tuple[str, int] | None:
    words = re.findall(r"[a-z]+", text.lower())
    for category, terms in TEXT_TERMS.items():
        vocabulary = set(terms.split())
        hits = sum(w in vocabulary for w in words)
        if hits >= TEXT_HITS_MIN:
            return category, hits
    return None


def domain_reason(host: str) -> str | None:
    host = host.lower().removeprefix("www.")
    if host.rsplit(".", 1)[-1] in RISKY_ENDINGS:
        return "risky_domain_ending"
    if DOMAIN_TERMS.search(host):
        return "risky_domain_name"
    return None


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pages-dir", type=Path, default=ROOT / "data" / "final")
    p.add_argument("--out", type=Path, default=EVAL / "rater_safety_filter.json")
    args = p.parse_args()
    kept = json.loads((EVAL / "page_filter.json").read_text(encoding="utf-8"))["kept_ids"]
    removed, safe = [], []
    for pid in kept:
        meta = json.loads((args.pages_dir / f"{pid}.meta.json").read_text(encoding="utf-8"))
        host = re.sub(r"^https?://", "", meta["url"]).split("/")[0]
        html = (args.pages_dir / f"{pid}.html").read_text(encoding="utf-8", errors="replace")
        reason = domain_reason(host)
        hit = None if reason else text_category(visible_text(html))
        if hit:
            reason = f"text_{hit[0]}"
        if reason:
            removed.append({"id": pid, "host": host, "reason": reason, "hits": hit[1] if hit else None})
        else:
            safe.append(pid)
    args.out.write_text(
        json.dumps({"n_input": len(kept), "n_safe": len(safe), "removed": removed, "safe_ids": safe}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"removed {len(removed)} of {len(kept)}")
    for r in removed:
        print(" ", r["id"], r["host"], r["reason"], r["hits"])


if __name__ == "__main__":
    main()
