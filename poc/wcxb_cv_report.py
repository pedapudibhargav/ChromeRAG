"""Table of WCXB dev results from the 5-fold, site-grouped cross-validation predictions.

Every ChromeRAG number comes from a model that never saw the page's site. Baseline numbers are
the frozen v0.1.2 per-page results (same pages). Predictions are produced by
``poc.wcxb_diag run --fold K`` with CHROMERAG_PRIORITY set; this script only scores them.

  python -m poc.wcxb_cv_report --pattern '/tmp/cr/cv_{priority}_{fold}.pkl' --out evaluations/.../wcxb_dev_cv.json
"""

from __future__ import annotations

import argparse
import json
import pickle
from collections import defaultdict
from pathlib import Path

from poc.wcxb import load_split, snippet_rate, word_f1

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "evaluations" / "2026-09-v0.1.2-baseline" / "wcxb_dev_v012_per_page.json"
TYPES = ("article", "forum", "product", "collection", "listing", "documentation", "service")
MODES = {"coverage": "chromerag_coverage", "balanced": "chromerag", "precision": "chromerag_precision"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", default="/tmp/cr/cv_{priority}_{fold}.pkl")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    pages = {p.id: p for p in load_split("dev")}
    rows: dict[str, dict] = {}
    for base in json.loads(BASELINE.read_text()):
        rows[base["id"]] = {"id": base["id"], "type": base["type"]} | {
            k: v for k, v in base.items() if k in ("trafilatura", "markitdown", "readability")
        }
    for priority, tool in MODES.items():
        for fold in range(5):
            path = Path(a.pattern.format(priority=priority, fold=fold))
            if not path.is_file():
                continue
            for pid, _url, _t, ours, _traf, ref in pickle.load(open(path, "rb")):
                p, r, f1 = word_f1(ours, ref)
                page = pages[pid]
                rows.setdefault(pid, {"id": pid, "type": page.page_type})[tool] = {
                    "p": p, "r": r, "f1": f1,
                    "with": snippet_rate(ours, page.with_snippets),
                    "without": snippet_rate(ours, page.without_snippets),
                }
    done = [r for r in rows.values() if "chromerag_coverage" in r]
    tools = [t for t in (*MODES.values(), "trafilatura", "readability", "markitdown") if any(t in r for r in done)]

    def mean(rs, tool, key):
        v = [r[tool][key] for r in rs if tool in r and r[tool].get(key) is not None]
        return sum(v) / len(v) if v else float("nan")

    by_type = defaultdict(list)
    for r in done:
        by_type[r["type"]].append(r)
    print(f"{len(done)} pages scored by held-out models\n")
    print(f"{'type':14s} {'n':>5s} " + " ".join(f"{t[:18]:>18s}" for t in tools))
    for t in (*TYPES, "ALL"):
        rs = done if t == "ALL" else by_type.get(t, [])
        print(f"{t:14s} {len(rs):5d} " + " ".join(f"{mean(rs, tool, 'f1'):18.3f}" for tool in tools))
    print("\nALL pages: precision / recall / with / without")
    for tool in tools:
        print(f"  {tool:22s} P {mean(done, tool, 'p'):.3f}  R {mean(done, tool, 'r'):.3f}  "
              f"with {mean(done, tool, 'with'):.3f}  without {mean(done, tool, 'without'):.3f}")
    if a.out:
        Path(a.out).write_text(json.dumps(done, indent=1))
        print("wrote", a.out)


if __name__ == "__main__":
    main()
