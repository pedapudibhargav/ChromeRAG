#!/usr/bin/env python3
"""Revalidate the corpus benchmark report without re-fetching the web.

Recomputes the scoreable cohort from each page's input-DOM anchor count and every
method's leaderboard means from the per-page scores, and checks them against the
report's summary. Uses the local re-run (data/outputs) when present, otherwise the
published report in docs/data. When raw HTML is available, also classifies the thin
pages via input_quality (JS shell vs other thin HTML).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from chromerag.input_quality import assess_input_html  # noqa: E402
from poc.metrics import page_key  # noqa: E402

LOCAL_REPORT = ROOT / "data" / "outputs" / "corpus_comparison_report.json"
PUBLISHED_REPORT = ROOT / "docs" / "data" / "corpus_comparison_report.json"
REPORT = LOCAL_REPORT if LOCAL_REPORT.exists() else PUBLISHED_REPORT
MIN_CONTENT_ANCHORS = 50
METRICS = ("content_recall", "noise_retention", "f_balanced")
CORPUS = ROOT / "poc" / "corpus_urls.json"
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "outputs" / "corpus_revalidation.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def _fail(msg: str, errors: list[str]) -> None:
    errors.append(msg)
    print(f"FAIL: {msg}")


def main() -> int:
    errors: list[str] = []
    if not REPORT.exists():
        print(f"Missing report: {REPORT}")
        return 2

    print(f"Report:             {REPORT.relative_to(ROOT)}")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    listed = len(corpus.get("urls") or [])
    pages = report.get("pages") or {}
    n_pages = len(pages)
    n_scoreable = sum(1 for e in pages.values() if e.get("scoreable"))
    n_thin = n_pages - n_scoreable
    raw_html = list(RAW.glob("*.html"))
    raw_html = [p for p in raw_html if not p.name.startswith("_")]
    # The harness scores each final URL once, so count unique pages on disk.
    raw_unique = {
        page_key(json.loads(p.with_suffix(".meta.json").read_text(encoding="utf-8")))
        for p in raw_html
        if p.with_suffix(".meta.json").exists()
    }

    print(f"Corpus URLs listed: {listed}")
    print(f"Report pages:       {n_pages}")
    print(f"Scoreable:          {n_scoreable}")
    print(f"Thin:               {n_thin}")
    print(f"Raw HTML on disk:   {len(raw_html)} ({len(raw_unique)} unique pages)")

    if listed < 300:
        _fail(f"Expected ~367 listed URLs, got {listed}", errors)
    if raw_unique and n_pages != len(raw_unique):
        _fail(f"Report pages ({n_pages}) != unique raw pages ({len(raw_unique)})", errors)
    for pid, e in pages.items():
        expected = int((e.get("anchors") or {}).get("content_ngrams", 0)) >= MIN_CONTENT_ANCHORS
        if bool(e.get("scoreable")) != expected:
            _fail(f"{pid}: scoreable flag does not match the input-anchor rule", errors)
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

    # Recompute every published mean from the per-page scores.
    for method, stats in summary.items():
        for metric in METRICS:
            vals = [
                float(e["methods"][method][metric])
                for e in pages.values()
                if e.get("scoreable") and metric in (e.get("methods", {}).get(method) or {})
            ]
            if not vals:
                continue
            mean = sum(vals) / len(vals)
            published = float(stats.get(f"avg_{metric}", -1))
            if abs(mean - published) > 5e-4:
                _fail(f"{method} {metric}: recomputed {mean:.4f} != published {published:.4f}", errors)

    # Classify thin pages (JS shell vs other)
    thin_ids = [pid for pid, e in pages.items() if not e.get("scoreable")]
    kinds: Counter[str] = Counter()
    thin_detail: list[dict] = []
    for pid in thin_ids:
        html_path = RAW / f"{pid}.html"
        if not html_path.exists():
            kinds["raw_html_not_available"] += 1
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
