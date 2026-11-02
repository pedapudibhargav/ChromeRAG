"""Blind pairwise judging of the new evaluation pages under evaluations/2026-11-final/RUBRIC.md.

Reads frozen tool outputs from the extraction cache and the page list from page_filter.json.
Balanced ChromeRAG is compared with each baseline. A/B order is random per page with a stored
seed, and tool names stay hidden.

  python -m poc.final_page_judge --dry-run
  python -m poc.final_page_judge --baselines trafilatura,readability --out results/x.json
"""

from __future__ import annotations

import argparse
import json
import random
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from poc.eval_rubric import page_judge_prompt, sensitivity_verdict
from poc.final_page_filter import visible_text
from poc.final_run import cache_key, cache_path
from poc.openai_client import BudgetExceeded, OpenAI, spent

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "evaluations" / "2026-11-final"
MODEL = "gpt-5.6-luna"
SEED = 20261101
REFERENCE = "chromerag"
BUDGET_CHARS = 24000
HEAD_CHARS = 18000
TAIL_CHARS = 6000
SWAP_SHARE = 0.1
PRICE_IN_PER_M = 0.20
PRICE_OUT_PER_M = 0.75
EST_OUTPUT_TOKENS = 150
EST_SYSTEM_TOKENS = 600
PAGE_SYSTEM = page_judge_prompt()


def clip(text: str) -> str:
    text = text.strip()
    if len(text) <= BUDGET_CHARS:
        return text
    return text[:HEAD_CHARS] + "\n[...]\n" + text[-TAIL_CHARS:]


def build_prompt(source: str, a: str, b: str) -> str:
    return (
        f"PAGE TEXT (first {BUDGET_CHARS} characters):\n{source[:BUDGET_CHARS]}\n\n"
        f"=== EXTRACTION A ===\n{clip(a)}\n\n=== EXTRACTION B ===\n{clip(b)}"
    )


def page_seed(page_id: str) -> int:
    return int.from_bytes(f"{SEED}:{page_id}".encode(), "big") % (2**32)


def load_output(cache_dir: Path, html: str, tool: str, version: str) -> str:
    key = cache_key(html=html, tool=tool, version=version)
    row = json.loads(cache_path(cache_dir, tool, key).read_text(encoding="utf-8"))
    return row["text"]


def build_jobs(
    pages_dir: Path, cache_dir: Path, extract_report: dict, kept_ids: list[str], baselines: list[str]
) -> list[dict]:
    rng = random.Random(SEED)
    jobs: list[dict] = []
    for pid in kept_ids:
        html = (pages_dir / f"{pid}.html").read_text(encoding="utf-8", errors="replace")
        per_tool = extract_report["per_page"][pid]
        ref = load_output(cache_dir, html, REFERENCE, per_tool[REFERENCE]["tool_version"])
        source = visible_text(html)
        ours_is_a = random.Random(page_seed(pid)).random() < 0.5
        for base in baselines:
            other = load_output(cache_dir, html, base, per_tool[base]["tool_version"])
            pair = {
                "id": pid,
                "baseline": base,
                "source": source,
                "ref": ref,
                "base": other,
                "clipped": max(len(ref.strip()), len(other.strip())) > BUDGET_CHARS,
            }
            jobs.append({**pair, "ours_is_a": ours_is_a, "swapped": False})
            if rng.random() < SWAP_SHARE:
                jobs.append({**pair, "ours_is_a": not ours_is_a, "swapped": True})
    return jobs


def estimate_usd(jobs: list[dict]) -> float:
    chars = sum(
        min(len(j["source"]), BUDGET_CHARS) + len(clip(j["ref"])) + len(clip(j["base"])) for j in jobs
    )
    tokens_in = chars / 4 + EST_SYSTEM_TOKENS * len(jobs)
    tokens_out = EST_OUTPUT_TOKENS * len(jobs)
    return tokens_in / 1e6 * PRICE_IN_PER_M + tokens_out / 1e6 * PRICE_OUT_PER_M


def winner_of(better: str, ours: str, theirs: str) -> str:
    return "chromerag" if better == ours else ("baseline" if better == theirs else "tie")


def score_row(job: dict, verdict: dict) -> dict:
    ours, theirs = ("A", "B") if job["ours_is_a"] else ("B", "A")
    better = str(verdict.get("better", "tie")).strip().upper()
    row = {
        "id": job["id"],
        "baseline": job["baseline"],
        "swapped": job["swapped"],
        "ours_is_a": job["ours_is_a"],
        "clipped": job["clipped"],
        "winner": winner_of(better, ours, theirs),
        "content_A": verdict.get("content_A"),
        "content_B": verdict.get("content_B"),
        "chrome_A": verdict.get("chrome_A"),
        "chrome_B": verdict.get("chrome_B"),
        "reason": str(verdict.get("reason", ""))[:300],
    }
    scores = [row["content_A"], row["chrome_A"], row["content_B"], row["chrome_B"]]
    row["winner_sensitivity"] = None
    if all(isinstance(x, int) for x in scores):
        row["winner_sensitivity"] = winner_of(sensitivity_verdict(*scores), ours, theirs)
    return row


