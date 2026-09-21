"""Proper comparison: baselines + our precision/coverage/balanced modes.

Measures content_recall and noise_retention from HTML-derived anchors
(independent of any extractor). Writes:
  data/outputs/comparison_report.json
  data/outputs/comparison_summary.md
"""

from __future__ import annotations

import json
import traceback
from collections import defaultdict
from pathlib import Path

from poc.baselines import BASELINES
from poc.metrics import extract_anchors, score_extraction, scores_to_dict
from chromerag import ChromeRAG
from chromerag.config import ContentPriority, PipelineConfig

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

OUR_METHODS = {
    "chromerag_precision": ContentPriority.PRECISION,
    "chromerag_balanced": ContentPriority.BALANCED,
    "chromerag_coverage": ContentPriority.COVERAGE,
}

# Prefer live baselines; fall back to cached .md if import/runtime fails
BASELINE_NAMES = [
    "trafilatura",
    "readability",
    "markitdown",
    "markdownify",
    "html2text",
    "beautifulsoup_text",
]


def load_fixtures() -> list[tuple[str, str, dict]]:
    rows = []
    for meta_path in sorted(RAW.glob("*.meta.json")):
        if meta_path.name.startswith("_"):
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        html_path = RAW / f"{meta['id']}.html"
        if not html_path.exists():
            continue
        rows.append(
            (meta["id"], html_path.read_text(encoding="utf-8", errors="ignore"), meta)
        )
    return rows


def _run_baseline(name: str, html: str, page_id: str) -> tuple[str, str]:
    fn = BASELINES.get(name)
    if fn is None:
        return "", "missing_fn"
    try:
        text = fn(html)
        if text.startswith("[") and "not installed" in text:
            cached = OUT / page_id / f"{name}.md"
            if cached.exists():
                cached_text = cached.read_text(encoding="utf-8", errors="ignore")
                if not (cached_text.startswith("[") and "not installed" in cached_text):
                    return cached_text, "cache_fallback"
            return text, "not_installed"
        return text, "live"
    except Exception as exc:  # noqa: BLE001
        cached = OUT / page_id / f"{name}.md"
        if cached.exists():
            cached_text = cached.read_text(encoding="utf-8", errors="ignore")
            if cached_text and not (
                cached_text.startswith("[") and "not installed" in cached_text
            ):
                return cached_text, f"cache_after_error:{type(exc).__name__}"
        return "", f"error:{type(exc).__name__}:{exc}"


