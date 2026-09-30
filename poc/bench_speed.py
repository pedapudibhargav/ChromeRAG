"""Sequential single-process speed benchmark (200 fixed pages)."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from chromerag import ChromeRAG, ContentPriority, PipelineConfig

from poc.baselines import BASELINES

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
LANDING_RAW = ROOT / "data" / "landing_raw"
SPEED_PAGES = ROOT / "poc" / "speed_pages.json"
EVAL_DIR = ROOT / "evaluations" / "2026-10-v0.1.3"

TOOLS = {
    "chromerag_coverage": lambda html: ChromeRAG(
        config=PipelineConfig.from_priority(ContentPriority.COVERAGE)
    ).extract(html).markdown,
    "trafilatura": BASELINES["trafilatura"],
    "markitdown": BASELINES["markitdown"],
    "readability": BASELINES["readability"],
}


def _sorted_ids(raw_dir: Path, n: int) -> list[str]:
    ids: list[str] = []
    for meta_path in sorted(raw_dir.glob("*.meta.json")):
        if meta_path.name.startswith("_"):
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        page_id = meta["id"]
        if (raw_dir / f"{page_id}.html").exists():
            ids.append(page_id)
        if len(ids) >= n:
            break
    return ids


def _ensure_speed_pages() -> list[tuple[str, Path]]:
    if SPEED_PAGES.exists():
        payload = json.loads(SPEED_PAGES.read_text(encoding="utf-8"))
        return [(e["id"], Path(e["path"])) for e in payload["pages"]]

    doc_ids = _sorted_ids(RAW, 100)
    land_ids = _sorted_ids(LANDING_RAW, 100)
    pages: list[tuple[str, Path]] = []
    for page_id in doc_ids:
        pages.append((page_id, RAW / f"{page_id}.html"))
    for page_id in land_ids:
        pages.append((page_id, LANDING_RAW / f"{page_id}.html"))

    SPEED_PAGES.write_text(
        json.dumps(
            {
                "pages": [{"id": pid, "path": str(path.relative_to(ROOT))} for pid, path in pages],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return pages


def _bench_tool(name: str, fn, htmls: list[str], *, passes: int = 3) -> dict:
    # Warm-up
    for html in htmls[:5]:
        fn(html)

    pass_medians: list[float] = []
    all_times: list[float] = []
    for _ in range(passes):
        times: list[float] = []
        t0 = time.perf_counter()
        for html in htmls:
            t_page = time.perf_counter()
            fn(html)
            times.append((time.perf_counter() - t_page) * 1000)
        all_times.extend(times)
        pass_medians.append(statistics.median(times))

    median_ms = statistics.median(pass_medians)
    sorted_times = sorted(all_times)
    p95 = sorted_times[int(0.95 * len(sorted_times)) - 1] if sorted_times else 0.0
    pps = 1000.0 / median_ms if median_ms > 0 else 0.0
    return {
        "median_ms_per_page": round(median_ms, 3),
        "p95_ms_per_page": round(p95, 3),
        "pages_per_second": round(pps, 3),
        "n_pages": len(htmls),
        "passes": passes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="baseline", choices=["baseline", "wp1", "final"])
    args = parser.parse_args()

    page_refs = _ensure_speed_pages()
    htmls = [path.read_text(encoding="utf-8", errors="ignore") for _, path in page_refs]
    print(f"Benchmarking {len(htmls)} pages (sequential, 1 process)")

    report: dict = {"label": args.label, "tools": {}}
    for tool, fn in TOOLS.items():
        print(f"  {tool}...", flush=True)
        report["tools"][tool] = _bench_tool(tool, fn, htmls)
        t = report["tools"][tool]
        print(f"    median={t['median_ms_per_page']:.1f}ms  p95={t['p95_ms_per_page']:.1f}ms  pps={t['pages_per_second']:.1f}")

    out = EVAL_DIR / f"speed_{args.label}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
