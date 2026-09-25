"""Fetch ~200-URL corpus and compare ChromeRAG vs baselines.

Writes:
  data/outputs/corpus_comparison_report.json
  data/outputs/corpus_comparison_summary.md
"""

from __future__ import annotations

import json
import traceback
from collections import defaultdict
from pathlib import Path

from chromerag import ChromeRAG, ContentPriority, PipelineConfig
from poc.baselines import BASELINES
from poc.fetch_pages import fetch_all
from poc.metrics import extract_anchors, page_key, score_extraction, scores_to_dict

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

METHODS_OURS = {
    "chromerag": ContentPriority.BALANCED,
    "chromerag_coverage": ContentPriority.COVERAGE,
    "chromerag_precision": ContentPriority.PRECISION,
}

BASELINE_NAMES = [
    "trafilatura",
    "readability",
    "markdownify",
    "html2text",
    "beautifulsoup_text",
    "markitdown",
]

CORPUS_URLS = ROOT / "poc" / "corpus_urls.json"

# Scoreable cohort is defined from the INPUT DOM only (never from any tool's output),
# so every extractor — ChromeRAG included — is averaged over the same, tool-independent
# set of pages. Pages below this many main-content 5-gram anchors are too thin (JS
# shells, empty landmarks) for recall/noise to be meaningful.
MIN_CONTENT_ANCHORS = 50
BOOTSTRAP_ITERS = 2000


def _corpus_urls_listed() -> int:
    """Count URLs listed in the public corpus manifest (may exceed fetched)."""
    if not CORPUS_URLS.exists():
        return 0
    payload = json.loads(CORPUS_URLS.read_text(encoding="utf-8"))
    urls = payload.get("urls") if isinstance(payload, dict) else payload
    return len(urls) if isinstance(urls, list) else 0


def load_ok_pages(raw: Path = RAW) -> list[tuple[str, str, dict]]:
    pages = []
    seen: set[str] = set()
    for meta_path in sorted(raw.glob("*.meta.json")):
        if meta_path.name.startswith("_"):
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        html_path = raw / f"{meta['id']}.html"
        if not html_path.exists():
            continue
        key = page_key(meta)
        if key in seen:
            continue
        seen.add(key)
        pages.append(
            (
                meta["id"],
                html_path.read_text(encoding="utf-8", errors="ignore"),
                meta,
            )
        )
    return pages


def _paired_bootstrap(pages: dict, *, seed: int = 0) -> list[dict]:
    """Paired bootstrap CIs for ChromeRAG-vs-baseline mean differences on scoreable pages."""
    import random

    rng = random.Random(seed)
    rows = []
    for a, b in (
        ("chromerag_coverage", "trafilatura"),
        ("chromerag", "trafilatura"),
        ("chromerag_coverage", "markitdown"),
    ):
        for metric in ("f_balanced", "content_recall", "noise_retention"):
            diffs = [
                float(e["methods"][a][metric]) - float(e["methods"][b][metric])
                for e in pages.values()
                if e.get("scoreable")
                and metric in e["methods"].get(a, {})
                and metric in e["methods"].get(b, {})
            ]
            if not diffs:
                continue
            n = len(diffs)
            means = sorted(
                sum(diffs[rng.randrange(n)] for _ in range(n)) / n
                for _ in range(BOOTSTRAP_ITERS)
            )
            rows.append(
                {
                    "a": a,
                    "b": b,
                    "metric": metric,
                    "n": n,
                    "mean_diff": round(sum(diffs) / n, 4),
                    "ci_low": round(means[int(0.025 * BOOTSTRAP_ITERS)], 4),
                    "ci_high": round(means[int(0.975 * BOOTSTRAP_ITERS) - 1], 4),
                }
            )
    return rows


