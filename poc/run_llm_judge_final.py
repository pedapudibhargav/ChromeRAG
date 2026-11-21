"""Blind pairwise LLM judgement on the held-out landing companies and the fresh companies.

Same model and scoring shape as poc/run_llm_judge.py; uses the neutral 2026-11 page rubric
from evaluations/2026-11-final/RUBRIC.md. A/B order is randomized per page with a stored seed;
tool names stay hidden.

  python -m poc.run_llm_judge_final --heldout 50 --fresh 50      # needs OPENAI_API_KEY, spends money
"""

from __future__ import annotations

import argparse
import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from poc.eval_rubric import page_judge_prompt
from poc.landing_corpus import RAW as LANDING_RAW
from poc.openai_client import BudgetExceeded, OpenAI, spent
from poc.run_corpus_comparison import OUT, load_ok_pages
from poc.run_llm_judge import (
    _FRONT_MATTER,
    BASELINES,
    MODEL,
    REFERENCE,
    SEED,
    SWAP_SHARE,
    _prompt,
    summarize,
    visible_text,
)

ROOT = Path(__file__).resolve().parents[1]
FINAL = ROOT / "evaluations" / "2026-10-v0.1.3" / "FINAL"
PAGE_SYSTEM = page_judge_prompt()


def _page_ab_seed(page_id: str) -> int:
    return int.from_bytes(f"{SEED}:{page_id}".encode(), "big") % (2**32)


def _jobs(items: list[dict], rng: random.Random) -> list[dict]:
    jobs = []
    for item in items:
        source = visible_text(item["html"])
        texts = {
            m: _FRONT_MATTER.sub("", (item["outputs"] / f"{m}.md").read_text(encoding="utf-8"))
            for m in (REFERENCE, *BASELINES)
            if (item["outputs"] / f"{m}.md").exists()
        }
        ab_seed = _page_ab_seed(item["id"])
        # One A/B assignment per page (shared across baselines); seed stored for audit.
        ours_is_a = random.Random(ab_seed).random() < 0.5
        for base in BASELINES:
            if REFERENCE not in texts or base not in texts:
                continue
            pair = {
                "corpus": item["corpus"],
                "id": item["id"],
                "category": item["meta"].get("category"),
                "baseline": base,
                "source": source,
                "ref": texts[REFERENCE],
                "base": texts[base],
                "ab_seed": ab_seed,
            }
            jobs.append({**pair, "ours_is_a": ours_is_a, "swapped": False})
            if rng.random() < SWAP_SHARE:
                jobs.append({**pair, "ours_is_a": not ours_is_a, "swapped": True})
    return jobs


def _judge_page(client: OpenAI, job: dict) -> dict | None:
    a, b = (job["ref"], job["base"]) if job["ours_is_a"] else (job["base"], job["ref"])
    try:
        verdict, cost = client.chat_json(MODEL, PAGE_SYSTEM, _prompt(job["source"], a, b))
    except (RuntimeError, ValueError) as exc:
        print(f"  skipped {job['id']} vs {job['baseline']}: {str(exc)[:120]}")
        return None
    better = str(verdict.get("better", "tie")).strip().upper()
    ours, theirs = ("A", "B") if job["ours_is_a"] else ("B", "A")
    winner = "chromerag" if better == ours else ("baseline" if better == theirs else "tie")
    return {
        "corpus": job["corpus"],
        "id": job["id"],
        "category": job["category"],
        "baseline": job["baseline"],
        "swapped": job["swapped"],
        "ours_is_a": job["ours_is_a"],
        "ab_seed": job["ab_seed"],
        "winner": winner,
        "content_ours": verdict.get(f"content_{ours}"),
        "content_base": verdict.get(f"content_{theirs}"),
        "chrome_ours": verdict.get(f"chrome_{ours}"),
        "chrome_base": verdict.get(f"chrome_{theirs}"),
        "reason": str(verdict.get("reason", ""))[:300],
        "cost_usd": round(cost, 6),
    }


def _items(rng: random.Random, n_heldout: int, n_fresh: int) -> list[dict]:
    split = json.loads((ROOT / "poc" / "landing_split.json").read_text(encoding="utf-8"))
    held = set(split["heldout"])
    pages = [(p, h, m) for p, h, m in load_ok_pages(LANDING_RAW) if m.get("company") in held]
    fresh = load_ok_pages(ROOT / "data" / "landing_fresh_raw")
    rng.shuffle(pages)
    rng.shuffle(fresh)
    items = []
    for pid, html, meta in pages[:n_heldout]:
        items.append(
            {
                "corpus": "landing",
                "id": pid,
                "html": html,
                "meta": meta,
                "outputs": OUT / "landing" / pid,
            }
        )
    for pid, html, meta in fresh[:n_fresh]:
        items.append(
            {
                "corpus": "benchmark",
                "id": pid,
                "html": html,
                "meta": meta,
                "outputs": OUT / "landing_fresh" / pid,
            }
        )
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
    print(
        f"{len(jobs)} judgements; blind A/B per page (ab_seed stored); "
        f"tool names hidden; spent so far ${spent():.3f}"
    )
    if args.dry_run:
        return
    client, results = OpenAI(), []
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for r in pool.map(lambda j: _judge_page(client, j), jobs):
                if r is not None:
                    results.append(r)
    except BudgetExceeded as exc:
        print(f"Stopped: {exc}")
    report = {
        "model": MODEL,
        "sample": "held-out landing companies (corpus=landing) + fresh companies (corpus=benchmark)",
        "seed": SEED,
        "page_rubric": "evaluations/2026-11-final/RUBRIC.md",
        "blinding": {
            "tool_names_hidden": True,
            "ab_randomized_per_page": True,
            "ab_seed": "hash(SEED, page_id)",
        },
        "system_prompt": PAGE_SYSTEM,
        "n_judgements": len(results),
        "cost_usd": round(sum(r["cost_usd"] for r in results), 4),
        "summary": summarize(results),
        "judgements": results,
    }
    FINAL.mkdir(parents=True, exist_ok=True)
    (FINAL / "llm_judge_final.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"cost ${report['cost_usd']:.3f}; total OpenAI spend ${spent():.3f}")


if __name__ == "__main__":
    main()
