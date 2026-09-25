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

import json
import math
import random
import re
import statistics
from collections import Counter, defaultdict

from bs4 import BeautifulSoup

from poc.metrics import char_ngrams, extract_anchors
from poc.run_corpus_comparison import MIN_CONTENT_ANCHORS, OUT, load_ok_pages

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


def run() -> dict:
    rng = random.Random(SEED)
    pages = []
    content_all: set[str] = set()
    noise_all: set[str] = set()
    for pid, html, _ in load_ok_pages():
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
    kmax = max(TOP_K)
    per_query: dict[str, dict[str, list[float]]] = {}
    for tool in TOOLS:
        chunk_page: list[str] = []
        chunk_grams: list[set[str]] = []
        docs: list[list[str]] = []
        tokens = 0
        for pid, _ in pages:
            path = OUT / pid / f"{tool}.md"
            text = path.read_text(encoding="utf-8") if path.exists() else ""
            for chunk in chunk_markdown(text):
                toks = tokenize(chunk)
                chunk_page.append(pid)
                chunk_grams.append(char_ngrams(chunk))
                docs.append(toks)
                tokens += len(toks)
        index = BM25(docs)
        per_kind: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        for q in queries:
            top = index.search(tokenize(q["text"]), kmax)
            ranked = [chunk_page[i] for i in top]
            grams = [g for i in top for g in chunk_grams[i]]
            share = sum(1 for g in grams if g in chrome) / len(grams) if grams else 0.0
            per_kind[q["kind"]]["context_chrome@5"].append(share)
            per_kind["all"]["context_chrome@5"].append(share)
            first = next((r for r, p in enumerate(ranked, 1) if p == q["page"]), None)
            for k in TOP_K:
                hit = 1.0 if first is not None and first <= k else 0.0
                per_kind[q["kind"]][f"hit@{k}"].append(hit)
                per_kind["all"][f"hit@{k}"].append(hit)
            rr = 1.0 / first if first else 0.0
            per_kind[q["kind"]]["mrr@5"].append(rr)
            per_kind["all"]["mrr@5"].append(rr)
        per_query[tool] = per_kind["all"]
        report["tools"][tool] = {
            "chunks": len(docs),
            "indexed_words": tokens,
            "scores": {
                kind: {m: round(statistics.mean(v), 3) for m, v in metrics.items()}
                for kind, metrics in per_kind.items()
            },
        }
    report["paired_bootstrap"] = _paired_bootstrap(queries, per_query)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "retrieval_eval_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    report = run()
    print(f"Pages: {report['n_pages']}  queries: {report['n_queries']}")
    print(f"{'tool':20s} {'chunks':>7s}  " + "  ".join(f"{k:>27s}" for k in ("title", "heading", "passage", "all")))
    for tool, r in report["tools"].items():
        cells = []
        for kind in ("title", "heading", "passage", "all"):
            s = r["scores"].get(kind, {})
            cells.append(
                f"h1 {s.get('hit@1', 0):.3f} h5 {s.get('hit@5', 0):.3f} "
                f"ch {s.get('context_chrome@5', 0):.3f}"
            )
        print(f"{tool:20s} {r['chunks']:7d}  " + "  ".join(f"{c:>27s}" for c in cells))
    for row in report["paired_bootstrap"]:
        lo, hi = row["ci95"]
        print(f"  {row['comparison']:38s} {row['metric']:17s} {row['mean_diff']:+.3f} [{lo:+.3f}, {hi:+.3f}]")
    print(f"Wrote {OUT / 'retrieval_eval_report.json'}")


if __name__ == "__main__":
    main()
