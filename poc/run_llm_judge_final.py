"""Blind pairwise LLM judgement on the held-out landing companies and the fresh companies.

Same prompt, model, reference mode and scoring as poc/run_llm_judge.py (see that file); only the page
sample differs: pages of the companies listed under "heldout" in poc/landing_split.json plus pages of
the fresh companies (poc/landing_companies_fresh.json), none of which were used for development.

  python -m poc.run_llm_judge_final --heldout 50 --fresh 50      # needs OPENAI_API_KEY, spends money
"""

from __future__ import annotations

import argparse
import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from poc.landing_corpus import RAW as LANDING_RAW
from poc.openai_client import BudgetExceeded, OpenAI, spent
from poc.run_corpus_comparison import OUT, load_ok_pages
from poc.run_llm_judge import MODEL, SEED, SYSTEM, _jobs, _judge, summarize

ROOT = Path(__file__).resolve().parents[1]
FINAL = ROOT / "evaluations" / "2026-10-v0.1.3" / "FINAL"


def _items(rng: random.Random, n_heldout: int, n_fresh: int) -> list[dict]:
    split = json.loads((ROOT / "poc" / "landing_split.json").read_text(encoding="utf-8"))
    held = set(split["heldout"])
    pages = [(p, h, m) for p, h, m in load_ok_pages(LANDING_RAW) if m.get("company") in held]
    fresh = load_ok_pages(ROOT / "data" / "landing_fresh_raw")
    rng.shuffle(pages)
    rng.shuffle(fresh)
    items = []
    for pid, html, meta in pages[:n_heldout]:
        items.append({"corpus": "landing", "id": pid, "html": html, "meta": meta, "outputs": OUT / "landing" / pid})
    for pid, html, meta in fresh[:n_fresh]:
        items.append({"corpus": "benchmark", "id": pid, "html": html, "meta": meta, "outputs": OUT / "landing_fresh" / pid})
    return items


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--heldout", type=int, default=50)
    p.add_argument("--fresh", type=int, default=50)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    rng = random.Random(SEED)
    jobs = _jobs(_items(rng, args.heldout, args.fresh), rng)
    print(f"{len(jobs)} judgements; spent so far ${spent():.3f}")
    if args.dry_run:
        return
    client, results = OpenAI(), []
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for r in pool.map(lambda j: _judge(client, j), jobs):
                if r is not None:
                    results.append(r)
    except BudgetExceeded as exc:
        print(f"Stopped: {exc}")
    # In the summary "landing" = held-out companies, "benchmark" = fresh companies.
    report = {"model": MODEL, "sample": "held-out landing companies (corpus=landing) + fresh companies (corpus=benchmark)",
              "seed": SEED, "system_prompt": SYSTEM, "n_judgements": len(results),
              "cost_usd": round(sum(r["cost_usd"] for r in results), 4), "summary": summarize(results), "judgements": results}
    FINAL.mkdir(parents=True, exist_ok=True)
    (FINAL / "llm_judge_final.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"cost ${report['cost_usd']:.3f}; total OpenAI spend ${spent():.3f}")


if __name__ == "__main__":
    main()
