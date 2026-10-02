"""Build the training table for the learned block classifier from WCXB pages.

For each page: clean it with the normal pipeline, list its blocks, describe each block
(chromerag.blockfeatures) and label it from the human-reviewed main content. A block is
content when most of its word trigrams occur in the reference (short blocks: the whole word
sequence occurs in it). Rows are weighted by word count because the benchmark scores words.

  python -m poc.lbc_data --split dev --out /tmp/cr/lbc_dev.npz
"""

from __future__ import annotations

import argparse
import zlib
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from chromerag import ChromeRAG, ContentPriority, PipelineConfig
from chromerag.blockfeatures import block_features, find_blocks
from chromerag.extractor import StopExtraction
from chromerag.treestats import TreeStats
from poc.learn_tokens import half, site_of
from poc.wcxb import load_split, tokenize

POSITIVE_SHARE = 0.5
MAX_WEIGHT = 120


def label_blocks(texts: list[str], reference: str) -> tuple[np.ndarray, np.ndarray]:
    ref = tokenize(reference)
    joined = " " + " ".join(ref) + " "
    tri = {tuple(ref[i : i + 3]) for i in range(len(ref) - 2)}
    y = np.zeros(len(texts), dtype=np.float32)
    w = np.zeros(len(texts), dtype=np.float32)
    for i, text in enumerate(texts):
        toks = tokenize(text)
        w[i] = min(MAX_WEIGHT, max(1, len(toks)))
        if not toks:
            continue
        if len(toks) < 3:
            y[i] = 1.0 if (" " + " ".join(toks) + " ") in joined else 0.0
        else:
            grams = [tuple(toks[j : j + 3]) for j in range(len(toks) - 2)]
            y[i] = 1.0 if sum(g in tri for g in grams) / len(grams) >= POSITIVE_SHARE else 0.0
    return y, w


def _one(page):
    rows: dict = {}

    def capture(soup, root):
        body = soup.body or soup
        stats = TreeStats(body)
        blocks = find_blocks(body, stats)
        rows["X"], rows["box"] = block_features(blocks, body, stats, root)
        rows["texts"] = [b.text for b in blocks]

    rag = ChromeRAG(config=PipelineConfig.from_priority(ContentPriority.COVERAGE))
    rag._capture = capture
    try:
        rag.extract(page.html, url=page.url or None)
    except StopExtraction:
        pass
    except Exception as exc:  # noqa: BLE001
        print("CRASH", page.id, exc)
    if "X" not in rows or len(rows["texts"]) == 0:
        return None
    y, w = label_blocks(rows["texts"], page.main_content)
    site = site_of(page.url)
    return page.id, page.page_type, half(site), rows["X"], y, w, [len(t) for t in rows["texts"]], rows["box"], zlib.crc32(site.encode()) % 5


def build(split: str, out: str) -> None:
    pages = [p for p in load_split(split) if len(tokenize(p.main_content)) >= 30]
    with ProcessPoolExecutor() as pool:
        results = [r for r in pool.map(_one, pages, chunksize=8) if r is not None]
    X = np.concatenate([r[3] for r in results])
    y = np.concatenate([r[4] for r in results])
    w = np.concatenate([r[5] for r in results])
    page = np.concatenate([np.full(len(r[4]), i, dtype=np.int32) for i, r in enumerate(results)])
    halves = np.concatenate([np.full(len(r[4]), 0 if r[2] == "learn" else 1, dtype=np.int8) for r in results])
    chars = np.concatenate([np.array(r[6]) for r in results])
    box = np.concatenate([r[7] for r in results])
    fold = np.concatenate([np.full(len(r[4]), r[8], dtype=np.int8) for r in results])
    types = np.array([r[1] for r in results])
    ids = np.array([r[0] for r in results])
    np.savez_compressed(out, X=X, y=y, w=w, page=page, half=halves, types=types, ids=ids, chars=chars, box=box, fold=fold)
    print(f"{len(results)} pages, {len(y)} blocks, {y.mean():.3f} positive, {X.shape[1]} features -> {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    ap.add_argument("--out", default="/tmp/cr/lbc_dev.npz")
    a = ap.parse_args()
    build(a.split, a.out)


if __name__ == "__main__":
    main()
