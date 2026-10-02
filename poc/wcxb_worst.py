"""Print worst WCXB dev pages by F1 for a page type."""

from __future__ import annotations

import argparse

from chromerag import ChromeRAG, ContentPriority, PipelineConfig
from poc.wcxb import load_split, strip_front_matter, word_f1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", required=True, help="WCXB page type, e.g. forum or article")
    parser.add_argument("--n", type=int, default=25)
    args = parser.parse_args()

    rag = ChromeRAG(config=PipelineConfig.from_priority(ContentPriority.COVERAGE))
    rows: list[tuple[float, str, str, float, float, str, str]] = []

    for page in load_split("dev"):
        if page.page_type != args.type:
            continue
        pred = strip_front_matter(rag.extract(page.html, url=page.url).markdown)
        p, r, f1 = word_f1(pred, page.main_content)
        rows.append((f1, page.id, page.url, p, r, pred[:300], page.main_content[:300]))

    rows.sort(key=lambda x: x[0])
    for f1, page_id, url, p, r, pred_head, ref_head in rows[: args.n]:
        print(f"\n=== {page_id} F1={f1:.3f} P={p:.3f} R={r:.3f} ===")
        print(url)
        print("--- pred ---")
        print(pred_head)
        print("--- ref ---")
        print(ref_head)


if __name__ == "__main__":
    main()
