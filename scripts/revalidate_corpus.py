#!/usr/bin/env python3
"""Revalidate corpus report integrity without re-fetching the web.

Checks that published leaderboard numbers are internally consistent and that
thin/scoreable accounting matches the honesty rules used in the SoftareX draft.
Also classifies thin pages via input_quality (JS shell vs other thin HTML).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chromerag.input_quality import assess_input_html  # noqa: E402

REPORT = ROOT / "data" / "outputs" / "corpus_comparison_report.json"
CORPUS = ROOT / "poc" / "corpus_urls.json"
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "outputs" / "corpus_revalidation.json"


def _fail(msg: str, errors: list[str]) -> None:
    errors.append(msg)
    print(f"FAIL: {msg}")


def main() -> int:
    errors: list[str] = []
    if not REPORT.exists():
        print(f"Missing report: {REPORT}")
        return 2

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    listed = len(corpus.get("urls") or [])
    pages = report.get("pages") or {}
    n_pages = len(pages)
    n_scoreable = sum(1 for e in pages.values() if e.get("scoreable"))
    n_thin = n_pages - n_scoreable
    raw_html = list(RAW.glob("*.html"))
    raw_html = [p for p in raw_html if not p.name.startswith("_")]

    print(f"Corpus URLs listed: {listed}")
    print(f"Report pages:       {n_pages}")
    print(f"Scoreable:          {n_scoreable}")
    print(f"Thin:               {n_thin}")
    print(f"Raw HTML on disk:   {len(raw_html)}")

    if listed < 300:
        _fail(f"Expected ~373 listed URLs, got {listed}", errors)
    if n_pages != len(raw_html):
        _fail(f"Report pages ({n_pages}) != raw HTML files ({len(raw_html)})", errors)
    if report.get("n_scoreable") not in (None, n_scoreable) and int(report["n_scoreable"]) != n_scoreable:
        _fail(
            f"report.n_scoreable={report.get('n_scoreable')} != recomputed {n_scoreable}",
            errors,
        )

    summary = report.get("summary") or {}
    for method, stats in summary.items():
        scored = int(stats.get("pages_scored") or 0)
        if scored != n_scoreable:
            _fail(f"{method} pages_scored={scored} != scoreable={n_scoreable}", errors)

    # Spot-check Fbal formula ordering: coverage should beat markitdown on Fbal
    cov = float((summary.get("chromerag_coverage") or {}).get("avg_f_balanced") or 0)
    traf = float((summary.get("trafilatura") or {}).get("avg_f_balanced") or 0)
    mid = float((summary.get("markitdown") or {}).get("avg_f_balanced") or 0)
    if not (cov > traf > 0.5):
        _fail(f"Unexpected ranking: coverage={cov} trafilatura={traf}", errors)
    if not (cov > mid):
        _fail(f"coverage Fbal {cov} should exceed markitdown {mid}", errors)

    # Classify thin pages (JS shell vs other)
    thin_ids = [pid for pid, e in pages.items() if not e.get("scoreable")]
    kinds: Counter[str] = Counter()
    thin_detail: list[dict] = []
    for pid in thin_ids:
        html_path = RAW / f"{pid}.html"
        if not html_path.exists():
            kinds["missing_html"] += 1
            continue
        html = html_path.read_text(encoding="utf-8", errors="ignore")
        iq = assess_input_html(html)
        kind = "js_shell" if iq.likely_js_shell else ("thin_other" if iq.is_thin else "not_thin_but_unscoreable")
        kinds[kind] += 1
        thin_detail.append(
            {
                "id": pid,
                "kind": kind,
                "visible_chars": iq.visible_chars,
                "visible_words": iq.visible_words,
                "root_marker": iq.root_marker,
            }
        )

    print("Thin-page classification:")
    for k, v in sorted(kinds.items()):
        print(f"  {k}: {v}")

    payload = {
        "ok": not errors,
        "errors": errors,
        "corpus_urls_listed": listed,
        "n_fetched": n_pages,
        "n_scoreable": n_scoreable,
        "n_thin": n_thin,
        "leaderboard": {
            m: {
                "pages_scored": s.get("pages_scored"),
                "avg_content_recall": s.get("avg_content_recall"),
                "avg_noise_retention": s.get("avg_noise_retention"),
                "avg_f_balanced": s.get("avg_f_balanced"),
            }
            for m, s in summary.items()
        },
        "thin_kinds": dict(kinds),
        "thin_sample": thin_detail[:25],
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")

    if errors:
        print(f"\n{len(errors)} integrity error(s).")
        return 1
    print("\nPASS: corpus report revalidation OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
