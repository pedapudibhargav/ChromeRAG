"""End-to-end retrieval over each extractor's chunks (BM25, known-item queries).

For every tool, the Markdown written by ``poc.run_corpus_comparison`` for the
scoreable pages is split into ~200-word chunks and indexed together, as a RAG
ingest step would. Queries come from the *input* HTML only, never from any
tool's output:

* ``title``   — the page's ``<h1>`` inside ``<main>``/``<article>``. Site sidebars
  and breadcrumbs repeat the titles of other pages, so this is where leftover
  chrome produces false positives.
* ``heading`` — up to three ``<h2>``/``<h3>`` headings from the same region.
* ``passage`` — up to two 12-word spans from main-content paragraphs, which
  mostly tests whether the content survived extraction.

A query is kept only when its text occurs in the main content of exactly one
page, so it has a single correct answer. A hit at k means a chunk from that page
ranks in the top k. ``context_chrome@5`` is the share of word 5-grams in the top
five chunks that are chrome anchors (nav/header/footer/aside/cookie text of any
page, minus anything that is also main content): the chrome a RAG system would
put into the model's context. Lexical retrieval keeps the evaluation model-free;
dense retrieval is left to future work.

Usage:
  python -m poc.run_retrieval_eval    # after python -m poc.run_corpus_comparison
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from bs4 import BeautifulSoup

from poc.metrics import char_ngrams, extract_anchors
from poc.run_corpus_comparison import MIN_CONTENT_ANCHORS, OUT, RAW, load_ok_pages

TOOLS = ("chromerag_coverage", "chromerag", "trafilatura", "markitdown", "readability")
CHUNK_WORDS = 200
TOP_K = (1, 5)
MAX_HEADINGS = 3
MAX_PASSAGES = 2
PASSAGE_WORDS = 12
SEED = 0
BM25_K1 = 1.2
BM25_B = 0.75
BOOTSTRAP_ITERS = 2000
REFERENCE = "chromerag_coverage"
EMBED_MODEL = "text-embedding-3-small"
EMBED_BATCH = 256
EMBED_MAX_CHARS = 6000

_TOKEN = re.compile(r"[a-z0-9]+")
_FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_WS = re.compile(r"\s+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def chunk_markdown(text: str, *, words: int = CHUNK_WORDS) -> list[str]:
    """Pack paragraphs into chunks of about ``words`` words (long paragraphs are split)."""
    text = _FRONT_MATTER.sub("", text)
    chunks: list[str] = []
    current: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para_words = para.split()
        while para_words:
            room = words - len(current)
            current.extend(para_words[:room])
            para_words = para_words[room:]
            if len(current) >= words:
                chunks.append(" ".join(current))
                current = []
    if current:
        chunks.append(" ".join(current))
    return [c for c in chunks if tokenize(c)]


class BM25:
    def __init__(self, docs: list[list[str]]) -> None:
        self.n = len(docs)
        self.lengths = [len(d) for d in docs]
        self.avg = sum(self.lengths) / max(1, self.n)
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for i, doc in enumerate(docs):
            for term, tf in Counter(doc).items():
                self.postings[term].append((i, tf))

    def search(self, query: list[str], k: int) -> list[int]:
        scores: dict[int, float] = defaultdict(float)
        for term in set(query):
            posting = self.postings.get(term)
            if not posting:
                continue
            idf = math.log(1 + (self.n - len(posting) + 0.5) / (len(posting) + 0.5))
            for i, tf in posting:
                norm = tf + BM25_K1 * (1 - BM25_B + BM25_B * self.lengths[i] / self.avg)
                scores[i] += idf * tf * (BM25_K1 + 1) / norm
        return sorted(scores, key=lambda i: (-scores[i], i))[:k]


def _main_region(html: str):
    soup = BeautifulSoup(html, "lxml")
    for t in soup.find_all(["script", "style", "noscript", "svg", "template"]):
        t.decompose()
    return soup.find("main") or soup.find("article") or soup.find(attrs={"role": "main"})


def _clean(text: str) -> str:
    return _WS.sub(" ", text).strip()


def page_queries(html: str, rng: random.Random) -> list[tuple[str, str]]:
    root = _main_region(html)
    if root is None:
        return []
    out: list[tuple[str, str]] = []
    h1 = root.find("h1")
    if h1 is not None:
        title = _clean(h1.get_text(" "))
        if 1 <= len(title.split()) <= 12:
            out.append(("title", title))
    headings = [
        _clean(h.get_text(" "))
        for h in root.find_all(["h2", "h3"])
        if 2 <= len(_clean(h.get_text(" ")).split()) <= 12
    ]
    for text in list(dict.fromkeys(headings))[:MAX_HEADINGS]:
        out.append(("heading", text))
    paragraphs = [
        _clean(p.get_text(" "))
        for p in root.find_all("p")
        if len(_clean(p.get_text(" ")).split()) >= PASSAGE_WORDS + 8
    ]
    for para in rng.sample(paragraphs, min(MAX_PASSAGES, len(paragraphs))):
        words = para.split()
        start = rng.randrange(0, len(words) - PASSAGE_WORDS + 1)
        out.append(("passage", " ".join(words[start : start + PASSAGE_WORDS])))
    return out


def _paired_bootstrap(queries: list[dict], per_query: dict[str, dict[str, list[float]]]) -> list[dict]:
    """95% CI of REFERENCE minus each other tool, resampling pages (queries cluster by page)."""
    by_page: dict[str, list[int]] = defaultdict(list)
    for i, q in enumerate(queries):
        by_page[q["page"]].append(i)
    page_ids = sorted(by_page)
    rng = random.Random(SEED)
    samples = [[rng.choice(page_ids) for _ in page_ids] for _ in range(BOOTSTRAP_ITERS)]
    rows = []
    for other in TOOLS:
        if other == REFERENCE:
            continue
        for metric in ("hit@5", "context_chrome@5"):
            a, b = per_query[REFERENCE][metric], per_query[other][metric]
            diffs = [a[i] - b[i] for i in range(len(queries))]
            means = sorted(
                statistics.mean(diffs[i] for p in sample for i in by_page[p]) for sample in samples
            )
            rows.append(
                {
                    "comparison": f"{REFERENCE} - {other}",
                    "metric": metric,
                    "mean_diff": round(statistics.mean(diffs), 3),
                    "ci95": [
                        round(means[int(0.025 * BOOTSTRAP_ITERS)], 3),
                        round(means[int(0.975 * BOOTSTRAP_ITERS) - 1], 3),
                    ],
                }
            )
    return rows


def _embed_cached(client, texts: list[str], cache: Path) -> np.ndarray:
    """Embed texts once; vectors are cached on disk keyed by the text hash."""
    cache.mkdir(parents=True, exist_ok=True)
    keys = [hashlib.sha1(t.encode("utf-8")).hexdigest() for t in texts]
    store = cache / f"{EMBED_MODEL}.npz"
    known: dict[str, np.ndarray] = dict(np.load(store)) if store.exists() else {}
    missing = [i for i, k in enumerate(keys) if k not in known]
    for start in range(0, len(missing), EMBED_BATCH):
        batch = missing[start : start + EMBED_BATCH]
        vectors = client.embed(EMBED_MODEL, [texts[i][:EMBED_MAX_CHARS] for i in batch])
        for i, v in zip(batch, vectors, strict=True):
            known[keys[i]] = np.asarray(v, dtype=np.float32)
        np.savez(store, **known)
    matrix = np.stack([known[k] for k in keys]) if keys else np.zeros((0, 1), dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0, 1, norms)


def _score_tool(queries: list[dict], chunk_page: list[str], chunk_grams: list[set[str]], chrome: set[str], search) -> dict:
    kmax = max(TOP_K)
    per_kind: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for qi, q in enumerate(queries):
        top = search(qi, kmax)
        ranked = [chunk_page[i] for i in top]
        grams = [g for i in top for g in chunk_grams[i]]
        share = sum(1 for g in grams if g in chrome) / len(grams) if grams else 0.0
        first = next((r for r, p in enumerate(ranked, 1) if p == q["page"]), None)
        for kind in (q["kind"], "all"):
            per_kind[kind]["context_chrome@5"].append(share)
            for k in TOP_K:
                per_kind[kind][f"hit@{k}"].append(1.0 if first is not None and first <= k else 0.0)
            per_kind[kind]["mrr@5"].append(1.0 / first if first else 0.0)
    return per_kind


def run(*, raw: Path = RAW, outputs: Path = OUT, name: str = "retrieval_eval", dense: bool = False) -> dict:
    rng = random.Random(SEED)
    pages = []
    content_all: set[str] = set()
    noise_all: set[str] = set()
    for pid, html, _ in load_ok_pages(raw):
        content_ng, noise_ng, diag = extract_anchors(html)
        if diag["content_ngrams"] >= MIN_CONTENT_ANCHORS:
            pages.append((pid, html))
            content_all |= content_ng
            noise_all |= noise_ng
    chrome = noise_all - content_all
    main_text = {}
    for pid, html in pages:
        root = _main_region(html)
        main_text[pid] = " ".join(tokenize(root.get_text(" "))) if root is not None else ""

    queries: list[dict] = []
    for pid, html in pages:
        for kind, text in page_queries(html, rng):
            needle = " ".join(tokenize(text))
            if not needle:
                continue
            owners = [p for p, body in main_text.items() if f" {needle} " in f" {body} "]
            if owners == [pid]:
                queries.append({"page": pid, "kind": kind, "text": text})

    report: dict = {
        "n_pages": len(pages),
        "chunk_words": CHUNK_WORDS,
        "n_queries": dict(Counter(q["kind"] for q in queries)),
        "tools": {},
    }
    client = query_vectors = None
    if dense:
        from poc.openai_client import OpenAI

        client = OpenAI()
        query_vectors = _embed_cached(client, [q["text"] for q in queries], OUT / "embedding_cache")
        report["dense"] = {"model": EMBED_MODEL, "tools": {}}
    per_query: dict[str, dict[str, dict[str, list[float]]]] = {"bm25": {}, "dense": {}}
    for tool in TOOLS:
        chunk_page: list[str] = []
        chunk_grams: list[set[str]] = []
        chunks: list[str] = []
        docs: list[list[str]] = []
        for pid, _ in pages:
            path = outputs / pid / f"{tool}.md"
            text = path.read_text(encoding="utf-8") if path.exists() else ""
            for chunk in chunk_markdown(text):
                chunk_page.append(pid)
                chunk_grams.append(char_ngrams(chunk))
                chunks.append(chunk)
                docs.append(tokenize(chunk))
        index = BM25(docs)
        bm25 = _score_tool(queries, chunk_page, chunk_grams, chrome, lambda qi, k, index=index: index.search(tokenize(queries[qi]["text"]), k))
        per_query["bm25"][tool] = bm25["all"]
        summary = {"chunks": len(docs), "indexed_words": sum(len(d) for d in docs)}
        report["tools"][tool] = {**summary, "scores": _means(bm25)}
        if dense:
            vectors = _embed_cached(client, chunks, OUT / "embedding_cache")

            def search(qi: int, k: int, vectors=vectors) -> list[int]:
                sims = vectors @ query_vectors[qi]
                return [int(i) for i in np.argsort(-sims, kind="stable")[:k]]

            dense_scores = _score_tool(queries, chunk_page, chunk_grams, chrome, search)
            per_query["dense"][tool] = dense_scores["all"]
            report["dense"]["tools"][tool] = {**summary, "scores": _means(dense_scores)}
    report["paired_bootstrap"] = _paired_bootstrap(queries, per_query["bm25"])
    if dense:
        report["dense"]["paired_bootstrap"] = _paired_bootstrap(queries, per_query["dense"])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _means(per_kind: dict[str, dict[str, list[float]]]) -> dict:
    return {kind: {m: round(statistics.mean(v), 3) for m, v in metrics.items()} for kind, metrics in per_kind.items()}


def _print(label: str, tools: dict, bootstrap: list[dict]) -> None:
    print(f"-- {label}")
    for tool, r in tools.items():
        s = r["scores"]["all"]
        print(f"  {tool:20s} chunks {r['chunks']:6d}  hit@1 {s['hit@1']:.3f}  hit@5 {s['hit@5']:.3f}  "
              f"chrome@5 {s['context_chrome@5']:.3f}")
    for row in bootstrap:
        lo, hi = row["ci95"]
        print(f"    {row['comparison']:38s} {row['metric']:17s} {row['mean_diff']:+.3f} [{lo:+.3f}, {hi:+.3f}]")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--corpus", choices=("benchmark", "landing"), default="benchmark")
    p.add_argument("--dense", action="store_true", help=f"also run embedding retrieval ({EMBED_MODEL})")
    args = p.parse_args()
    if args.corpus == "landing":
        from poc.landing_corpus import RAW as LANDING_RAW

        report = run(raw=LANDING_RAW, outputs=OUT / "landing", name="landing_retrieval_eval", dense=args.dense)
    else:
        report = run(dense=args.dense)
    print(f"Pages: {report['n_pages']}  queries: {report['n_queries']}")
    _print("BM25", report["tools"], report["paired_bootstrap"])
    if args.dense:
        _print(f"dense ({EMBED_MODEL})", report["dense"]["tools"], report["dense"]["paired_bootstrap"])


if __name__ == "__main__":
    main()
