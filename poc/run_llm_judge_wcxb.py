"""Blind pairwise LLM judgement on a stratified sample of the WCXB test split.

Same prompt, model and scoring as poc/run_llm_judge.py. Sample: N pages per WCXB page type (seeded),
ChromeRAG in balanced mode against Trafilatura, MarkItDown and Readability, 20% of pairs repeated with
swapped positions. Source text for the judge is the page's visible text, not the reference annotation.

  python -m poc.run_llm_judge_wcxb --per-type 15      # needs OPENAI_API_KEY, spends money
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from poc.baselines import BASELINES
from poc.openai_client import BudgetExceeded, OpenAI, spent
from poc.run_llm_judge import MODEL, SEED, SWAP_SHARE, SYSTEM, _FRONT_MATTER, _judge, summarize, visible_text
from poc.wcxb import load_split

ROOT = Path(__file__).resolve().parents[1]
FINAL = ROOT / "evaluations" / "2026-10-v0.1.3" / "FINAL"
BASE = ("trafilatura", "markitdown", "readability")


def build_jobs(per_type: int) -> tuple[list[dict], list[dict]]:
    from chromerag import ChromeRAG, ContentPriority, PipelineConfig

    rng = random.Random(SEED)
    pages = load_split("test")
    by_type: dict[str, list] = defaultdict(list)
    for p in pages:
        by_type[p.page_type].append(p)
    chosen = []
    for t in sorted(by_type):
        group = sorted(by_type[t], key=lambda p: p.id)
        rng.shuffle(group)
        chosen += group[:per_type]
    jobs, sample = [], []
    rag = ChromeRAG(config=PipelineConfig.from_priority(ContentPriority.BALANCED))
    for p in chosen:
        ours = _FRONT_MATTER.sub("", rag.extract(p.html, url=p.url or None).markdown)
        source = visible_text(p.html)
        sample.append({"id": p.id, "type": p.page_type, "url": p.url})
        for base in BASE:
            try:
                theirs = _FRONT_MATTER.sub("", BASELINES[base](p.html) or "")
            except Exception:  # noqa: BLE001
                continue
            if not ours.strip() or not theirs.strip():
                continue
            ours_is_a = rng.random() < 0.5
            pair = {"corpus": "benchmark", "id": p.id, "category": p.page_type, "baseline": base,
                    "source": source, "ref": ours, "base": theirs}
            jobs.append({**pair, "ours_is_a": ours_is_a, "swapped": False})
            if rng.random() < SWAP_SHARE:
                jobs.append({**pair, "ours_is_a": not ours_is_a, "swapped": True})
    return jobs, sample


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-type", type=int, default=15)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    jobs, sample = build_jobs(a.per_type)
    print(f"{len(sample)} pages, {len(jobs)} judgements; spent so far ${spent():.3f}")
    if a.dry_run:
        return
    client, results = OpenAI(), []
    try:
        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            for r in pool.map(lambda j: _judge(client, j), jobs):
                if r is not None:
                    results.append(r)
    except BudgetExceeded as exc:
        print(f"Stopped: {exc}")
    by_type = {}
    for t in sorted({s["type"] for s in sample}):
        rows = [r for r in results if r["category"] == t and not r["swapped"]]
        for base in BASE:
            sub = [r for r in rows if r["baseline"] == base]
            if sub:
                by_type[f"{t}:{base}"] = {"pairs": len(sub), "chromerag_wins": round(sum(r["winner"] == "chromerag" for r in sub) / len(sub), 3),
                                          "baseline_wins": round(sum(r["winner"] == "baseline" for r in sub) / len(sub), 3)}
    summary = summarize(results)
    report = {"model": MODEL, "sample": f"{a.per_type} WCXB test pages per page type; ChromeRAG balanced vs baselines",
              "seed": SEED, "n_pages": len(sample), "pages": sample, "n_judgements": len(results),
              "cost_usd": round(sum(r["cost_usd"] for r in results), 4), "summary": summary,
              "by_type": by_type, "judgements": results}
    FINAL.mkdir(parents=True, exist_ok=True)
    (FINAL / "llm_judge_wcxb_test.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k.startswith("all:") or k == "position_consistency"}, indent=1))
    print(json.dumps(by_type, indent=1))
    print(f"cost ${report['cost_usd']:.3f}; total OpenAI spend ${spent():.3f}")


if __name__ == "__main__":
    main()
