"""Build blinded pairwise-judgement batches for Claude sub-agent judges.

For each page: the page's visible text (from the input HTML), and two outputs labelled A and B in a random order:
ChromeRAG (balanced) and Trafilatura (best configuration). Judge prompt, clipping and rubric follow
poc/run_llm_judge.py. The A/B key is written to a separate file that the judges never see.

  python -m poc.claude_judge_build --set wcxb_clean|docs|products --batch-size 25 --out /tmp/cr/judge
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

from chromerag import ChromeRAG, ContentPriority, PipelineConfig
from poc.baselines import BASELINES
from poc.run_llm_judge import OUTPUT_HEAD_CHARS, SYSTEM, visible_text
from poc.wcxb import load_split

ROOT = Path(__file__).resolve().parents[1]
_FRONT = re.compile(r"\A---\n.*?\n---\n+", re.S)
SOURCE_CHARS = 5000
TAIL = 1000


def _clip(text: str) -> str:
    text = text.strip()
    return text if len(text) <= OUTPUT_HEAD_CHARS - 1000 + TAIL else text[: OUTPUT_HEAD_CHARS - 1000] + "\n[...]\n" + text[-TAIL:]


def pages(name: str, n_mix: int = 250):
    if name == "mix":  # a seeded sample over the three untouched evaluation sets, for rival comparisons
        pool = [p for part in ("wcxb_clean", "docs_final", "products_final") for p in pages(part)]
        random.Random(5).shuffle(pool)
        yield from pool[:n_mix]
        return
    if name == "wcxb_clean":
        for p in load_split("test", drop_leaked=True):
            yield f"wcxb-{p.id}", p.page_type, p.url, p.html
    else:
        kind = "docs" if name.startswith("docs") else "products"
        raw = "extra_raw_final" if name.endswith("_final") else "extra_raw"
        for meta in sorted((ROOT / "data" / raw / kind).glob("*.meta.json")):
            m = json.loads(meta.read_text())
            html = (meta.parent / f"{m['id']}.html").read_text(encoding="utf-8", errors="ignore")
            yield f"{kind}-{m['id']}", kind.rstrip("s") if kind == "products" else "documentation", m["url"], html


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True, choices=["wcxb_clean", "docs", "products", "docs_final", "products_final", "mix"])
    ap.add_argument("--batch-size", type=int, default=25)
    ap.add_argument("--rival", default="trafilatura", choices=sorted(BASELINES))
    ap.add_argument("--out", default="/tmp/cr/judge")
    a = ap.parse_args()
    tag = a.set if a.rival == "trafilatura" else f"{a.set}_{a.rival}"
    out = Path(a.out)
    (out / "key").mkdir(parents=True, exist_ok=True)
    (out / "batches").mkdir(parents=True, exist_ok=True)
    rng = random.Random(7)
    rag = ChromeRAG(config=PipelineConfig.from_priority(ContentPriority.BALANCED))
    items, key = [], {}
    for pid, ptype, url, html in pages(a.set):
        ours = _FRONT.sub("", rag.extract(html, url=url or None).markdown)
        try:
            theirs = BASELINES[a.rival](html) or ""
        except Exception:  # noqa: BLE001
            theirs = ""
        if not ours.strip() or not theirs.strip():
            continue
        ours_first = rng.random() < 0.5
        A, B = (ours, theirs) if ours_first else (theirs, ours)
        items.append({"pid": pid, "source": visible_text(html)[:SOURCE_CHARS], "A": _clip(A), "B": _clip(B)})
        key[pid] = {"type": ptype, "url": url, "A": "chromerag" if ours_first else a.rival, "B": a.rival if ours_first else "chromerag"}
    rng.shuffle(items)
    for i in range(0, len(items), a.batch_size):
        (out / "batches" / f"{tag}_{i // a.batch_size:02d}.json").write_text(json.dumps(items[i : i + a.batch_size], ensure_ascii=False))
    (out / "key" / f"{tag}.json").write_text(json.dumps(key))
    (out / "SYSTEM.txt").write_text(SYSTEM)
    print(tag, len(items), "pairs in", -(-len(items) // a.batch_size), "batches")


if __name__ == "__main__":
    main()
