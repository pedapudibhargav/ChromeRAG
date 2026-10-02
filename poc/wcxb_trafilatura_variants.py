"""Trafilatura under different settings on WCXB dev, to show the baseline is not under-configured.

The word-F1 comparison in the paper uses ``include_tables=True, include_comments=False,
include_links=False`` (Markdown output). This scores the library defaults and the recall setting too.
"""

from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor

from poc.wcxb import load_split, word_f1

VARIANTS = {
    "defaults": {},
    "tables_markdown (paper baseline)": {"include_tables": True, "include_comments": False, "include_links": False, "output_format": "markdown"},
    "favor_recall": {"favor_recall": True, "include_tables": True},
    "favor_precision": {"favor_precision": True, "include_tables": True},
    "recall+comments": {"favor_recall": True, "include_tables": True, "include_comments": True},
}


def _one(page):
    import trafilatura

    out = {}
    for name, kw in VARIANTS.items():
        try:
            text = trafilatura.extract(page.html, **kw) or ""
        except Exception:  # noqa: BLE001
            text = ""
        out[name] = word_f1(text, page.main_content)[2]
    return page.page_type, out


def main() -> None:
    pages = load_split("dev")
    with ProcessPoolExecutor() as pool:
        rows = list(pool.map(_one, pages, chunksize=8))
    result = {}
    for name in VARIANTS:
        vals = [r[1][name] for r in rows]
        result[name] = {"all": sum(vals) / len(vals)}
        for t in sorted({r[0] for r in rows}):
            v = [r[1][name] for r in rows if r[0] == t]
            result[name][t] = sum(v) / len(v)
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
