"""Summarise the blind human ratings exported by apps/rating (human_ratings.csv).

  python -m poc.human_eval_analyze path/to/human_ratings.csv
"""

from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict

import numpy as np

TOOLS = ("chromerag", "trafilatura", "readability", "markitdown")


def ci(values: np.ndarray, iters: int = 5000) -> tuple[float, float, float]:
    rng = np.random.default_rng(0)
    bs = [values[rng.integers(0, len(values), len(values))].mean() for _ in range(iters)]
    return float(values.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def main(path: str) -> None:
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    pages: dict[str, dict] = {}
    for r in rows:
        p = pages.setdefault(r["item_id"], {"type": r["type"], "best": r["best_tool"], "skipped": r["skipped"] == "1", "scores": {}})
        if r["content"] and r["chrome"]:
            p["scores"][r["tool"]] = (int(r["content"]), int(r["chrome"]))
    rated = {k: v for k, v in pages.items() if not v["skipped"] and v["best"] != ""}
    ties = sum(1 for v in pages.values() if not v["skipped"] and v["best"] == "" )
    print(f"{len(pages)} pages, {len(rated)} with a pick, {ties} 'none/tie', {sum(v['skipped'] for v in pages.values())} skipped\n")
    c = Counter(v["best"] for v in rated.values())
    print("Picked best:")
    for t in TOOLS:
        x = np.array([1.0 if v["best"] == t else 0.0 for v in rated.values()])
        m, lo, hi = ci(x)
        print(f"  {t:12s} {c[t]:3d} / {len(rated)}  {m:.2f} [{lo:.2f}, {hi:.2f}]")
    by_type: dict[str, Counter] = defaultdict(Counter)
    for v in rated.values():
        by_type[v["type"]][v["best"]] += 1
    print("\nBy page type (picks):")
    for t, cnt in sorted(by_type.items()):
        print(f"  {t:14s} " + "  ".join(f"{k} {cnt[k]}" for k in TOOLS))
    print("\nMean scores (content kept / chrome left out, 1-5):")
    for t in TOOLS:
        cs = [v["scores"][t] for v in pages.values() if t in v["scores"]]
        if cs:
            a = np.array(cs)
            print(f"  {t:12s} content {a[:, 0].mean():.2f}  chrome {a[:, 1].mean():.2f}  (n={len(cs)})")
    for base in TOOLS[1:]:
        d = np.array([v["scores"]["chromerag"][0] + v["scores"]["chromerag"][1] - v["scores"][base][0] - v["scores"][base][1]
                      for v in pages.values() if "chromerag" in v["scores"] and base in v["scores"]], dtype=float)
        if len(d):
            m, lo, hi = ci(d)
            print(f"  ChromeRAG - {base:12s} (content+chrome) {m:+.2f} [{lo:+.2f}, {hi:+.2f}]  n={len(d)}")


if __name__ == "__main__":
    main(sys.argv[1])
