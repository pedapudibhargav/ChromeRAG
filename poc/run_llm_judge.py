"""Blind pairwise LLM judgement of extraction quality for RAG.

For a seeded sample of pages, the judge sees the page's own visible text (from the input
HTML, independent of any tool) and two extractions labelled only A and B, and decides which
is better for indexing in a RAG system: keeps the substantive page content, drops navigation,
footers, cookie banners and other site chrome. Tool identity is hidden and A/B assignment is
randomized; a share of pairs is judged a second time with A and B swapped to measure position
bias. Unlike the anchor metric, the judge also covers pages without <main>/<article>.
ChromeRAG's YAML front-matter is removed before judging (as in the retrieval evaluation):
it is structured metadata, attached to chunks rather than embedded as text, and a first run
showed the judge counting it as chrome (that run is kept as llm_judge_report_with_front_matter.json).

Usage:
  python -m poc.run_llm_judge --landing 150 --docs 100      # needs OPENAI_API_KEY
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup

from poc.landing_corpus import RAW as LANDING_RAW
from poc.openai_client import BudgetExceeded, OpenAI, spent
from poc.run_corpus_comparison import MIN_CONTENT_ANCHORS, OUT, RAW, load_ok_pages

MODEL = "gpt-5.6-luna"
REFERENCE = "chromerag_coverage"
BASELINES = ("trafilatura", "markitdown")
SOURCE_CHARS = 6000
OUTPUT_HEAD_CHARS = 4500
OUTPUT_TAIL_CHARS = 1500
SWAP_SHARE = 0.2
SEED = 7
BOOTSTRAP_ITERS = 2000

SYSTEM = """You evaluate HTML-to-text extraction for retrieval-augmented generation (RAG).
You get the visible text of a web page (it includes the page's real content and its site
chrome) and two extractions of that page, A and B. For RAG, a good extraction keeps the
page's substantive content (what the page is about: descriptions, product details, prices,
features, instructions, tables) and drops site chrome (navigation menus, headers and footers,
cookie/consent banners, newsletter or sign-up prompts, repeated calls to action, social links,
legal boilerplate). Losing real content is worse than keeping a little chrome.
Long extractions may be shortened with "[...]" in the middle; judge what you can see.
Answer with JSON only:
{"better": "A" | "B" | "tie",
 "content_A": 1-5, "content_B": 1-5,   (5 = all substantive content kept)
 "chrome_A": 1-5, "chrome_B": 1-5,     (5 = no chrome left)
 "reason": "one short sentence"}"""

_WS = re.compile(r"\s+")
_FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n+", re.S)


def visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for t in soup.find_all(["script", "style", "noscript", "svg", "template"]):
        t.decompose()
    return _WS.sub(" ", (soup.body or soup).get_text(" ", strip=True))


def _clip(text: str) -> str:
    text = text.strip()
    if len(text) <= OUTPUT_HEAD_CHARS + OUTPUT_TAIL_CHARS:
        return text
    return text[:OUTPUT_HEAD_CHARS] + "\n[...]\n" + text[-OUTPUT_TAIL_CHARS:]


def _prompt(source: str, a: str, b: str) -> str:
    return (
        f"PAGE TEXT (first {SOURCE_CHARS} characters):\n{source[:SOURCE_CHARS]}\n\n"
        f"=== EXTRACTION A ===\n{_clip(a)}\n\n=== EXTRACTION B ===\n{_clip(b)}"
    )


def _sample(rng: random.Random, n_landing: int, n_docs: int) -> list[dict]:
    items: list[dict] = []
    landing = load_ok_pages(LANDING_RAW)
    rng.shuffle(landing)
    for pid, html, meta in landing[:n_landing]:
        items.append({"corpus": "landing", "id": pid, "html": html, "meta": meta, "outputs": OUT / "landing" / pid})
    report = json.loads((OUT / "corpus_comparison_report.json").read_text(encoding="utf-8"))
    docs = [
        (pid, html, meta)
        for pid, html, meta in load_ok_pages(RAW)
        if report["pages"].get(pid, {}).get("anchors", {}).get("content_ngrams", 0) >= MIN_CONTENT_ANCHORS
    ]
    rng.shuffle(docs)
    for pid, html, meta in docs[:n_docs]:
        items.append({"corpus": "benchmark", "id": pid, "html": html, "meta": meta, "outputs": OUT / pid})
    return items


def _jobs(items: list[dict], rng: random.Random) -> list[dict]:
    jobs = []
    for item in items:
        source = visible_text(item["html"])
        texts = {m: _FRONT_MATTER.sub("", (item["outputs"] / f"{m}.md").read_text(encoding="utf-8"))
                 for m in (REFERENCE, *BASELINES) if (item["outputs"] / f"{m}.md").exists()}
        for base in BASELINES:
            if REFERENCE not in texts or base not in texts:
                continue
            ours_is_a = rng.random() < 0.5
            pair = {"corpus": item["corpus"], "id": item["id"], "category": item["meta"].get("category"),
                    "baseline": base, "source": source, "ref": texts[REFERENCE], "base": texts[base]}
            jobs.append({**pair, "ours_is_a": ours_is_a, "swapped": False})
            if rng.random() < SWAP_SHARE:
                jobs.append({**pair, "ours_is_a": not ours_is_a, "swapped": True})
    return jobs


def _judge(client: OpenAI, job: dict) -> dict | None:
    a, b = (job["ref"], job["base"]) if job["ours_is_a"] else (job["base"], job["ref"])
    try:
        verdict, cost = client.chat_json(MODEL, SYSTEM, _prompt(job["source"], a, b))
    except (RuntimeError, ValueError) as exc:  # one failed call must not abort the run
        print(f"  skipped {job['id']} vs {job['baseline']}: {str(exc)[:120]}")
        return None
    better = str(verdict.get("better", "tie")).strip().upper()
    ours, theirs = ("A", "B") if job["ours_is_a"] else ("B", "A")
    winner = "chromerag" if better == ours else ("baseline" if better == theirs else "tie")
    return {
        "corpus": job["corpus"], "id": job["id"], "category": job["category"], "baseline": job["baseline"],
        "swapped": job["swapped"], "ours_is_a": job["ours_is_a"], "winner": winner,
        "content_ours": verdict.get(f"content_{ours}"), "content_base": verdict.get(f"content_{theirs}"),
        "chrome_ours": verdict.get(f"chrome_{ours}"), "chrome_base": verdict.get(f"chrome_{theirs}"),
        "reason": str(verdict.get("reason", ""))[:300], "cost_usd": round(cost, 6),
    }


def _win_ci(rows: list[dict], rng: random.Random) -> list[float]:
    """95% CI of (win share - loss share), resampling pages."""
    by_page: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        by_page[r["id"]].append(1 if r["winner"] == "chromerag" else -1 if r["winner"] == "baseline" else 0)
    pages = list(by_page)
    stats = sorted(
        statistics.mean(v for p in (rng.choice(pages) for _ in pages) for v in by_page[p])
        for _ in range(BOOTSTRAP_ITERS)
    )
    return [round(stats[int(0.025 * BOOTSTRAP_ITERS)], 3), round(stats[int(0.975 * BOOTSTRAP_ITERS) - 1], 3)]


def _mean(rows: list[dict], key: str) -> float | None:
    values = [r[key] for r in rows if isinstance(r[key], (int, float))]
    return round(statistics.mean(values), 2) if values else None


def summarize(results: list[dict]) -> dict:
    rng = random.Random(SEED)
    primary = [r for r in results if not r["swapped"]]
    summary: dict = {}
    for corpus in ("landing", "benchmark", "all"):
        for base in BASELINES:
            rows = [r for r in primary if r["baseline"] == base and corpus in (r["corpus"], "all")]
            if not rows:
                continue
            n = len(rows)
            summary[f"{corpus}:{base}"] = {
                "pairs": n,
                "chromerag_wins": round(sum(r["winner"] == "chromerag" for r in rows) / n, 3),
                "baseline_wins": round(sum(r["winner"] == "baseline" for r in rows) / n, 3),
                "ties": round(sum(r["winner"] == "tie" for r in rows) / n, 3),
                "net_win_ci95": _win_ci(rows, rng),
                "content_chromerag": _mean(rows, "content_ours"), "content_baseline": _mean(rows, "content_base"),
                "chrome_chromerag": _mean(rows, "chrome_ours"), "chrome_baseline": _mean(rows, "chrome_base"),
            }
    swapped = {(r["id"], r["baseline"]): r["winner"] for r in results if r["swapped"]}
    pairs = [(r["winner"], swapped[(r["id"], r["baseline"])]) for r in primary if (r["id"], r["baseline"]) in swapped]
    summary["position_consistency"] = {
        "pairs": len(pairs),
        "same_verdict": round(sum(a == b for a, b in pairs) / len(pairs), 3) if pairs else None,
    }
    return summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--landing", type=int, default=150)
    p.add_argument("--docs", type=int, default=100)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--dry-run", action="store_true", help="build the jobs and print the count only")
    args = p.parse_args()
    rng = random.Random(SEED)
    jobs = _jobs(_sample(rng, args.landing, args.docs), rng)
    print(f"{len(jobs)} judgements ({sum(j['swapped'] for j in jobs)} position-swap repeats); "
          f"spent so far ${spent():.3f}")
    if args.dry_run:
        return
    client = OpenAI()
    results: list[dict] = []
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for r in pool.map(lambda j: _judge(client, j), jobs):
                if r is not None:
                    results.append(r)
    except BudgetExceeded as exc:
        print(f"Stopped: {exc}")
    report = {"model": MODEL, "n_jobs": len(jobs), "front_matter": "removed before judging", "reasoning_effort": "low", "seed": SEED, "system_prompt": SYSTEM,
              "n_judgements": len(results), "cost_usd": round(sum(r["cost_usd"] for r in results), 4),
              "summary": summarize(results), "judgements": results}
    out = OUT / "llm_judge_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"cost ${report['cost_usd']:.3f}; total OpenAI spend ${spent():.3f}; wrote {out}")


if __name__ == "__main__":
    main()
