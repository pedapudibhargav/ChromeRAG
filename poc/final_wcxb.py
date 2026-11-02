"""The one protocol run on the WCXB test split: all local tools, same HTML, saved outputs and paired ranges."""

from __future__ import annotations

import argparse
import json
import subprocess
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import trafilatura

from chromerag import ChromeRAG
from chromerag.config import PipelineConfig
from poc.baselines import baseline_markitdown, baseline_readability, baseline_trafilatura
from poc.learn_tokens import cv_site_of
from poc.wcxb import load_split, snippet_rate, strip_front_matter, word_f1

TOOLS = ("chromerag", "chromerag_precision", "chromerag_coverage", "trafilatura", "readability", "markitdown")
PRIORITY = {"chromerag": "balanced", "chromerag_precision": "precision", "chromerag_coverage": "coverage"}


def run_tool(tool: str, html: str, url: str) -> str:
    if tool in PRIORITY:
        cfg = PipelineConfig.from_priority(PRIORITY[tool])
        return strip_front_matter(ChromeRAG(config=cfg).extract(html, url=url).markdown)
    if tool == "trafilatura":
        return baseline_trafilatura(html, url)
    if tool == "readability":
        return baseline_readability(html)
    return baseline_markitdown(html)


def score_page(args: tuple) -> dict:
    pid, html, url, ref, without, page_type, out_root = args
    row = {"id": pid, "type": page_type, "site": cv_site_of(url)}
    for tool in TOOLS:
        try:
            text = run_tool(tool, html, url)
        except Exception as exc:
            row.setdefault("errors", {})[tool] = type(exc).__name__
            text = ""
        path = Path(out_root) / tool / f"{pid}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        p, r, f1 = word_f1(text, ref)
        row[tool] = {"p": p, "r": r, "f1": f1, "without": snippet_rate(text, without)}
    return row


def paired(rows: list[dict], a: str, b: str, key: str) -> dict:
    by_site: dict[str, list[float]] = {}
    for row in rows:
        by_site.setdefault(row["site"], []).append(row[a][key] - row[b][key])
    weights = np.array([len(v) for v in by_site.values()])
    sums = np.array([sum(v) for v in by_site.values()])
    rng = np.random.default_rng(0)
    n = len(weights)
    samples = [
        sums[ix].sum() / weights[ix].sum() for ix in (rng.integers(0, n, n) for _ in range(5000))
    ]
    return {
        "mean": float(sums.sum() / weights.sum()),
        "ci95": [float(x) for x in np.percentile(samples, [2.5, 97.5])],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wcxb-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--outputs-dir", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()
    if subprocess.call(["git", "diff", "--quiet", "freeze-0.1.5", "--", "src", "pyproject.toml"]):
        raise SystemExit("src differs from freeze-0.1.5")
    if args.out.exists():
        raise SystemExit(f"{args.out} exists: this set is scored once")
    pages = load_split("test", root=args.wcxb_root)
    work = [
        (p.id, p.html, p.url, p.main_content, p.without_snippets, getattr(p, "page_type", ""), str(args.outputs_dir))
        for p in pages
    ]
    with Pool(args.workers) as pool:
        rows = pool.map(score_page, work, chunksize=4)
    summary = {
        t: {
            k: float(np.mean([r[t][k] for r in rows]))
            for k in ("p", "r", "f1", "without")
        }
        | {"under_0_1": sum(r[t]["f1"] < 0.1 for r in rows)}
        for t in TOOLS
    }
    report = {
        "pages": len(rows),
        "summary": summary,
        "trafilatura_version": trafilatura.__version__,
        "primary_balanced_minus_trafilatura": {
            k: paired(rows, "chromerag", "trafilatura", k) for k in ("f1", "without")
        },
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("pages", "summary", "primary_balanced_minus_trafilatura")}, indent=1))


if __name__ == "__main__":
    main()