def run() -> dict:
    fixtures = load_fixtures()
    report: dict = {
        "pages": {},
        "summary": {},
        "mode_tradeoff": {},
        "notes": [
            "content_recall = fraction of HTML content 5-grams retained",
            "noise_retention = fraction of HTML chrome 5-grams retained",
            "chromerag_precision = ContentPriority.PRECISION (clean, may drop chunks)",
            "chromerag_coverage = ContentPriority.COVERAGE (keep chunks, tolerate noise)",
            "chromerag_balanced = ContentPriority.BALANCED (default)",
        ],
    }

    method_metrics: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    method_metrics_scoreable: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for page_id, html, meta in fixtures:
        page_out = OUT / page_id
        page_out.mkdir(parents=True, exist_ok=True)

        content_ng, noise_ng, anchor_diag = extract_anchors(html)
        page_entry: dict = {
            "meta": {"id": page_id, "url": meta.get("url"), "category": meta.get("category")},
            "anchors": anchor_diag,
            "methods": {},
        }

        # Skip pages with almost no measurable content anchors (JS shells)
        thin = anchor_diag["content_ngrams"] < 15
        page_entry["thin_static_content"] = thin

        # Our three modes
        for method_name, priority in OUR_METHODS.items():
            try:
                ext = ChromeRAG(config=PipelineConfig.from_priority(priority))
                result = ext.extract(html, url=meta.get("url"))
                (page_out / f"{method_name}.md").write_text(result.markdown, encoding="utf-8")
                # Keep default name for balanced (UI compat)
                if priority == ContentPriority.BALANCED:
                    (page_out / "chromerag.md").write_text(
                        result.markdown, encoding="utf-8"
                    )
                scores = score_extraction(
                    method_name, result.markdown, content_ng, noise_ng, anchor_diag
                )
                row = scores_to_dict(scores)
                row["source"] = "live"
                row["priority"] = priority.value
                row["front_matter_keys"] = list(result.front_matter.keys())
                row["json_ld"] = result.diagnostics.get("schema_sources", {}).get(
                    "json_ld_count", 0
                )
                page_entry["methods"][method_name] = row
            except Exception as exc:  # noqa: BLE001
                page_entry["methods"][method_name] = {
                    "error": str(exc),
                    "trace": traceback.format_exc()[-600:],
                }

        # Baselines
        for name in BASELINE_NAMES:
            text, source = _run_baseline(name, html, page_id)
            if not text:
                page_entry["methods"][name] = {"error": source, "source": source}
                continue
            if source == "live":
                (page_out / f"{name}.md").write_text(text, encoding="utf-8")
            scores = score_extraction(name, text, content_ng, noise_ng, anchor_diag)
            row = scores_to_dict(scores)
            row["source"] = source
            page_entry["methods"][name] = row

        # Unextractable static shell: no strong method retains ≥20% content
        recalls = [
            float(s["content_recall"])
            for s in page_entry["methods"].values()
            if "content_recall" in s
        ]
        unextractable = (max(recalls) if recalls else 0.0) < 0.20
        page_entry["unextractable_static"] = unextractable

        report["pages"][page_id] = page_entry

        print(
            f"\n=== {page_id} content_ng={anchor_diag['content_ngrams']} "
            f"noise_ng={anchor_diag['noise_ngrams']} thin={thin} "
            f"unextractable={unextractable} ==="
        )
        for method, stats in sorted(page_entry["methods"].items()):
            if "error" in stats:
                print(f"  {method:22s} ERROR {stats['error'][:80]}")
                continue
            print(
                f"  {method:22s} tok={stats['tokens']:6d}  "
                f"recall={stats['content_recall']:.3f}  "
                f"noise_ret={stats['noise_retention']:.3f}  "
                f"Fbal={stats['f_balanced']:.3f}  src={stats.get('source')}"
            )
            if not thin and not unextractable:
                for key in (
                    "content_recall",
                    "noise_retention",
                    "f_precision",
                    "f_coverage",
                    "f_balanced",
                    "tokens",
                    "noise_per_1k_tokens",
                ):
                    method_metrics[method][key].append(float(stats[key]))

        # Separate bucket: pages where at least one of our modes retained content
        ours_recalls = [
            float(page_entry["methods"][m]["content_recall"])
            for m in OUR_METHODS
            if m in page_entry["methods"] and "content_recall" in page_entry["methods"][m]
        ]
        ours_ok = (max(ours_recalls) if ours_recalls else 0.0) >= 0.05
        page_entry["ours_scoreable"] = ours_ok
        if ours_ok and not thin:
            for method, stats in page_entry["methods"].items():
                if "content_recall" not in stats:
                    continue
                for key in (
                    "content_recall",
                    "noise_retention",
                    "f_precision",
                    "f_coverage",
                    "f_balanced",
                    "tokens",
                    "noise_per_1k_tokens",
                ):
                    method_metrics_scoreable[method][key].append(float(stats[key]))

    # Aggregate (exclude thin JS shells from averages)
    def _agg(bucket: dict[str, dict[str, list[float]]]) -> dict:
        out = {}
        for method, metrics in bucket.items():
            if not metrics.get("content_recall"):
                continue
            out[method] = {
                "pages_scored": len(metrics["content_recall"]),
                **{
                    f"avg_{k}": round(sum(v) / len(v), 4)
                    for k, v in metrics.items()
                    if v
                },
            }
        return out

    summary = _agg(method_metrics)
    summary_scoreable = _agg(method_metrics_scoreable)
    report["summary"] = summary
    report["summary_ours_scoreable"] = summary_scoreable

    # Explicit mode tradeoff table (prefer scoreable — excludes total pipeline failures)
    src = summary_scoreable if summary_scoreable else summary
    tradeoff = {}
    for m in OUR_METHODS:
        if m in src:
            tradeoff[m] = {
                "avg_content_recall": src[m].get("avg_content_recall"),
                "avg_noise_retention": src[m].get("avg_noise_retention"),
                "avg_f_precision": src[m].get("avg_f_precision"),
                "avg_f_coverage": src[m].get("avg_f_coverage"),
                "avg_f_balanced": src[m].get("avg_f_balanced"),
                "avg_tokens": src[m].get("avg_tokens"),
                "pages": src[m].get("pages_scored"),
            }
    report["mode_tradeoff"] = tradeoff

    out_json = OUT / "comparison_report.json"
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Markdown summary for humans
    lines = [
        "# Extraction Comparison Report",
        "",
        "Metrics use HTML-derived anchors (main/article content vs nav/footer chrome),",
        "independent of any extractor. Thin JS-shell pages excluded from averages.",
        "",
        "## Mode tradeoff (ours, scoreable pages only)",
        "",
        "Pages where all our modes return ~0 content (static JS shells) are excluded here;",
        "see per-page table in `comparison_report.json` for those failures.",
        "",
        "| Mode | Pages | Content recall ↑ | Noise retention ↓ | F_precision | F_coverage | F_balanced | Avg tokens |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for m, t in tradeoff.items():
        lines.append(
            f"| `{m}` | {t.get('pages')} | {t['avg_content_recall']} | {t['avg_noise_retention']} | "
            f"{t['avg_f_precision']} | {t['avg_f_coverage']} | {t['avg_f_balanced']} | "
            f"{t['avg_tokens']:.0f} |"
        )
    lines += [
        "",
        "## All methods on scoreable pages",
        "",
        "| Method | Pages | Recall ↑ | Noise ret ↓ | F_bal | Tokens | Noise/1k tok |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    rank_src = summary_scoreable if summary_scoreable else summary
    for method, s in sorted(
        rank_src.items(),
        key=lambda x: (-x[1].get("avg_f_balanced", 0), x[1].get("avg_noise_retention", 1)),
    ):
        lines.append(
            f"| `{method}` | {s['pages_scored']} | {s.get('avg_content_recall', 0):.3f} | "
            f"{s.get('avg_noise_retention', 0):.3f} | {s.get('avg_f_balanced', 0):.3f} | "
            f"{s.get('avg_tokens', 0):.0f} | {s.get('avg_noise_per_1k_tokens', 0):.2f} |"
        )
    lines += [
        "",
        "## How to choose",
        "",
        "- `--priority precision` — maximize cleanliness; accept lower content recall.",
        "- `--priority coverage` — maximize content recall; accept more residual chrome.",
        "- `--priority balanced` — default for enterprise RAG ingest.",
        "",
        "## Known gaps",
        "",
        "- JS-rendered shells (some SPA docs homes): static extractors under-extract;",
        "  needs optional Playwright render stage — not more aggressive pruning.",
        "- MarkItDown not installed in this container run (excluded).",
        "",
    ]
    out_md = OUT / "comparison_summary.md"
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n===== MODE TRADEOFF (scoreable) =====")
    for m, t in tradeoff.items():
        print(
            f"  {m:16s} n={t.get('pages')} recall={t['avg_content_recall']}  "
            f"noise_ret={t['avg_noise_retention']}  "
            f"Fbal={t['avg_f_balanced']}  tok={t['avg_tokens']:.0f}"
        )
    print("\n===== ALL METHODS on scoreable (by F_balanced) =====")
    for method, s in sorted(
        rank_src.items(), key=lambda x: -x[1].get("avg_f_balanced", 0)
    ):
        print(
            f"  {method:22s} recall={s.get('avg_content_recall', 0):.3f}  "
            f"noise={s.get('avg_noise_retention', 0):.3f}  "
            f"Fbal={s.get('avg_f_balanced', 0):.3f}  tok={s.get('avg_tokens', 0):.0f}"
        )
    print(f"\nWrote {out_json}")
    print(f"Wrote {out_md}")
    return report


if __name__ == "__main__":
    run()
