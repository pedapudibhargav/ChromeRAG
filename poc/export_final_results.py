"""Collect the 0.1.3 evaluation results into one small file for the site and the paper figures.

Reads evaluations/2026-10-v0.1.3/ (WCXB dev cross-validation, frontier, final test, held-out and fresh
landing, judge, retrieval) and writes docs/data/final_results.json. Nothing is recomputed from raw HTML.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evaluations" / "2026-10-v0.1.3"
OUT = ROOT / "docs" / "data" / "final_results.json"
TOOLS = ("chromerag_coverage", "chromerag", "chromerag_precision", "trafilatura", "readability", "markitdown")
TYPES = ("article", "documentation", "service", "forum", "product", "collection", "listing")


def _means(rows: list[dict]) -> dict:
    out: dict = {}
    for scope in ("all", *TYPES):
        rs = rows if scope == "all" else [r for r in rows if r["type"] == scope]
        out[scope] = {"n": len(rs)}
        for t in TOOLS:
            vals = [r[t] for r in rs if t in r and isinstance(r[t], dict)]
            if vals:
                out[scope][t] = {k: float(np.mean([v[k] for v in vals if v.get(k) is not None])) for k in ("p", "r", "f1", "with", "without")}
    return out


def _boot(rows: list[dict], tool: str, base: str, scope: str = "all", iters: int = 5000) -> list[float]:
    rs = rows if scope == "all" else [r for r in rows if r["type"] == scope]
    d = np.array([r[tool]["f1"] - r[base]["f1"] for r in rs])
    rng = np.random.default_rng(0)
    bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(iters)]
    return [float(d.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]


def main() -> None:
    test = json.loads((EV / "FINAL" / "wcxb_test.json").read_text())
    dev = json.loads((EV / "wcxb_dev_cv.json").read_text())
    frontier = json.loads((EV / "wcxb_dev_frontier.json").read_text())
    judge = json.loads((EV / "FINAL" / "llm_judge_final.json").read_text())
    judge2 = json.loads((EV / "FINAL" / "llm_judge_wcxb_test.json").read_text())
    fresh_ret = json.loads((EV / "FINAL" / "fresh_retrieval_eval_report.json").read_text())
    thr = sorted({t for r in frontier for t in r["thr"]}, key=float)
    result = {
        "protocol": "word-level F1 against WCXB main_content; dev = 5-fold cross-validation grouped by site; test = model trained on all dev, scored once",
        "wcxb_test": {
            "means": _means(test),
            "bootstrap_vs_trafilatura": {t: _boot(test, t, "trafilatura") for t in TOOLS[:3]},
            "bootstrap_by_type_balanced": {s: _boot(test, "chromerag", "trafilatura", s) for s in TYPES},
        },
        "wcxb_dev_cv": {
            "means": _means(dev),
            "bootstrap_vs_trafilatura": {t: _boot(dev, t, "trafilatura") for t in TOOLS[:3]},
        },
        "frontier_dev": {
            t: [float(np.mean([r["thr"][t][i] for r in frontier])) for i in range(3)] for t in thr
        },
        "landing": {
            name: {m["method"] if "method" in m else k: m for k, m in json.loads((EV / "FINAL" / f"landing_comparison_{name}_report.json").read_text())["summary"].items()}
            for name in ("heldout", "fresh")
        },
        "judge": {k: v for k, v in judge["summary"].items() if k.startswith("all:") or k == "position_consistency"},
        "judge_wcxb_test": {"pages": judge2["n_pages"], **{k: v for k, v in judge2["summary"].items() if k.startswith("all:") or k == "position_consistency"}, "by_type": judge2["by_type"]},
        "retrieval_fresh": {
            "bm25": {t: v["scores"]["all"] for t, v in fresh_ret["tools"].items()},
            "dense": {t: v["scores"]["all"] for t, v in fresh_ret["dense"]["tools"].items()},
            "queries": fresh_ret["n_queries"],
            "pages": fresh_ret["n_pages"],
        },
    }
    OUT.write_text(json.dumps(result, indent=1))
    print("wrote", OUT, f"{OUT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
