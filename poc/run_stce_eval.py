"""Score site-template chrome elimination (STCE) on the public corpus.

For every site group (host + first path segment) with at least ``--min-pages``
fetched pages, learn a site model with the same defaults as ``chromerag learn``
and extract each page in coverage mode with and without it. Scores use the same
anchors as ``poc.run_corpus_comparison`` plus a site-level measure: output
5-grams that recur in at least 80% of the group's outputs (text that would be
embedded once per page). YAML front-matter is excluded from that measure, since
repeated metadata such as ``author`` or ``type`` is intended, not chrome.

Trafilatura and MarkItDown are scored the same way for context.

Usage:
  python -m poc.run_stce_eval                         # benchmark pages (data/raw)
  python -m poc.run_stce_eval --raw data/stce_crawl   # multi-page crawl (poc.crawl_site_groups)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from chromerag import ChromeRAG, ContentPriority, PipelineConfig
from chromerag.batch import learn_chrome
from chromerag.site_chrome import site_group_key
from poc.baselines import BASELINES
from poc.metrics import char_ngrams, extract_anchors, score_extraction, scores_to_dict
from poc.run_corpus_comparison import MIN_CONTENT_ANCHORS, OUT, RAW, ROOT, load_ok_pages

VARIANTS = ("coverage", "coverage_stce", "trafilatura", "markitdown")
_FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
SITE_REPEAT_SHARE = 0.8


def _site_repeated(outputs: dict[str, set[str]], page_id: str) -> int:
    counts = Counter(g for grams in outputs.values() for g in grams)
    threshold = max(2, SITE_REPEAT_SHARE * len(outputs))
    return sum(1 for g in outputs[page_id] if counts[g] >= threshold)


def _score_page(task: tuple) -> tuple[dict, dict[str, set[str]]]:
    """Score one page with every variant (runs in a worker process)."""
    page_id, html, url, group, model = task
    cfg = PipelineConfig.from_priority(ContentPriority.COVERAGE)
    content_ng, noise_ng, diag = extract_anchors(html)
    row = {"id": page_id, "group": group, "scoreable": diag["content_ngrams"] >= MIN_CONTENT_ANCHORS}
    page_grams: dict[str, set[str]] = {}
    for variant in VARIANTS:
        if variant in BASELINES:
            text = BASELINES[variant](html)
        else:
            site_model = model if variant == "coverage_stce" else None
            text = ChromeRAG(config=cfg, site_chrome=site_model).extract(html, url=url).markdown
        row[variant] = scores_to_dict(score_extraction(variant, text, content_ng, noise_ng, diag))
        page_grams[variant] = char_ngrams(_FRONT_MATTER.sub("", text))
    return row, page_grams


def run(*, min_pages: int = 3, raw: Path = RAW, workers: int | None = None) -> dict:
    pages = load_ok_pages(raw)
    if not pages:
        raise SystemExit(f"No fetched HTML in {raw}. Fetch the pages first (see module docstring).")
    models = learn_chrome([(meta.get("url"), html) for _, html, meta in pages], min_pages=min_pages)
    models = {k: m for k, m in models.items() if m.signatures}
    tasks = []
    for page_id, html, meta in pages:
        group = site_group_key(meta.get("url"))
        if group in models:
            tasks.append((page_id, html, meta.get("url"), group, models[group]))

    rows: list[dict] = []
    grams: dict[str, dict[str, dict[str, set[str]]]] = defaultdict(lambda: defaultdict(dict))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for row, page_grams in pool.map(_score_page, tasks, chunksize=4):
            for variant, g in page_grams.items():
                grams[row["group"]][variant][row["id"]] = g
            rows.append(row)

    for row in rows:
        for variant in VARIANTS:
            outputs = grams[row["group"]][variant]
            repeated = _site_repeated(outputs, row["id"])
            row[variant]["site_repeated_5grams"] = repeated
            row[variant]["site_repeated_share"] = repeated / len(outputs[row["id"]]) if outputs[row["id"]] else 0.0

    scoreable = [r for r in rows if r["scoreable"]]
    summary = {
        variant: {
            metric: round(statistics.mean(r[variant][metric] for r in scoreable), 3)
            for metric in (
                "content_recall",
                "noise_retention",
                "f_balanced",
                "tokens",
                "site_repeated_5grams",
                "site_repeated_share",
            )
        }
        for variant in VARIANTS
    }
    report = {
        "raw": str(raw.relative_to(ROOT)) if raw.is_relative_to(ROOT) else str(raw),
        "min_pages": min_pages,
        "groups": {k: {"pages": m.n_pages, "signatures": len(m.signatures)} for k, m in models.items()},
        "n_pages": len(rows),
        "n_scoreable": len(scoreable),
        "n_pages_changed": sum(
            1 for r in rows if r["coverage"]["tokens"] != r["coverage_stce"]["tokens"]
        ),
        "summary_scoreable": summary,
        "pages": rows,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    name = "stce_eval_report.json" if raw == RAW else f"stce_eval_{raw.name}_report.json"
    (OUT / name).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {**report, "path": str(OUT / name)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--min-pages", type=int, default=3)
    p.add_argument("--raw", type=Path, default=RAW, help="directory of <id>.html + <id>.meta.json")
    p.add_argument("--workers", type=int, default=os.cpu_count(), help="parallel processes")
    args = p.parse_args()
    report = run(min_pages=args.min_pages, raw=args.raw.resolve(), workers=args.workers)
    print(
        f"Site groups with a learned model: {len(report['groups'])}; "
        f"pages: {report['n_pages']} ({report['n_scoreable']} scoreable); "
        f"pages changed by STCE: {report['n_pages_changed']}"
    )
    for variant, s in report["summary_scoreable"].items():
        print(
            f"  {variant:14s} recall {s['content_recall']:.3f}  noise {s['noise_retention']:.3f}  "
            f"Fbal {s['f_balanced']:.3f}  tokens {s['tokens']:.0f}  "
            f"site-repeated 5-grams/page {s['site_repeated_5grams']:.1f} "
            f"({s['site_repeated_share']:.1%} of output)"
        )
    print(f"Wrote {report['path']}")


if __name__ == "__main__":
    main()
