"""Regenerate evaluations/2026-10-v0.1.3/strict_dev_cv.json on strict dev ids only.

Each page is scored with the fold model that never saw its registrable domain
(``data/outputs/lbc/cv/fold_{cv_fold(url)}``). Requires WCXB under ``data/wcxb/`` and
``pip install -e ".[train,baselines]"``.

  python -m poc.run_strict_dev_cv --jobs 6
"""

from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from chromerag import ChromeRAG, ContentPriority, PipelineConfig
from chromerag.lbc import TwoStageModel
from poc.baselines import BASELINES
from poc.learn_tokens import cv_fold, cv_site_of
from poc.wcxb import load_split, snippet_rate, strip_front_matter, word_f1

ROOT = Path(__file__).resolve().parents[1]
IDS_PATH = ROOT / "poc" / "wcxb_strict_train_ids.json"
OUT_PATH = ROOT / "evaluations" / "2026-10-v0.1.3" / "strict_dev_cv.json"
DEFAULT_MODELS = "data/outputs/lbc/cv/fold_{fold}"

CHROMERAG = {
    "chromerag_coverage": ContentPriority.COVERAGE,
    "chromerag": ContentPriority.BALANCED,
    "chromerag_precision": ContentPriority.PRECISION,
}
BASELINE_TOOLS = ("trafilatura", "markitdown", "readability")

_models: dict[int, TwoStageModel] = {}
_model_pattern = ""


def _model_dir(fold: int) -> Path:
    p = Path(_model_pattern.format(fold=fold))
    return p if p.is_absolute() else ROOT / p


def _worker_init(pattern: str) -> None:
    global _model_pattern
    _model_pattern = pattern


def _model(fold: int) -> TwoStageModel:
    if fold not in _models:
        _models[fold] = TwoStageModel.load(_model_dir(fold))
    return _models[fold]


def _tool_row(pred: str, ref: str, page_dict: dict, ms: float | None) -> dict:
    p, r, f1 = word_f1(pred, ref)
    row = {
        "p": p,
        "r": r,
        "f1": f1,
        "with": snippet_rate(pred, page_dict["with_snippets"]),
        "without": snippet_rate(pred, page_dict["without_snippets"]),
    }
    if ms is not None:
        row["ms"] = ms
    return row


def _score(page_dict: dict) -> dict:
    fold = cv_fold(page_dict["url"])
    model = _model(fold)
    ref = page_dict["main_content"]
    row: dict = {"id": page_dict["id"], "type": page_dict["page_type"]}
    for tool in BASELINE_TOOLS:
        t0 = time.perf_counter()
        try:
            pred = strip_front_matter(BASELINES[tool](page_dict["html"]))
        except Exception:  # noqa: BLE001
            pred = ""
        ms = (time.perf_counter() - t0) * 1000.0
        row[tool] = _tool_row(pred, ref, page_dict, ms)
    for name, prio in CHROMERAG.items():
        cfg = PipelineConfig.from_priority(prio, enable_dvdf=True)
        try:
            pred = strip_front_matter(
                ChromeRAG(config=cfg, lbc_model=model)
                .extract(page_dict["html"], url=page_dict["url"] or None)
                .markdown
            )
        except Exception:  # noqa: BLE001
            pred = ""
        row[name] = _tool_row(pred, ref, page_dict, None)
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=None)
    ap.add_argument("--models", default=DEFAULT_MODELS)
    ap.add_argument("--wcxb", type=Path, default=ROOT / "data" / "wcxb")
    args = ap.parse_args()

    allow = frozenset(json.loads(IDS_PATH.read_text(encoding="utf-8")))
    pages = [p for p in load_split("dev", root=args.wcxb) if p.id in allow]
    if len(pages) != len(allow):
        missing = allow - {p.id for p in pages}
        raise SystemExit(f"missing {len(missing)} pages in dev split, e.g. {next(iter(missing))}")
    page_dicts = [
        {
            "id": p.id,
            "url": p.url,
            "page_type": p.page_type,
            "html": p.html,
            "main_content": p.main_content,
            "with_snippets": p.with_snippets,
            "without_snippets": p.without_snippets,
        }
        for p in sorted(pages, key=lambda x: x.id)
    ]
    jobs = args.jobs if args.jobs is not None else int(
        os.environ.get("REBUILD_JOBS", max(1, (os.cpu_count() or 4) - 1))
    )
    _worker_init(args.models)
    if jobs <= 1:
        rows = [_score(pd) for pd in page_dicts]
    else:
        with ProcessPoolExecutor(max_workers=jobs, initializer=_worker_init, initargs=(args.models,)) as pool:
            rows = list(pool.map(_score, page_dicts, chunksize=4))
    assert all(r["id"] in allow for r in rows)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH.relative_to(ROOT)} ({len(rows)} pages, cv_site={cv_site_of(page_dicts[0]['url'])!r} example)")


if __name__ == "__main__":
    main()
