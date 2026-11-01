"""Hash default ChromeRAG output on the first N WCXB dev pages (balanced mode)."""

from __future__ import annotations

import argparse
import hashlib

from chromerag import ChromeRAG, ContentPriority, PipelineConfig
from poc.wcxb import load_split


def combined_hash(n: int = 200) -> str:
    pages = sorted(load_split("dev"), key=lambda p: p.id)[:n]
    cfg = PipelineConfig.from_priority(ContentPriority.BALANCED)
    rag = ChromeRAG(config=cfg)
    h = hashlib.sha256()
    for page in pages:
        md = rag.extract(page.html, url=page.url or None).markdown
        h.update(page.id.encode())
        h.update(md.encode())
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=200)
    a = ap.parse_args()
    print(combined_hash(a.n))


if __name__ == "__main__":
    main()
