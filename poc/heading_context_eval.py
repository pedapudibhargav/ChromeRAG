"""Does heading-path context in the embedded text improve retrieval?

Pages are the held-out documentation corpus. ChromeRAG Markdown is cut into <=180-word chunks inside heading
sections. Each chunk is indexed in three forms: plain text, with the page title prepended, and with the full heading
path (title > h2 > h3) prepended. Questions are written by a blinded Claude judge from the chunk, not from any
variant. Retrieval is BM25 and OpenAI embeddings; the target is the chunk the question was written from.

  python -m poc.heading_context_eval build   # chunks + question-writing batches in /tmp/cr/hc
  python -m poc.heading_context_eval run     # after /tmp/cr/hc/results/*.json exist
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import random
import re
from collections import Counter
from pathlib import Path

import numpy as np

from chromerag import ChromeRAG, ContentPriority, PipelineConfig
from chromerag.chunking import Chunk, chunk_markdown
from poc.claude_judge_build import pages

OUT = Path("/tmp/cr/hc")
N_QUESTIONS = 400


def _chunk_record(c: Chunk, page: str, title: str) -> dict:
    if title and c.heading_path and c.heading_path[0] == title:
        path = list(c.heading_path[1:])
    else:
        path = list(c.heading_path)
    return {"page": page, "title": title, "path": path, "text": c.text}


def variants(c: dict) -> dict[str, str]:
    path = " > ".join(dict.fromkeys([c["title"], *c["path"]])) if c["title"] else " > ".join(c["path"])
    return {"plain": c["text"], "title": f'{c["title"]}\n{c["text"]}' if c["title"] else c["text"], "path": f"{path}\n{c['text']}"}


def build() -> None:
    rng = random.Random(11)
    rag = ChromeRAG(config=PipelineConfig.from_priority(ContentPriority.BALANCED))
    chunks: list[dict] = []
    for pid, _t, url, html in pages("docs"):
        r = rag.extract(html, url=url or None)
        title = str(r.front_matter.get("title") or "").strip()
        for c in chunk_markdown(r.markdown, title=title):
            row = _chunk_record(c, pid, title)
            row["url"] = url
            row["id"] = f"c{len(chunks):05d}"
            chunks.append(row)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results").mkdir(exist_ok=True)
    (OUT / "batches").mkdir(exist_ok=True)
    (OUT / "chunks.json").write_text(json.dumps(chunks))
    # questions only for chunks inside a section (non-empty path) so context can matter; one per page at most twice
    per_page: Counter = Counter()
    pool = [c for c in chunks if c["path"]]
    rng.shuffle(pool)
    chosen = []
    for c in pool:
        if per_page[c["page"]] < 2:
            chosen.append(c)
            per_page[c["page"]] += 1
        if len(chosen) >= N_QUESTIONS:
            break
    for i in range(0, len(chosen), 50):
        (OUT / "batches" / f"q_{i // 50:02d}.json").write_text(json.dumps(
            [{"cid": c["id"], "page_title": c["title"], "passage": c["text"]} for c in chosen[i : i + 50]], ensure_ascii=False))
    print(len(chunks), "chunks;", len(chosen), "question targets;", -(-len(chosen) // 50), "batches")


def _tok(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.2, b: float = 0.75) -> None:
        self.tf = [Counter(_tok(d)) for d in docs]
        self.len = np.array([sum(t.values()) for t in self.tf], dtype=float)
        self.avg = self.len.mean()
        df: Counter = Counter()
        for t in self.tf:
            df.update(t.keys())
        n = len(docs)
        self.idf = {w: math.log(1 + (n - d + 0.5) / (d + 0.5)) for w, d in df.items()}
        self.k1, self.b = k1, b

    def scores(self, q: str) -> np.ndarray:
        out = np.zeros(len(self.tf))
        for w in set(_tok(q)):
            idf = self.idf.get(w)
            if idf is None:
                continue
            for i, t in enumerate(self.tf):
                f = t.get(w)
                if f:
                    out[i] += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
        return out


def metrics(rank: list[int]) -> dict:
    a = np.array(rank)
    return {"n": len(a), "hit@1": float((a <= 1).mean()), "hit@5": float((a <= 5).mean()), "hit@10": float((a <= 10).mean()),
            "mrr": float((1.0 / a).mean())}


def run(dense: bool) -> None:
    chunks = json.loads((OUT / "chunks.json").read_text())
    by_id = {c["id"]: i for i, c in enumerate(chunks)}
    qs = []
    for f in sorted(glob.glob(str(OUT / "results" / "q_*.json"))):
        qs += [q for q in json.loads(Path(f).read_text()) if q.get("cid") in by_id and str(q.get("question", "")).strip()]
    print(len(qs), "questions")
    forms = {k: [variants(c)[k] for c in chunks] for k in ("plain", "title", "path")}
    report: dict = {"n_chunks": len(chunks), "n_questions": len(qs), "bm25": {}, "dense": {}}
    ranks: dict[str, dict[str, list[int]]] = {"bm25": {}, "dense": {}}
    for name, docs in forms.items():
        bm = BM25(docs)
        r = []
        for q in qs:
            s = bm.scores(q["question"])
            tgt = by_id[q["cid"]]
            r.append(int((s > s[tgt]).sum()) + 1)
        ranks["bm25"][name] = r
        report["bm25"][name] = metrics(r)
    if dense:
        from poc.openai_client import OpenAI
        from poc.run_retrieval_eval import EMBED_MODEL
        client = OpenAI(cap_usd=2.10)  # the total approved for this evaluation
        qv = _embed(client, EMBED_MODEL, [q["question"] for q in qs])
        for name, docs in forms.items():
            dv = _embed(client, EMBED_MODEL, [d[:6000] for d in docs])
            r = []
            for j, q in enumerate(qs):
                s = dv @ qv[j]
                r.append(int((s > s[by_id[q["cid"]]]).sum()) + 1)
            ranks["dense"][name] = r
            report["dense"][name] = metrics(r)
    rng = np.random.default_rng(0)
    for kind in ("bm25", "dense"):
        if not ranks[kind]:
            continue
        for a, b in (("plain", "path"), ("plain", "title"), ("title", "path")):
            ra, rb = 1.0 / np.array(ranks[kind][a]), 1.0 / np.array(ranks[kind][b])
            d = rb - ra
            boots = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(2000)]
            report[kind][f"mrr_gain_{b}_over_{a}"] = {"mean": float(d.mean()), "ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]}
    (OUT / "report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


def _embed(client, model: str, texts: list[str]) -> np.ndarray:
    out = []
    for i in range(0, len(texts), 64):
        out += client.embed(model, texts[i : i + 64])
    v = np.array(out, dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "run"])
    ap.add_argument("--dense", action="store_true")
    a = ap.parse_args()
    build() if a.cmd == "build" else run(a.dense)
