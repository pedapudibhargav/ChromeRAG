"""Closed-loop QA: extract → score → flag failures → summary.

Stages:
  1. Unit smoke (import + single extract)
  2. Learn chrome (optional) then batch extract
  3. Anchor metrics vs baselines
  4. Gate: fail if scoreable avg F_balanced < threshold or recall collapse
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from poc.baselines import BASELINES, noise_keyword_hits
from poc.metrics import extract_anchors, score_extraction, scores_to_dict
from chromerag import ChromeRAG, ContentPriority, PipelineConfig, learn_then_extract
from chromerag.batch import BatchPage
from chromerag.site_chrome import save_chrome_models

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "outputs"
MODELS = ROOT / "data" / "chrome_models"
OUT.mkdir(parents=True, exist_ok=True)
MODELS.mkdir(parents=True, exist_ok=True)

# Gates for "satisfying" on scoreable pages
MIN_AVG_RECALL = 0.70
MIN_AVG_FBAL = 0.80
MAX_AVG_NOISE_RET = 0.05


def load_pages() -> list[BatchPage]:
    pages = []
    for meta_path in sorted(RAW.glob("*.meta.json")):
        if meta_path.name.startswith("_"):
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        html_path = RAW / f"{meta['id']}.html"
        if not html_path.exists():
            continue
        pages.append(
            BatchPage(
                html=html_path.read_text(encoding="utf-8", errors="ignore"),
                url=meta.get("url"),
                page_id=meta["id"],
            )
        )
    return pages


def stage_smoke() -> None:
    print("\n== STAGE 1: smoke ==")
    sample = "<html><head><title>T</title><script type='application/ld+json'>"
    sample += '{"@type":"TechArticle","name":"Demo"}'
    sample += "</script></head><body><main><h1>Hello</h1><p>Content about widgets.</p>"
    sample += "<nav>Home About Careers</nav></main></body></html>"
    r = ChromeRAG().extract(sample, url="https://example.com/docs/demo")
    assert "Hello" in r.markdown
    assert r.front_matter.get("title") or r.front_matter.get("type")
    print("  smoke OK", "tokens=", r.tokens_estimate, "fm=", list(r.front_matter)[:4])


def stage_batch(pages: list[BatchPage]) -> dict:
    print(f"\n== STAGE 2: learn-then-extract ({len(pages)} pages) ==")
    cfg = PipelineConfig.from_priority(
        ContentPriority.BALANCED,
        stce_min_pages=3,
        stce_frequency=0.85,
        stce_max_block_chars=1500,
    )
    # Host-level mining so multi-page sites share chrome
    results, models = learn_then_extract(
        pages, config=cfg, learn=True, path_prefix_depth=0
    )
    save_chrome_models(models, MODELS / "corpus_host.json")
    active = {k: len(m.signatures) for k, m in models.items() if m.signatures}
    print("  chrome groups with sigs:", active or "(none — need ≥3 pages/host)")

    rows = []
    for br in results:
        assert br.page_id
        page_out = OUT / br.page_id
        page_out.mkdir(parents=True, exist_ok=True)
        (page_out / "chromerag.md").write_text(br.result.markdown, encoding="utf-8")
        (page_out / "smart_rag_extractor.md").write_text(br.result.markdown, encoding="utf-8")
        rows.append(
            {
                "id": br.page_id,
                "tokens": br.result.tokens_estimate,
                "stce": br.stce_applied,
                "stce_rm": br.result.diagnostics.get("stce_removed", 0),
                "json_ld": br.result.diagnostics.get("schema_sources", {}).get(
                    "json_ld_count", 0
                ),
                "noise_kw": sum(noise_keyword_hits(br.result.markdown).values()),
            }
        )
        print(
            f"  {br.page_id:32s} tok={rows[-1]['tokens']:6d} "
            f"stce={rows[-1]['stce']} rm={rows[-1]['stce_rm']} "
            f"jsonld={rows[-1]['json_ld']}"
        )
    return {"pages": rows, "chrome_active": active}


def stage_metrics(pages: list[BatchPage]) -> dict:
    print("\n== STAGE 3: anchor metrics vs baselines ==")
    by_method: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    page_rows = {}
    failures = []

    for page in pages:
        assert page.page_id
        content_ng, noise_ng, diag = extract_anchors(page.html)
        methods: dict[str, str] = {}
        # ours
        md_path = OUT / page.page_id / "chromerag.md"
        if md_path.exists():
            methods["chromerag"] = md_path.read_text(encoding="utf-8", errors="ignore")
        # priority variants for tradeoff check
        for pri in (ContentPriority.PRECISION, ContentPriority.COVERAGE):
            r = ChromeRAG(config=PipelineConfig.from_priority(pri)).extract(
                page.html, url=page.url
            )
            methods[f"chromerag_{pri.value}"] = r.markdown
            (OUT / page.page_id / f"chromerag_{pri.value}.md").write_text(
                r.markdown, encoding="utf-8"
            )
        for name, fn in BASELINES.items():
            try:
                methods[name] = fn(page.html)
            except Exception as exc:  # noqa: BLE001
                methods[name] = ""
                print(f"  baseline {name} fail on {page.page_id}: {exc}")

        scored = {}
        for name, text in methods.items():
            if not text or (text.startswith("[") and "not installed" in text):
                continue
            s = score_extraction(name, text, content_ng, noise_ng, diag)
            scored[name] = scores_to_dict(s)

        ours_ok = scored.get("chromerag", {}).get("content_recall", 0) >= 0.05
        page_rows[page.page_id] = {
            "anchors": diag,
            "ours_scoreable": ours_ok,
            "methods": scored,
        }
        if ours_ok:
            for name, s in scored.items():
                for k in (
                    "content_recall",
                    "noise_retention",
                    "f_balanced",
                    "tokens",
                ):
                    by_method[name][k].append(float(s[k]))
        else:
            failures.append(
                {
                    "id": page.page_id,
                    "reason": "chromerag_recall_near_zero",
                    "best_other": max(
                        (
                            (n, m["content_recall"])
                            for n, m in scored.items()
                            if n != "chromerag"
                        ),
                        key=lambda x: x[1],
                        default=("none", 0.0),
                    ),
                }
            )
            print(f"  FAIL scoreable {page.page_id}: near-zero recall")

    summary = {}
    for method, metrics in by_method.items():
        if not metrics["content_recall"]:
            continue
        summary[method] = {
            "n": len(metrics["content_recall"]),
            "avg_recall": round(sum(metrics["content_recall"]) / len(metrics["content_recall"]), 4),
            "avg_noise_ret": round(
                sum(metrics["noise_retention"]) / len(metrics["noise_retention"]), 4
            ),
            "avg_fbal": round(sum(metrics["f_balanced"]) / len(metrics["f_balanced"]), 4),
            "avg_tokens": round(sum(metrics["tokens"]) / len(metrics["tokens"]), 1),
        }

    print("\n  method averages (scoreable pages):")
    for method, s in sorted(summary.items(), key=lambda x: -x[1]["avg_fbal"]):
        print(
            f"  {method:24s} n={s['n']:2d} recall={s['avg_recall']:.3f} "
            f"noise={s['avg_noise_ret']:.3f} Fbal={s['avg_fbal']:.3f} tok={s['avg_tokens']:.0f}"
        )

    return {"summary": summary, "pages": page_rows, "failures": failures}


def stage_gate(metrics: dict) -> bool:
    print("\n== STAGE 4: quality gates ==")
    s = metrics["summary"].get("chromerag")
    if not s:
        print("  GATE FAIL: no chromerag scoreable pages")
        return False
    ok = True
    checks = [
        ("avg_recall", s["avg_recall"], MIN_AVG_RECALL, ">="),
        ("avg_fbal", s["avg_fbal"], MIN_AVG_FBAL, ">="),
        ("avg_noise_ret", s["avg_noise_ret"], MAX_AVG_NOISE_RET, "<="),
    ]
    for name, val, thr, op in checks:
        passed = val >= thr if op == ">=" else val <= thr
        print(f"  {'PASS' if passed else 'FAIL'} {name}={val} ({op} {thr})")
        ok = ok and passed

    # Must beat trafilatura Fbal when both present
    traf = metrics["summary"].get("trafilatura")
    if traf and s["avg_fbal"] + 0.02 < traf["avg_fbal"]:
        print(
            f"  FAIL Fbal behind trafilatura ({s['avg_fbal']} < {traf['avg_fbal']})"
        )
        ok = False
    elif traf:
        print(f"  PASS Fbal vs trafilatura ({s['avg_fbal']} >= {traf['avg_fbal'] - 0.02})")

    # Priority tradeoff sanity: coverage recall >= precision recall
    cov = metrics["summary"].get("chromerag_coverage")
    prec = metrics["summary"].get("chromerag_precision")
    if cov and prec:
        if cov["avg_recall"] + 0.01 < prec["avg_recall"]:
            print("  FAIL coverage recall < precision recall")
            ok = False
        else:
            print(
                f"  PASS priority tradeoff coverage_recall={cov['avg_recall']} "
                f">= precision_recall={prec['avg_recall']}"
            )

    n_fail = len(metrics.get("failures", []))
    print(f"  unscored/JS-shell failures: {n_fail}")
    return ok


def main() -> int:
    stage_smoke()
    pages = load_pages()
    if not pages:
        print("No fixtures — run: python -m poc.fetch_pages")
        return 2
    print(f"Loaded {len(pages)} fixtures")
    batch_info = stage_batch(pages)
    metrics = stage_metrics(pages)
    report = {
        "batch": batch_info,
        "metrics": {
            "summary": metrics["summary"],
            "failures": metrics["failures"],
        },
        "gates": {
            "min_avg_recall": MIN_AVG_RECALL,
            "min_avg_fbal": MIN_AVG_FBAL,
            "max_avg_noise_ret": MAX_AVG_NOISE_RET,
        },
    }
    passed = stage_gate(metrics)
    report["passed"] = passed
    out_path = OUT / "qa_loop_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    # slim md
    lines = [
        "# ChromeRAG QA Loop",
        "",
        f"Fixtures: {len(pages)}  Passed: {passed}",
        "",
        "| Method | n | Recall | Noise ret | Fbal | Tokens |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method, s in sorted(
        metrics["summary"].items(), key=lambda x: -x[1]["avg_fbal"]
    ):
        lines.append(
            f"| `{method}` | {s['n']} | {s['avg_recall']:.3f} | "
            f"{s['avg_noise_ret']:.3f} | {s['avg_fbal']:.3f} | {s['avg_tokens']:.0f} |"
        )
    if metrics["failures"]:
        lines += ["", "## Unscored / near-zero recall", ""]
        for f in metrics["failures"]:
            lines.append(f"- `{f['id']}` — {f['reason']} (best other: {f['best_other']})")
    (OUT / "qa_loop_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {out_path}")
    print(f"Wrote {OUT / 'qa_loop_summary.md'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
