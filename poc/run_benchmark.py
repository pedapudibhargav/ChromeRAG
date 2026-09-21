"""Run chromerag vs baselines on fetched fixtures."""

from __future__ import annotations

import json
import traceback
from pathlib import Path

from poc.baselines import BASELINES, estimate_tokens, noise_keyword_hits
from chromerag import ChromeRAG

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)


def load_fixtures() -> list[tuple[str, str, dict]]:
    fixtures = []
    for meta_path in sorted(RAW.glob("*.meta.json")):
        if meta_path.name.startswith("_"):
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        html_path = RAW / f"{meta['id']}.html"
        if not html_path.exists():
            continue
        fixtures.append((meta["id"], html_path.read_text(encoding="utf-8", errors="ignore"), meta))
    return fixtures


def run() -> dict:
    extractor = ChromeRAG()
    report: dict = {"pages": {}, "summary": {}}
    method_token_sums: dict[str, list[int]] = {}
    method_noise_sums: dict[str, list[int]] = {}

    fixtures = load_fixtures()
    if not fixtures:
        print("No fixtures in data/raw — run: python -m poc.fetch_pages")
        return report

    for page_id, html, meta in fixtures:
        page_out = OUT / page_id
        page_out.mkdir(parents=True, exist_ok=True)
        page_report: dict = {"meta": meta, "methods": {}}

        # Ours
        try:
            result = extractor.extract(html, url=meta.get("url"))
            (page_out / "chromerag.md").write_text(result.markdown, encoding="utf-8")
            noise = noise_keyword_hits(result.markdown)
            page_report["methods"]["chromerag"] = {
                "tokens": result.tokens_estimate,
                "n_blocks_in": result.n_blocks_in,
                "n_blocks_kept": result.n_blocks_kept,
                "n_tables": result.n_tables,
                "front_matter": result.front_matter,
                "noise_hits": noise,
                "noise_total": sum(noise.values()),
                "chars": len(result.markdown),
                "diagnostics": result.diagnostics,
            }
        except Exception as exc:  # noqa: BLE001
            page_report["methods"]["chromerag"] = {
                "error": str(exc),
                "trace": traceback.format_exc()[-800:],
            }

        for name, fn in BASELINES.items():
            try:
                text = fn(html)
                (page_out / f"{name}.md").write_text(text, encoding="utf-8")
                toks = estimate_tokens(text)
                noise = noise_keyword_hits(text)
                page_report["methods"][name] = {
                    "tokens": toks,
                    "chars": len(text),
                    "noise_hits": noise,
                    "noise_total": sum(noise.values()),
                }
            except Exception as exc:  # noqa: BLE001
                page_report["methods"][name] = {"error": str(exc)}

        report["pages"][page_id] = page_report
        print(f"\n=== {page_id} ({meta.get('category')}) ===")
        for method, stats in page_report["methods"].items():
            if "error" in stats:
                print(f"  {method:24s} ERROR: {stats['error'][:100]}")
                continue
            print(
                f"  {method:24s} tokens={stats['tokens']:6d}  "
                f"noise={stats['noise_total']:3d}  chars={stats['chars']}"
            )
            method_token_sums.setdefault(method, []).append(stats["tokens"])
            method_noise_sums.setdefault(method, []).append(stats["noise_total"])

    summary = {}
    for method, vals in method_token_sums.items():
        noises = method_noise_sums.get(method, [])
        summary[method] = {
            "pages": len(vals),
            "avg_tokens": round(sum(vals) / len(vals), 1),
            "avg_noise_hits": round(sum(noises) / max(1, len(noises)), 2),
            "total_tokens": sum(vals),
            "total_noise_hits": sum(noises),
        }
    report["summary"] = summary

    out_path = OUT / "benchmark_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\n===== SUMMARY (avg tokens / avg noise keyword hits) =====")
    for method, s in sorted(summary.items(), key=lambda x: x[1]["avg_tokens"]):
        print(f"  {method:24s} avg_tokens={s['avg_tokens']:8.1f}  avg_noise={s['avg_noise_hits']:5.2f}")
    print(f"\nWrote {out_path}")
    return report


if __name__ == "__main__":
    run()