def run(*, fetch: bool = True, limit: int | None = None) -> dict:
    if fetch:
        print("=== FETCH ===")
        fetch_all(limit=limit)

    pages = load_ok_pages()
    if limit is not None:
        pages = pages[:limit]
    if not pages:
        raise SystemExit(
            f"No fetched HTML in {RAW}. Run without --no-fetch first "
            "(network required); published results live in docs/data/."
        )
    print(f"=== COMPARE {len(pages)} pages ===")

    method_metrics: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    all_metrics: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    report: dict = {"pages": {}, "summary": {}, "n_pages": len(pages)}

    for page_id, html, meta in pages:
        content_ng, noise_ng, diag = extract_anchors(html)
        page_out = OUT / page_id
        page_out.mkdir(parents=True, exist_ok=True)
        entry: dict = {"meta": meta, "anchors": diag, "methods": {}}

        for method, priority in METHODS_OURS.items():
            try:
                text = ChromeRAG(
                    config=PipelineConfig.from_priority(priority)
                ).extract(html, url=meta.get("url")).markdown
                (page_out / f"{method}.md").write_text(text, encoding="utf-8")
                if method == "chromerag":
                    (page_out / "chromerag.md").write_text(text, encoding="utf-8")
                scores = scores_to_dict(
                    score_extraction(method, text, content_ng, noise_ng, diag)
                )
                entry["methods"][method] = scores
            except Exception as exc:  # noqa: BLE001
                entry["methods"][method] = {
                    "error": str(exc),
                    "trace": traceback.format_exc()[-400:],
                }

        for name in BASELINE_NAMES:
            try:
                text = BASELINES[name](html)
                (page_out / f"{name}.md").write_text(text, encoding="utf-8")
                scores = scores_to_dict(
                    score_extraction(name, text, content_ng, noise_ng, diag)
                )
                entry["methods"][name] = scores
            except Exception as exc:  # noqa: BLE001
                entry["methods"][name] = {"error": str(exc)}

        # Tool-independent cohort: enough main-content anchors in the input DOM.
        ours = entry["methods"].get("chromerag", {})
        scoreable = int(diag.get("content_ngrams", 0)) >= MIN_CONTENT_ANCHORS
        entry["scoreable"] = scoreable
        report["pages"][page_id] = entry

        status = "OK" if scoreable else "THIN"
        cr = ours.get("content_recall", 0)
        print(
            f"  {status} {page_id:40s} recall={cr} "
            f"noise={ours.get('noise_retention')} tok={ours.get('tokens')}"
        )

        for method, stats in entry["methods"].items():
            if "content_recall" in stats:
                for key in ("content_recall", "noise_retention", "f_balanced", "tokens"):
                    all_metrics[method][key].append(float(stats[key]))

        if scoreable:
            for method, stats in entry["methods"].items():
                if "content_recall" not in stats:
                    continue
                for key in (
                    "content_recall",
                    "noise_retention",
                    "f_balanced",
                    "f_precision",
                    "f_coverage",
                    "tokens",
                    "noise_per_1k_tokens",
                ):
                    method_metrics[method][key].append(float(stats[key]))

    summary = {}
    for method, metrics in method_metrics.items():
        if not metrics.get("content_recall"):
            continue
        summary[method] = {
            "pages_scored": len(metrics["content_recall"]),
            **{
                f"avg_{k}": round(sum(v) / len(v), 4)
                for k, v in metrics.items()
                if v
            },
        }
    report["summary"] = summary
    report["n_scoreable"] = summary.get("chromerag", {}).get("pages_scored", 0)
    report["scoreable_rule"] = f"input DOM content_ngrams >= {MIN_CONTENT_ANCHORS}"
    report["summary_all_fetched"] = {
        method: {
            "pages_scored": len(m["content_recall"]),
            **{f"avg_{k}": round(sum(v) / len(v), 4) for k, v in m.items() if v},
        }
        for method, m in all_metrics.items()
        if m.get("content_recall")
    }
    report["paired_bootstrap"] = _paired_bootstrap(report["pages"])

    # Per page-type (category) breakdown for ChromeRAG vs Trafilatura vs MarkItDown
    by_cat: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    for page_id, entry in report["pages"].items():
        if not entry.get("scoreable"):
            continue
        cat = str((entry.get("meta") or {}).get("category") or "unknown")
        for method in ("chromerag", "chromerag_coverage", "trafilatura", "markitdown"):
            stats = entry["methods"].get(method) or {}
            if "content_recall" not in stats:
                continue
            for key in ("content_recall", "noise_retention", "f_balanced", "tokens"):
                by_cat[cat][method][key].append(float(stats[key]))
    cat_summary: dict[str, dict[str, dict[str, float | int]]] = {}
    for cat, methods in sorted(by_cat.items()):
        cat_summary[cat] = {}
        for method, metrics in methods.items():
            n = len(metrics.get("content_recall") or [])
            if not n:
                continue
            cat_summary[cat][method] = {
                "pages": n,
                **{f"avg_{k}": round(sum(v) / len(v), 4) for k, v in metrics.items() if v},
            }
    report["by_category"] = cat_summary
    corpus_listed = _corpus_urls_listed()
    n_thin = sum(1 for e in report["pages"].values() if not e.get("scoreable"))
    report["corpus_urls_listed"] = corpus_listed
    report["corpus_url_count"] = corpus_listed  # permanent alias used in older docs
    report["n_fetched"] = len(pages)
    report["n_thin"] = n_thin
    report["n_scoreable"] = int(report["n_scoreable"])

    out_json = OUT / "corpus_comparison_report.json"
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        f"# ChromeRAG Corpus Comparison ({len(pages)} fetched / {corpus_listed} listed)",
        "",
        f"Corpus URLs listed: **{corpus_listed}**  ",
        f"Pages fetched/available: **{len(pages)}**  ",
        f"Scoreable (input DOM has ≥ {MIN_CONTENT_ANCHORS} main-content anchors): "
        f"**{report['n_scoreable']}**  ",
        f"Thin / excluded from means: **{n_thin}**",
        "",
        "> The scoreable cohort is defined from the input HTML only (main-content 5-gram "
        "anchors), never from any extractor's output, so every tool is averaged over the "
        "same tool-independent page set. Thin pages are mostly unrendered JS shells or "
        "empty landmarks; callers must render those first. Means over all fetched pages "
        "are reported below as well.",
        "",
        "## Baselines",
        "",
        "ChromeRAG (balanced / coverage / precision) vs Trafilatura, Readability, "
        "MarkItDown, markdownify, html2text, BeautifulSoup text.",
        "",
        "## Metrics",
        "",
        "- **Recall (content_recall)** — fraction of main-content text anchors kept. Higher = fewer lost relevant chunks.",
        "- **Noise ret (noise_retention)** — fraction of nav/footer chrome anchors kept. Lower = cleaner vectors.",
        "- **Fbal (f_balanced)** — harmonic-style score balancing high recall and low noise.",
        "",
        "## Leaderboard (scoreable pages)",
        "",
        "| Method | Pages | Recall ↑ | Noise ret ↓ | Fbal ↑ | Avg tokens |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method, s in sorted(
        summary.items(),
        key=lambda x: (-x[1].get("avg_f_balanced", 0), x[1].get("avg_noise_retention", 1)),
    ):
        lines.append(
            f"| `{method}` | {s['pages_scored']} | {s.get('avg_content_recall', 0):.3f} | "
            f"{s.get('avg_noise_retention', 0):.3f} | {s.get('avg_f_balanced', 0):.3f} | "
            f"{s.get('avg_tokens', 0):.0f} |"
        )
    lines.extend(
        [
            "",
            f"## All fetched pages (no cohort filter, n={len(pages)})",
            "",
            "| Method | Pages | Recall ↑ | Noise ret ↓ | Fbal ↑ |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for method, s in sorted(
        report["summary_all_fetched"].items(), key=lambda x: -x[1].get("avg_f_balanced", 0)
    ):
        lines.append(
            f"| `{method}` | {s['pages_scored']} | {s.get('avg_content_recall', 0):.3f} | "
            f"{s.get('avg_noise_retention', 0):.3f} | {s.get('avg_f_balanced', 0):.3f} |"
        )
    lines.extend(
        [
            "",
            "## Paired bootstrap (scoreable pages, 95% CI of mean difference)",
            "",
            "| Comparison | Metric | Mean diff | 95% CI |",
            "|---|---|---:|---:|",
        ]
    )
    for row in report["paired_bootstrap"]:
        lines.append(
            f"| `{row['a']}` − `{row['b']}` | {row['metric']} | {row['mean_diff']:+.3f} | "
            f"[{row['ci_low']:+.3f}, {row['ci_high']:+.3f}] |"
        )
    lines.extend(["", "## By page category (ChromeRAG vs Trafilatura vs MarkItDown)", ""])
    for cat, methods in cat_summary.items():
        lines.append(f"### `{cat}`")
        lines.append("")
        lines.append("| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |")
        lines.append("|---|---:|---:|---:|---:|")
        for method, s in sorted(
            methods.items(), key=lambda x: -float(x[1].get("avg_f_balanced", 0))
        ):
            lines.append(
                f"| `{method}` | {s['pages']} | {s.get('avg_content_recall', 0):.3f} | "
                f"{s.get('avg_noise_retention', 0):.3f} | {s.get('avg_f_balanced', 0):.3f} |"
            )
        lines.append("")
    out_md = OUT / "corpus_comparison_summary.md"
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n===== LEADERBOARD =====")
    for method, s in sorted(
        summary.items(), key=lambda x: -x[1].get("avg_f_balanced", 0)
    ):
        print(
            f"  {method:22s} n={s['pages_scored']:3d} "
            f"recall={s.get('avg_content_recall', 0):.3f} "
            f"noise={s.get('avg_noise_retention', 0):.3f} "
            f"Fbal={s.get('avg_f_balanced', 0):.3f}"
        )
    print(f"\nWrote {out_json}")
    print(f"Wrote {out_md}")
    return report


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--no-fetch", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()
    run(fetch=not args.no_fetch, limit=args.limit)
