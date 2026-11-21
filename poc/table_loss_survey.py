"""Survey HTML data-table token retention on WCXB strict-dev train ids only.

Uses held-out fold models ``data/outputs/lbc/cv/fold_{cv_fold(url)}``.
Never opens WCXB test pages. Writes ``data/outputs/table_loss_survey.json``.

  pip install -e ".[train,baselines]"
  python -m poc.table_loss_survey --jobs 6
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
from bs4 import BeautifulSoup

from chromerag import ChromeRAG, ContentPriority, PipelineConfig
from chromerag.tables import _own_rows, is_layout_table
from poc.empty_output_eval import (
    DEFAULT_MODELS,
    _fold_model,
    _worker_init,
    fold_for,
    load_train_pages,
)
from poc.wcxb import strip_front_matter

ROOT = Path(__file__).resolve().parents[1]

OUT_JSON = ROOT / "data" / "outputs" / "table_loss_survey.json"
_TABLE_TOKEN_RE = re.compile(r"\b\w+\b")


def table_tokens_from_html(html: str) -> set[str]:
    """Tokens from non-layout HTML tables with at least two rows."""
    soup = BeautifulSoup(html, "lxml")
    toks: set[str] = set()
    for table in soup.find_all("table"):
        if is_layout_table(table):
            continue
        if len(_own_rows(table)) < 2:
            continue
        text = table.get_text(" ", strip=True)
        toks.update(w.lower() for w in _TABLE_TOKEN_RE.findall(text) if len(w) > 1)
    return toks


def gold_table_tokens(ref: str) -> set[str]:
    """Tokens from pipe or linearized table markup in gold Markdown."""
    toks: set[str] = set()
    in_table = False
    for line in ref.splitlines():
        s = line.strip()
        if s.startswith("|") or s.startswith("[Table:") or s.startswith("Row "):
            in_table = True
            toks.update(
                w.lower()
                for w in _TABLE_TOKEN_RE.findall(s)
                if len(w) > 1 and w not in {"table", "row", "col"}
            )
        elif in_table and (not s or not (s.startswith("|") or s.startswith("Row "))):
            in_table = False
    return toks


def _score_one(row: dict[str, Any]) -> dict[str, Any]:
    fold = fold_for(row["url"])
    model = _fold_model(fold)
    rag = ChromeRAG(config=PipelineConfig.from_priority(ContentPriority.BALANCED), lbc_model=model)
    result = rag.extract(row["html"], url=row["url"])
    md = strip_front_matter(result.markdown)
    html_toks = table_tokens_from_html(row["html"])
    gold = {w.lower() for w in _TABLE_TOKEN_RE.findall(row["ref"]) if len(w) > 1}
    gold_tab = gold_table_tokens(row["ref"])
    kept = {w.lower() for w in _TABLE_TOKEN_RE.findall(md) if len(w) > 1}
    gold_tab_in_html = gold_tab & html_toks if gold_tab else set()
    html_in_gold = html_toks & gold
    lost = gold_tab_in_html - kept
    lost_html = html_in_gold - kept
    lbc = result.diagnostics.get("lbc") or {}
    return {
        "id": row["id"],
        "type": row["type"],
        "n_html_in_gold": len(html_in_gold),
        "n_lost_html_in_gold": len(lost_html),
        "frac_kept_html_in_gold": (1 - len(lost_html) / len(html_in_gold)) if html_in_gold else None,
        "n_gold_tab_in_html": len(gold_tab_in_html),
        "n_lost_gold_tab": len(lost),
        "frac_kept_gold_tab": (1 - len(lost) / len(gold_tab_in_html)) if gold_tab_in_html else None,
        "tables_rescued": int(lbc.get("tables_rescued") or 0),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wcxb", type=Path, default=ROOT / "data" / "wcxb")
    ap.add_argument("--models", default=DEFAULT_MODELS)
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--out", type=Path, default=OUT_JSON)
    args = ap.parse_args()

    pages = load_train_pages(args.wcxb)
    payload = [
        {"id": p.id, "url": p.url, "html": p.html, "ref": p.main_content, "type": p.page_type}
        for p in pages
    ]
    print(f"scoring {len(payload)} strict-dev train pages with {args.jobs} jobs", flush=True)
    _worker_init(args.models)
    if args.jobs == 1:
        rows = [_score_one(r) for r in payload]
    else:
        with ProcessPoolExecutor(
            max_workers=args.jobs, initializer=_worker_init, initargs=(args.models,)
        ) as pool:
            rows = list(pool.map(_score_one, payload, chunksize=4))

    with_html = [r for r in rows if r["n_html_in_gold"] > 0]
    with_gold_tab = [r for r in rows if r["n_gold_tab_in_html"] > 0]
    lost_html = [r for r in with_html if r["n_lost_html_in_gold"] > 0]
    lost_gold = [r for r in with_gold_tab if r["n_lost_gold_tab"] > 0]
    mean_ret = float(np.mean([r["frac_kept_html_in_gold"] for r in with_html])) if with_html else None
    tables_rescued_total = int(sum(r["tables_rescued"] for r in rows))
    pages_rescued = int(sum(1 for r in rows if r["tables_rescued"] > 0))

    by: dict[str, list] = defaultdict(list)
    for r in with_html:
        by[r["type"]].append(r)
    print(f"pages with HTML data-table tokens in gold: {len(with_html)}")
    print(f"pages losing any such tokens: {len(lost_html)}")
    if mean_ret is not None:
        print(f"mean retention of HTML-table∩gold tokens: {mean_ret:.3f}")
    print(f"pages with gold table markup ∩ html table toks: {len(with_gold_tab)}; losing: {len(lost_gold)}")
    print(f"tables_rescued total={tables_rescued_total} pages={pages_rescued}")
    for t, rs in sorted(by.items(), key=lambda x: -len(x[1])):
        lp = sum(1 for r in rs if r["n_lost_html_in_gold"] > 0)
        print(
            f"  {t}: n={len(rs)} loss_pages={lp} "
            f"mean_ret={np.mean([r['frac_kept_html_in_gold'] for r in rs]):.3f}"
        )

    report = {
        "n": len(rows),
        "with_html_in_gold": len(with_html),
        "lost_html_pages": len(lost_html),
        "mean_retention": mean_ret,
        "tables_rescued_total": tables_rescued_total,
        "pages_with_tables_rescued": pages_rescued,
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
