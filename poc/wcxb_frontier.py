"""Precision-recall frontier and confidence calibration on WCXB dev, from held-out fold models.

For every dev page the model of the fold that does not contain the page's site is used, so no
number comes from a model that saw the page. Output: per-page F1 at each threshold, plus the model's
own expected F1 at the default threshold (``diagnostics["lbc"]["expected_f1"]``).

  python -m poc.wcxb_frontier --models data/outputs/lbc/cv{fold} --out evaluations/.../wcxb_dev_frontier.json
"""

from __future__ import annotations

import argparse
import json
import zlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from chromerag import ChromeRAG, ContentPriority, PipelineConfig
from chromerag.lbc import TwoStageModel
from poc.learn_tokens import site_of
from poc.wcxb import load_split, strip_front_matter, word_f1

THRESHOLDS = (0.15, 0.25, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90)
_MODELS: dict[int, TwoStageModel] = {}
_PATTERN = ""


def _model(fold: int) -> TwoStageModel:
    if fold not in _MODELS:
        _MODELS[fold] = TwoStageModel.load(Path(_PATTERN.format(fold=fold)))
    return _MODELS[fold]


def _one(page):
    fold = zlib.crc32(site_of(page.url).encode()) % 5
    model = _model(fold)
    row = {"id": page.id, "type": page.page_type, "fold": fold, "thr": {}}
    for thr in THRESHOLDS:
        cfg = PipelineConfig.from_priority(ContentPriority.BALANCED)
        cfg.lbc_threshold = thr
        res = ChromeRAG(config=cfg, lbc_model=model).extract(page.html, url=page.url or None)
        p, r, f1 = word_f1(strip_front_matter(res.markdown), page.main_content)
        row["thr"][str(thr)] = [p, r, f1]
        if thr == 0.50:
            row["expected"] = res.diagnostics.get("lbc", {})
    return row


def main() -> None:
    global _PATTERN
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="data/outputs/lbc/cv{fold}")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    _PATTERN = a.models
    pages = load_split("dev")
    with ProcessPoolExecutor(initializer=_init, initargs=(a.models,)) as pool:
        rows = list(pool.map(_one, pages, chunksize=8))
    Path(a.out).write_text(json.dumps(rows))
    print("wrote", a.out, len(rows))


def _init(pattern: str) -> None:
    global _PATTERN
    _PATTERN = pattern


if __name__ == "__main__":
    main()
