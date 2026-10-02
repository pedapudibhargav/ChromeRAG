"""Quantified error taxonomy of the block classifier on WCXB dev (held-out fold models).

Every block is scored by the model of the fold that does not contain its site, labelled from the
human reference (see poc/lbc_data.py), and every mistake is assigned to one category using only the
block's tag, the words in its ancestors' class/id, and its text. Output: words per category.

  python -m poc.wcxb_errors --out evaluations/2026-10-v0.1.3/wcxb_dev_errors.json
"""

from __future__ import annotations

import argparse
import json
import re
import zlib
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from chromerag import ChromeRAG, ContentPriority, PipelineConfig
from chromerag.blockfeatures import block_features, find_blocks
from chromerag.extractor import StopExtraction
from chromerag.lbc import TwoStageModel
from chromerag.treestats import TreeStats
from poc.lbc_data import label_blocks
from poc.learn_tokens import site_of
from poc.wcxb import load_split

THRESHOLD = 0.5
_MODELS: dict[int, TwoStageModel] = {}
_SPLIT = re.compile(r"[^a-z]+")
GROUPS = {
    "comments": {"comment", "comments", "disqus", "respond", "reply", "replies", "discussion"},
    "related": {"related", "recommended", "popular", "trending", "suggested", "latest", "recent", "more"},
    "share/subscribe": {"share", "sharing", "social", "follow", "subscribe", "newsletter", "signup"},
    "author/meta": {"author", "byline", "bio", "meta", "posted", "avatar", "profile", "user", "date"},
    "promo/cta": {"promo", "cta", "banner", "advert", "ads", "sponsor", "offer"},
    "nav/footer": {"nav", "menu", "footer", "header", "sidebar", "breadcrumb", "toc", "widget"},
}


def _words(tag) -> set[str]:
    out: set[str] = set()
    for node in [tag, *list(tag.parents)[:8]]:
        if getattr(node, "attrs", None) is None:
            continue
        for v in [*(node.get("class") or []), node.get("id") or ""]:
            out.update(w for w in _SPLIT.split(str(v).lower()) if len(w) > 2)
    return out


def category(tag, text: str, fp: bool) -> str:
    words = _words(tag)
    for name, vocab in GROUPS.items():
        if words & vocab:
            return name
    n = len(text.split())
    if tag.name.startswith("h") and len(tag.name) == 2:
        return "heading"
    if tag.name in ("pre", "code") or tag.find("code"):
        return "code"
    if tag.name == "table":
        return "table"
    if tag.name in ("li", "dt", "dd"):
        return "list item"
    if n <= 5:
        return "short fragment"
    return "prose paragraph" if tag.name in ("p", "blockquote") else "other text block"


def _one(args):
    page, pattern = args
    fold = zlib.crc32(site_of(page.url).encode()) % 5
    if fold not in _MODELS:
        _MODELS[fold] = TwoStageModel.load(Path(pattern.format(fold=fold)))
    model = _MODELS[fold]
    cap: dict = {}

    def capture(soup, root):
        body = soup.body or soup
        stats = TreeStats(body)
        blocks = find_blocks(body, stats)
        X, box = block_features(blocks, body, stats, root)
        chars = np.array([len(b.text) for b in blocks])
        cap["rows"] = [(b.tag, b.text) for b in blocks]
        cap["p"] = model.predict(X.astype("float64"), chars, box)

    rag = ChromeRAG(config=PipelineConfig.from_priority(ContentPriority.BALANCED), lbc_model=model)
    rag._capture = capture
    try:
        rag.extract(page.html, url=page.url or None)
    except StopExtraction:
        pass
    if "rows" not in cap:
        return page.page_type, {}
    y, w = label_blocks([t for _, t in cap["rows"]], page.main_content, page.without_snippets)
    out: Counter = Counter()
    for (tag, text), p, yy, ww in zip(cap["rows"], cap["p"], y, w, strict=True):
        kept = p >= THRESHOLD
        if kept and yy == 0:
            out["FP|" + category(tag, text, True)] += int(len(text.split()))
        elif not kept and yy == 1:
            out["FN|" + category(tag, text, False)] += int(len(text.split()))
        elif kept:
            out["TP"] += int(len(text.split()))
    return page.page_type, dict(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="data/outputs/lbc/cv{fold}")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    pages = load_split("dev")
    with ProcessPoolExecutor() as pool:
        rows = list(pool.map(_one, [(p, a.models) for p in pages], chunksize=8))
    agg: dict[str, Counter] = defaultdict(Counter)
    for t, c in rows:
        agg[t].update(c)
        agg["ALL"].update(c)
    Path(a.out).write_text(json.dumps({k: dict(v) for k, v in agg.items()}, indent=1))
    for t in ("article", "documentation", "ALL"):
        c = agg[t]
        tp = c["TP"]
        fp = sum(v for k, v in c.items() if k.startswith("FP|"))
        fn = sum(v for k, v in c.items() if k.startswith("FN|"))
        print(f"\n== {t}: words kept correctly {tp}, wrongly kept {fp}, wrongly dropped {fn}")
        for kind in ("FP", "FN"):
            tot = fp if kind == "FP" else fn
            for k, v in sorted(((k, v) for k, v in c.items() if k.startswith(kind + "|")), key=lambda kv: -kv[1])[:8]:
                print(f"   {k:28s} {v:8d}  {v / max(tot, 1):5.1%}")


if __name__ == "__main__":
    main()
