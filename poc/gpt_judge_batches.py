"""Judge the blinded batches built by poc.claude_judge_build with a GPT model (a second model family).

Same rubric, same blinded A/B items, same output format as the Claude sub-agent judges, so
``poc.claude_judge_aggregate`` reads both. Writes <out>/results/<tag>_NN.json and links the key.

  python -m poc.gpt_judge_batches --tag mix_readability --limit 120
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from poc.openai_client import BudgetExceeded, OpenAI, spent
from poc.run_llm_judge import SOURCE_CHARS, _clip

MODEL = "gpt-5.6-luna"


def _prompt(item: dict) -> str:
    return (
        f"PAGE TEXT (first {SOURCE_CHARS} characters):\n{item['source'][:SOURCE_CHARS]}\n\n"
        f"=== EXTRACTION A ===\n{_clip(item['A'])}\n\n=== EXTRACTION B ===\n{_clip(item['B'])}"
    )


def _one(client: OpenAI, system: str, item: dict) -> dict | None:
    verdict = None
    for attempt in range(4):
        try:
            verdict, _ = client.chat_json(MODEL, system, _prompt(item))
            break
        except BudgetExceeded:
            raise
        except httpx.HTTPError:  # transient network error: back off and retry
            time.sleep(2 * (attempt + 1))
        except (RuntimeError, ValueError) as exc:  # one failed call must not abort the run
            print(f"  skipped {item['pid']}: {str(exc)[:100]}")
            return None
    if verdict is None:
        print(f"  skipped {item['pid']}: network errors")
        return None
    out = {"pid": item["pid"], "better": str(verdict.get("better", "tie")).strip(), "reason": str(verdict.get("reason", ""))[:200]}
    for key in ("content_A", "content_B", "chrome_A", "chrome_B"):
        out[key] = verdict.get(key)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--src", default="/tmp/cr/judge")
    ap.add_argument("--out", default="/tmp/cr/judge_gpt")
    ap.add_argument("--limit", type=int, default=0, help="judge only the first N pairs (batches in order)")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    out = Path(a.out)
    (out / "results").mkdir(parents=True, exist_ok=True)
    (out / "key").mkdir(parents=True, exist_ok=True)
    key = Path(a.src) / "key" / f"{a.tag}.json"
    link = out / "key" / key.name
    if not link.exists():
        os.symlink(key, link)
    system = (Path(a.src) / "SYSTEM.txt").read_text()
    client = OpenAI(cap_usd=float(os.environ.get("CHROMERAG_OPENAI_CAP_USD", "3.10")))
    done = 0
    for f in sorted(glob.glob(f"{a.src}/batches/{a.tag}_*.json")):
        if (out / "results" / Path(f).name).exists():
            continue  # resume: this batch is already judged
        items = json.loads(Path(f).read_text())
        if a.limit:
            items = items[: max(a.limit - done, 0)]
        if not items:
            break
        with ThreadPoolExecutor(a.workers) as pool:
            rows = [r for r in pool.map(lambda it: _one(client, system, it), items) if r]
        (out / "results" / Path(f).name).write_text(json.dumps(rows))
        done += len(items)
        print(f"{Path(f).name}: {len(rows)}/{len(items)} judged, spend ${spent():.3f}")
        if a.limit and done >= a.limit:
            break


if __name__ == "__main__":
    main()
