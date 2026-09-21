"""Optional LLM judge for extraction quality (subset of corpus).

Primary metrics remain deterministic (content_recall / noise_retention / Fbal).
This script adds a human-style 1–5 rubric on a stratified sample when OPENAI_API_KEY
is available. Without a key it writes a skipped report (does not fail CI).

Usage:
  python -m poc.run_llm_eval --sample 40
  python -m poc.run_llm_eval --sample 40 --provider ollama --model llama3.2
"""

from __future__ import annotations

import argparse
import json
import os
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "outputs"
RAW = ROOT / "data" / "raw"
DOCS = ROOT / "docs" / "data"

RUBRIC = """You score HTML→Markdown extraction for enterprise RAG ingest.
Return ONLY JSON: {"content_keep":1-5,"noise_strip":1-5,"structure":1-5,"notes":"short"}
- content_keep: did main article/docs content survive?
- noise_strip: were nav/footer/CTA/cookie chrome removed?
- structure: headings/tables/lists usable for chunking?
"""


def _chat_openai(model: str, prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": RUBRIC},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content or "{}"


def _chat_ollama(model: str, prompt: str) -> str:
    import httpx

    r = httpx.post(
        os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434") + "/api/chat",
        json={
            "model": model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": RUBRIC},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=120.0,
    )
    r.raise_for_status()
    return r.json().get("message", {}).get("content") or "{}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", type=int, default=40)
    ap.add_argument("--provider", choices=("openai", "ollama", "none"), default="auto")
    ap.add_argument("--model", default="")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    report_path = OUT / "corpus_comparison_report.json"
    if not report_path.exists():
        print("Missing corpus_comparison_report.json — run corpus comparison first.")
        return 2
    report = json.loads(report_path.read_text(encoding="utf-8"))

    provider = args.provider
    if provider == "auto":
        if os.environ.get("OPENAI_API_KEY"):
            provider = "openai"
        else:
            provider = "none"
    model = args.model or ("gpt-4o-mini" if provider == "openai" else "llama3.2")

    scoreable = [
        (pid, entry)
        for pid, entry in report.get("pages", {}).items()
        if entry.get("scoreable")
    ]
    rng = random.Random(args.seed)
    # Stratify by category when possible
    by_cat: dict[str, list] = defaultdict(list)
    for pid, entry in scoreable:
        cat = str((entry.get("meta") or {}).get("category") or "unknown")
        by_cat[cat].append((pid, entry))
    sample: list[tuple[str, dict]] = []
    cats = sorted(by_cat)
    i = 0
    while len(sample) < min(args.sample, len(scoreable)) and cats:
        cat = cats[i % len(cats)]
        bucket = by_cat[cat]
        if bucket:
            sample.append(bucket.pop(rng.randrange(len(bucket))))
        else:
            cats = [c for c in cats if by_cat[c]]
            if not cats:
                break
            i = 0
            continue
        i += 1

    out = {
        "provider": provider,
        "model": model,
        "sample_size": len(sample),
        "seed": args.seed,
        "items": [],
        "averages": {},
    }

    if provider == "none":
        out["skipped"] = True
        out["reason"] = "No OPENAI_API_KEY and provider!=ollama — LLM eval skipped."
        (OUT / "llm_eval_report.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
        DOCS.mkdir(parents=True, exist_ok=True)
        (DOCS / "llm_eval_report.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
        print("LLM eval skipped (no API key). Deterministic metrics remain primary.")
        return 0

    chat = _chat_openai if provider == "openai" else _chat_ollama
    sums = defaultdict(float)
    n_ok = 0
    for pid, entry in sample:
        md_path = OUT / pid / "chromerag.md"
        if not md_path.exists():
            continue
        md = md_path.read_text(encoding="utf-8")[:6000]
        meta = entry.get("meta") or {}
        prompt = (
            f"URL: {meta.get('url')}\nCategory: {meta.get('category')}\n\n"
            f"EXTRACTED MARKDOWN (truncated):\n{md}"
        )
        try:
            raw = chat(model, prompt)
            scores = json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            scores = {"error": str(exc)}
        item = {"id": pid, "url": meta.get("url"), "category": meta.get("category"), "scores": scores}
        out["items"].append(item)
        if all(k in scores for k in ("content_keep", "noise_strip", "structure")):
            n_ok += 1
            for k in ("content_keep", "noise_strip", "structure"):
                sums[k] += float(scores[k])
            print(f"  OK {pid} {scores}")
        else:
            print(f"  FAIL {pid} {scores}")

    if n_ok:
        out["averages"] = {k: round(v / n_ok, 3) for k, v in sums.items()}
        out["n_scored"] = n_ok

    (OUT / "llm_eval_report.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "llm_eval_report.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("Wrote llm_eval_report.json averages=", out.get("averages"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
