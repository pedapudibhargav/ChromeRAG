"""Evaluate extractors on WCXB with per-page JSON output."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from chromerag import ChromeRAG, ContentPriority, PipelineConfig

from poc.baselines import BASELINES
from poc.wcxb import load_split, snippet_rate, strip_front_matter, word_f1

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "evaluations" / "2026-10-v0.1.3"
BASELINE_PATH = ROOT / "evaluations" / "2026-09-v0.1.2-baseline" / "wcxb_dev_v012_per_page.json"

TOOL_CHROMERAG = {
    "chromerag_coverage": ContentPriority.COVERAGE,
    "chromerag": ContentPriority.BALANCED,
}
TOOL_BASELINES = ("trafilatura", "markitdown", "readability")

TYPE_ORDER = (
    "article",
    "forum",
    "product",
    "collection",
    "listing",
    "documentation",
    "service",
)


def _extract(tool: str, html: str) -> str:
    if tool in TOOL_CHROMERAG:
        return ChromeRAG(
            config=PipelineConfig.from_priority(TOOL_CHROMERAG[tool], enable_dvdf=True)
        ).extract(html).markdown
    fn = BASELINES[tool]
    return fn(html)


def _score_page(args: tuple) -> dict:
    page_dict, tools = args
    row: dict = {"id": page_dict["id"], "type": page_dict["page_type"]}
    ref = page_dict["main_content"]
    for tool in tools:
        t0 = time.perf_counter()
        try:
            pred = strip_front_matter(_extract(tool, page_dict["html"]))
        except Exception as exc:  # noqa: BLE001
            row[tool] = {"error": str(exc), "ms": (time.perf_counter() - t0) * 1000}
            continue
        ms = (time.perf_counter() - t0) * 1000
        p, r, f1 = word_f1(pred, ref)
        row[tool] = {
            "p": p,
            "r": r,
            "f1": f1,
            "with": snippet_rate(pred, page_dict["with_snippets"]),
            "without": snippet_rate(pred, page_dict["without_snippets"]),
            "ms": ms,
        }
    return row


def _mean(rows: list[dict], tool: str, key: str) -> float:
    vals = [r[tool][key] for r in rows if tool in r and key in r[tool]]
    return sum(vals) / len(vals) if vals else 0.0


def _print_table(rows: list[dict], tools: list[str]) -> None:
    by_type: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_type[row["type"]].append(row)

    print(f"\n{'type':<16} {'n':>5}", end="")
    for tool in tools:
        print(f" {tool[:12]:>12}", end="")
    print()
    print("-" * (22 + 13 * len(tools)))

    for pt in TYPE_ORDER:
        group = by_type.get(pt, [])
        if not group:
            continue
        print(f"{pt:<16} {len(group):>5}", end="")
        for tool in tools:
            print(f" {_mean(group, tool, 'f1'):>12.3f}", end="")
        print()

    print(f"{'ALL':<16} {len(rows):>5}", end="")
    for tool in tools:
        print(f" {_mean(rows, tool, 'f1'):>12.3f}", end="")
    print()

    print("\nMeans (all pages):")
    for tool in tools:
        print(
            f"  {tool}: P={_mean(rows, tool, 'p'):.3f} "
            f"R={_mean(rows, tool, 'r'):.3f} "
            f"with={_mean(rows, tool, 'with'):.3f} "
            f"without={_mean(rows, tool, 'without'):.3f}"
        )


def _compare(current: list[dict], baseline_path: Path, tools: list[str]) -> None:
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    base_by_id = {r["id"]: r for r in baseline}
    by_type: dict[str, list[tuple[float, float]]] = defaultdict(list)
    all_deltas: list[float] = []

    for row in current:
        base = base_by_id.get(row["id"])
        if not base:
            continue
        tool = "chromerag_coverage"
        if tool not in row or tool not in base:
            continue
        delta = row[tool]["f1"] - base[tool]["f1"]
        all_deltas.append(delta)
        by_type[row["type"]].append((delta, 1.0))

    print(f"\nDelta F1 vs {baseline_path.name} (chromerag_coverage):")
    for pt in TYPE_ORDER + ("ALL",):
        if pt == "ALL":
            deltas = all_deltas
        else:
            deltas = [d for d, _ in by_type.get(pt, [])]
        if not deltas:
            continue
        mean_d = sum(deltas) / len(deltas)
        print(f"  {pt:<16} n={len(deltas):>4}  delta={mean_d:+.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="WCXB evaluation harness")
    parser.add_argument("--split", default="dev", choices=["dev", "test", "heldout", "all"])
    parser.add_argument(
        "--tools",
        default="chromerag_coverage,chromerag,trafilatura,markitdown,readability",
        help="Comma-separated tool names",
    )
    parser.add_argument("--out", type=Path, default=EVAL_DIR / "wcxb_dev_wp0.json")
    parser.add_argument("--compare", type=Path, default=None, help="Baseline per-page JSON")
    parser.add_argument(
        "--final",
        action="store_true",
        help="Required for test/heldout splits (writes to FINAL/)",
    )
    args = parser.parse_args()

    if args.split in {"test", "heldout"} and not args.final:
        parser.error(f"--split {args.split} requires --final")

    if args.split in {"test", "heldout", "fresh"} or (
        args.final and args.split != "dev"
    ):
        final_dir = EVAL_DIR / "FINAL"
        final_dir.mkdir(parents=True, exist_ok=True)
        if args.out == EVAL_DIR / "wcxb_dev_wp0.json":
            args.out = final_dir / f"wcxb_{args.split}.json"
        print(
            "WARNING: final evaluation run — do not tune on this split.",
            file=sys.stderr,
        )

    tools = [t.strip() for t in args.tools.split(",") if t.strip()]
    pages = load_split(args.split if args.split != "all" else "dev")
    if args.split == "all":
        pages = pages + load_split("test")

    print(f"Loaded {len(pages)} pages ({args.split})")
    page_dicts = [
        {
            "id": p.id,
            "page_type": p.page_type,
            "html": p.html,
            "main_content": p.main_content,
            "with_snippets": p.with_snippets,
            "without_snippets": p.without_snippets,
        }
        for p in pages
    ]

    workers = os.cpu_count() or 1
    with ProcessPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(_score_page, [(pd, tools) for pd in page_dicts]))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}")

    _print_table(rows, tools)
    if args.compare:
        _compare(rows, args.compare, tools)
    elif args.split == "dev" and BASELINE_PATH.exists():
        _compare(rows, BASELINE_PATH, tools)


if __name__ == "__main__":
    main()