def _counts(rows: list[dict], key: str) -> dict:
    rows = [r for r in rows if r[key] is not None]
    n = len(rows)
    wins = sum(r[key] == "chromerag" for r in rows)
    losses = sum(r[key] == "baseline" for r in rows)
    return {"pairs": n, "chromerag": wins, "baseline": losses, "tie": n - wins - losses}


def summarize(rows: list[dict], baselines: list[str]) -> dict:
    primary = [r for r in rows if not r["swapped"]]
    swapped = {(r["id"], r["baseline"]): r["winner"] for r in rows if r["swapped"]}
    repeat = [(r["winner"], swapped[(r["id"], r["baseline"])]) for r in primary if (r["id"], r["baseline"]) in swapped]
    out: dict = {
        "position_check": {"pairs": len(repeat), "same_verdict": sum(a == b for a, b in repeat)},
    }
    for base in baselines:
        sel = [r for r in primary if r["baseline"] == base]
        out[base] = {
            "judge_verdict": _counts(sel, "winner"),
            "judge_verdict_unclipped_pairs": _counts([r for r in sel if not r["clipped"]], "winner"),
            "fixed_order_sensitivity": _counts(sel, "winner_sensitivity"),
            "fixed_order_sensitivity_unclipped_pairs": _counts(
                [r for r in sel if not r["clipped"]], "winner_sensitivity"
            ),
        }
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pages-dir", type=Path, default=ROOT / "data" / "final")
    p.add_argument("--cache-dir", type=Path, default=EVAL / "cache" / "new_pages")
    p.add_argument("--extract-report", type=Path, default=EVAL / "results" / "new_pages_extract.json")
    p.add_argument("--page-filter", type=Path, default=EVAL / "page_filter.json")
    p.add_argument("--baselines", default="trafilatura,readability")
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--out", type=Path, default=EVAL / "results" / "new_pages_judge.json")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    baselines = args.baselines.split(",")
    kept = json.loads(args.page_filter.read_text(encoding="utf-8"))["kept_ids"]
    extract = json.loads(args.extract_report.read_text(encoding="utf-8"))
    jobs = build_jobs(args.pages_dir, args.cache_dir, extract, kept, baselines)
    n_clipped = sum(j["clipped"] for j in jobs)
    print(f"{len(jobs)} judgements on {len(kept)} pages; {n_clipped} clipped; est ${estimate_usd(jobs):.2f}")
    if args.dry_run:
        return
    client = OpenAI()
    start = spent()
    # Every verdict is saved as it arrives, so an interrupted run resumes without paying twice.
    args.out.parent.mkdir(parents=True, exist_ok=True)
    progress = args.out.with_suffix(".progress.jsonl")
    done: dict[tuple, dict] = {}
    if progress.exists():
        for line in progress.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            done[(row["id"], row["baseline"], row["swapped"])] = row
    todo = [j for j in jobs if (j["id"], j["baseline"], j["swapped"]) not in done]
    print(f"{len(done)} verdicts already saved; {len(todo)} to judge")
    lock = threading.Lock()

    def judge(job: dict) -> dict | None:
        a, b = (job["ref"], job["base"]) if job["ours_is_a"] else (job["base"], job["ref"])
        try:
            verdict, _cost = client.chat_json(MODEL, PAGE_SYSTEM, build_prompt(job["source"], a, b))
        except BudgetExceeded:
            raise
        except Exception as exc:  # noqa: BLE001
            print(f"  not judged {job['id']} vs {job['baseline']}: {type(exc).__name__}")
            return None
        row = score_row(job, verdict)
        with lock, progress.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        return row

    rows = list(done.values())
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            rows += [r for r in pool.map(judge, todo) if r is not None]
    except BudgetExceeded as exc:
        print(f"Stopped: {exc}")
    report = {
        "model": MODEL,
        "seed": SEED,
        "page_rubric": "evaluations/2026-11-final/RUBRIC.md",
        "system_prompt": PAGE_SYSTEM,
        "budget_chars": BUDGET_CHARS,
        "n_jobs": len(jobs),
        "n_judged": len(rows),
        "cost_usd": round(spent() - start, 4),
        "summary": summarize(rows, baselines),
        "judgements": rows,
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"cost ${report['cost_usd']:.3f}")


if __name__ == "__main__":
    main()
