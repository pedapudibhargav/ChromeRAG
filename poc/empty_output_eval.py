"""Measure empty-output fixes on WCXB strict-dev train ids only.

Uses held-out fold models ``data/outputs/lbc/cv/fold_{cv_fold(url)}``.
Never opens WCXB test pages. Compares against ``strict_dev_cv.json``.

  pip install -e ".[train,baselines]"
  python -m poc.empty_output_eval --jobs 6
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from chromerag import ChromeRAG, ContentPriority, PipelineConfig
from chromerag.lbc import TwoStageModel
from poc.learn_tokens import cv_fold, cv_site_of
from poc.wcxb import load_split, snippet_rate, strip_front_matter, word_f1

ROOT = Path(__file__).resolve().parents[1]

STRICT_CV = ROOT / "evaluations" / "2026-10-v0.1.3" / "strict_dev_cv.json"
TRAIN_IDS = ROOT / "poc" / "wcxb_strict_train_ids.json"
DEFAULT_MODELS = "data/outputs/lbc/cv/fold_{fold}"
OUT_JSON = ROOT / "data" / "outputs" / "empty_output_eval.json"
PRIORITIES = (
    ("chromerag_precision", ContentPriority.PRECISION),
    ("chromerag", ContentPriority.BALANCED),
    ("chromerag_coverage", ContentPriority.COVERAGE),
)
TYPES = ("article", "forum", "product", "collection", "listing", "documentation", "service")

_models: dict[int, TwoStageModel] = {}
_model_pattern = ""


def fold_for(url: str) -> int:
    return cv_fold(url)


def _worker_init(pattern: str) -> None:
    global _model_pattern
    _model_pattern = pattern


def _fold_model(fold: int) -> TwoStageModel:
    expected = Path(_model_pattern.format(fold=fold))
    if not expected.is_absolute():
        expected = ROOT / expected
    if fold not in _models:
        loaded = TwoStageModel.load(expected)
        if loaded is None:
            raise SystemExit(
                f"missing fold model {expected}; refusing the shipped model, it saw held-out sites"
            )
        _models[fold] = loaded
    return _models[fold]


def load_train_pages(wcxb_root: Path) -> list:
    allow = frozenset(json.loads(TRAIN_IDS.read_text(encoding="utf-8")))
    return [p for p in load_split("dev", root=wcxb_root) if p.id in allow]


def site_bootstrap(
    deltas_by_site: dict[str, list[float]], iters: int = 5000, seed: int = 0
) -> tuple[float, float, float]:
    """Page-weighted cluster bootstrap (sites resampled; mean weighted by page count).

    Matches ``poc.ablation_cv._paired_bootstrap`` weighting so multi-page sites do not
    shrink to a single equally-weighted point.
    """
    if not deltas_by_site:
        return (float("nan"), float("nan"), float("nan"))
    site_sums = np.array([float(sum(v)) for v in deltas_by_site.values()], dtype=np.float64)
    site_sizes = np.array([float(len(v)) for v in deltas_by_site.values()], dtype=np.float64)
    total = float(site_sizes.sum())
    if total <= 0:
        return (float("nan"), float("nan"), float("nan"))
    mean = float(site_sums.sum() / total)
    rng = np.random.default_rng(seed)
    n = len(site_sums)
    samples = np.empty(iters, dtype=np.float64)
    for j in range(iters):
        pick = rng.integers(0, n, n)
        samples[j] = site_sums[pick].sum() / site_sizes[pick].sum()
    return mean, float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))


def _summarize(rows: list[dict[str, Any]], key: str = "f1") -> dict[str, Any]:
    vals = [r[key] for r in rows]
    return {
        "n": len(rows),
        "mean_f1": float(np.mean([r["f1"] for r in rows])) if rows else float("nan"),
        "mean_precision": float(np.mean([r["p"] for r in rows])) if rows else float("nan"),
        "mean_recall": float(np.mean([r["r"] for r in rows])) if rows else float("nan"),
        "mean_without": float(np.mean([r["without"] for r in rows])) if rows else float("nan"),
        "f1_under_0_1": int(sum(1 for r in rows if r["f1"] < 0.1)),
        "ms_median": float(np.median(vals)) if key == "ms" and vals else None,
    }


def _score_one(row: dict[str, Any]) -> dict[str, Any]:
    from poc.table_loss_survey import table_tokens_from_html

    fold = fold_for(row["url"])
    model = _fold_model(fold)
    out: dict[str, Any] = {
        "id": row["id"],
        "type": row["type"],
        "site": row["site"],
        "fold": fold,
        "modes": {},
        "ms": {},
    }
    html_toks = table_tokens_from_html(row["html"])
    gold = {w.lower() for w in re.findall(r"\b\w+\b", row["ref"]) if len(w) > 1}
    html_in_gold = html_toks & gold
    errors = 0
    for name, priority in PRIORITIES:
        cfg = PipelineConfig.from_priority(priority)
        rag = ChromeRAG(config=cfg, lbc_model=model)
        t0 = time.perf_counter()
        try:
            result = rag.extract(row["html"], url=row["url"])
            md = strip_front_matter(result.markdown)
            tables_rescued = int((result.diagnostics.get("lbc") or {}).get("tables_rescued") or 0)
        except Exception as exc:  # noqa: BLE001
            md = ""
            tables_rescued = 0
            errors += 1
            print(f"ERROR {row['id']} {name}: {type(exc).__name__}: {exc}", flush=True)
        ms = (time.perf_counter() - t0) * 1000.0
        p, r, f1 = word_f1(md, row["ref"])
        kept = {w.lower() for w in re.findall(r"\b\w+\b", md) if len(w) > 1}
        lost = html_in_gold - kept
        table_ret = (1 - len(lost) / len(html_in_gold)) if html_in_gold else None
        out["modes"][name] = {
            "p": p,
            "r": r,
            "f1": f1,
            "without": snippet_rate(md, row["without"]),
            "words": len(md.split()),
            "ms": ms,
            "table_retention": table_ret,
            "tables_rescued": tables_rescued,
        }
        out["ms"][name] = ms
    out["extract_errors"] = errors
    return out


def _agg_mode(scored: list[dict], mode: str) -> dict[str, Any]:
    rows = [
        {
            "id": s["id"],
            "type": s["type"],
            "site": s["site"],
            "p": s["modes"][mode]["p"],
            "r": s["modes"][mode]["r"],
            "f1": s["modes"][mode]["f1"],
            "without": s["modes"][mode]["without"],
            "ms": s["modes"][mode]["ms"],
            "table_retention": s["modes"][mode].get("table_retention"),
            "tables_rescued": s["modes"][mode].get("tables_rescued", 0),
        }
        for s in scored
    ]
    ret_vals = [r["table_retention"] for r in rows if r["table_retention"] is not None]
    overall = {
        "mean_f1": float(np.mean([r["f1"] for r in rows])),
        "mean_precision": float(np.mean([r["p"] for r in rows])),
        "mean_recall": float(np.mean([r["r"] for r in rows])),
        "mean_without": float(np.mean([r["without"] for r in rows])),
        "mean_table_retention": float(np.mean(ret_vals)) if ret_vals else None,
        "tables_rescued_total": int(sum(r["tables_rescued"] for r in rows)),
        "f1_under_0_1": int(sum(1 for r in rows if r["f1"] < 0.1)),
        "ms_median": float(np.median([r["ms"] for r in rows])),
        "ms_p99": float(np.percentile([r["ms"] for r in rows], 99)),
    }
    by_type = {}
    for t in TYPES:
        subset = [r for r in rows if r["type"] == t]
        if not subset:
            continue
        by_type[t] = {
            "n": len(subset),
            "mean_f1": float(np.mean([r["f1"] for r in subset])),
            "mean_recall": float(np.mean([r["r"] for r in subset])),
            "mean_without": float(np.mean([r["without"] for r in subset])),
            "f1_under_0_1": int(sum(1 for r in subset if r["f1"] < 0.1)),
        }
    return {"overall": overall, "by_type": by_type, "rows": rows}


def _delta_vs_cv(
    scored: list[dict],
    cv_by_id: dict[str, dict],
    mode: str,
) -> dict[str, Any]:
    d_f1: dict[str, list[float]] = defaultdict(list)
    d_wo: dict[str, list[float]] = defaultdict(list)
    drops: list[dict[str, Any]] = []
    for s in scored:
        cv = cv_by_id[s["id"]][mode]
        after = s["modes"][mode]
        delta = after["f1"] - cv["f1"]
        d_f1[s["site"]].append(delta)
        d_wo[s["site"]].append(after["without"] - cv.get("without", 0.0))
        if delta < -0.05:
            drops.append(
                {
                    "id": s["id"],
                    "type": s["type"],
                    "site": s["site"],
                    "before_f1": cv["f1"],
                    "after_f1": after["f1"],
                    "delta_f1": delta,
                }
            )
    m, lo, hi = site_bootstrap(dict(d_f1))
    wm, wlo, whi = site_bootstrap(dict(d_wo))
    drops.sort(key=lambda r: r["delta_f1"])
    return {
        "delta_f1_mean": m,
        "delta_f1_ci": [lo, hi],
        "delta_without_mean": wm,
        "delta_without_ci": [wlo, whi],
        "f1_drops_gt_0_05": drops,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wcxb", type=Path, default=ROOT / "data" / "wcxb")
    ap.add_argument("--models", default=DEFAULT_MODELS)
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--out", type=Path, default=OUT_JSON)
    ap.add_argument(
        "--before-timing",
        type=Path,
        default=None,
        help="Optional JSON with before ms_median/ms_p99 per mode from a prior baseline run",
    )
    args = ap.parse_args()

    pages = load_train_pages(args.wcxb)
    cv_rows = json.loads(STRICT_CV.read_text(encoding="utf-8"))
    cv_by_id = {r["id"]: r for r in cv_rows}
    missing = [p.id for p in pages if p.id not in cv_by_id]
    if missing:
        raise SystemExit(f"strict_dev_cv.json missing {len(missing)} pages")

    payload = [
        {
            "id": p.id,
            "url": p.url,
            "html": p.html,
            "ref": p.main_content,
            "without": p.without_snippets,
            "type": p.page_type,
            "site": cv_site_of(p.url),
        }
        for p in pages
    ]
    print(f"scoring {len(payload)} strict-dev train pages with {args.jobs} jobs", flush=True)
    _worker_init(args.models)
    if args.jobs == 1:
        scored = [_score_one(r) for r in payload]
    else:
        with ProcessPoolExecutor(
            max_workers=args.jobs, initializer=_worker_init, initargs=(args.models,)
        ) as pool:
            scored = list(pool.map(_score_one, payload, chunksize=4))
    n_errors = sum(int(s.get("extract_errors") or 0) for s in scored)
    print(f"extract_errors={n_errors}", flush=True)

    before_timing = {}
    if args.before_timing and args.before_timing.is_file():
        before_timing = json.loads(args.before_timing.read_text(encoding="utf-8"))

    report: dict[str, Any] = {
        "n_pages": len(scored),
        "models": args.models,
        "modes": {},
        "gate": {},
    }
    for mode, _ in PRIORITIES:
        after = _agg_mode(scored, mode)
        delta = _delta_vs_cv(scored, cv_by_id, mode)
        cv_rows_mode = [
            {
                "f1": cv_by_id[s["id"]][mode]["f1"],
                "p": cv_by_id[s["id"]][mode]["p"],
                "r": cv_by_id[s["id"]][mode]["r"],
                "without": cv_by_id[s["id"]][mode].get("without", 0.0),
            }
            for s in scored
        ]
        before = {
            "mean_f1": float(np.mean([r["f1"] for r in cv_rows_mode])),
            "mean_precision": float(np.mean([r["p"] for r in cv_rows_mode])),
            "mean_recall": float(np.mean([r["r"] for r in cv_rows_mode])),
            "mean_without": float(np.mean([r["without"] for r in cv_rows_mode])),
            "f1_under_0_1": int(sum(1 for r in cv_rows_mode if r["f1"] < 0.1)),
        }
        bt = before_timing.get(mode, {})
        report["modes"][mode] = {
            "before": {**before, "ms_median": bt.get("ms_median"), "ms_p99": bt.get("ms_p99")},
            "after": after["overall"],
            "by_type_after": after["by_type"],
            "delta_vs_cv": {
                "delta_f1_mean": delta["delta_f1_mean"],
                "delta_f1_ci": delta["delta_f1_ci"],
                "delta_without_mean": delta["delta_without_mean"],
                "delta_without_ci": delta["delta_without_ci"],
            },
            "f1_drops_gt_0_05": delta["f1_drops_gt_0_05"],
        }

    bal = report["modes"]["chromerag"]
    f1_ok = bal["after"]["mean_f1"] + 1e-12 >= bal["before"]["mean_f1"]
    wo_ok = (bal["after"]["mean_without"] - bal["before"]["mean_without"]) <= 0.002 + 1e-12
    report["gate"] = {
        "keep_fix": bool(f1_ok and wo_ok),
        "mean_f1_before": bal["before"]["mean_f1"],
        "mean_f1_after": bal["after"]["mean_f1"],
        "mean_without_before": bal["before"]["mean_without"],
        "mean_without_after": bal["after"]["mean_without"],
    }

    # Cohort: balanced F1 < 0.1 with Trafilatura F1 > 0.5 (from CV labels for traf)
    cohort = []
    for s in scored:
        cv = cv_by_id[s["id"]]
        ft = cv["trafilatura"]["f1"]
        fb_before = cv["chromerag"]["f1"]
        fb_after = s["modes"]["chromerag"]["f1"]
        if fb_before < 0.1 and ft > 0.5:
            cohort.append(
                {
                    "id": s["id"],
                    "type": s["type"],
                    "traf_f1": ft,
                    "before_f1": fb_before,
                    "after_f1": fb_after,
                    "after_words": s["modes"]["chromerag"]["words"],
                }
            )
    report["low_f1_high_traf_cohort"] = cohort

    args.out.parent.mkdir(parents=True, exist_ok=True)
    # Keep the JSON smaller: drop per-row mode dumps from by-type helpers (already aggregated).
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["gate"], indent=2))
    print(f"wrote {args.out}")
    bal_after = bal["after"]
    print(
        f"balanced F1 {bal['before']['mean_f1']:.4f} -> {bal_after['mean_f1']:.4f} "
        f"without {bal['before']['mean_without']:.4f} -> {bal_after['mean_without']:.4f} "
        f"F1<0.1 {bal['before']['f1_under_0_1']} -> {bal_after['f1_under_0_1']} "
        f"ms med/p99 {bal_after['ms_median']:.1f}/{bal_after['ms_p99']:.1f}"
    )
    drops = bal["f1_drops_gt_0_05"]
    print(f"balanced F1 drops >0.05: {len(drops)}")
    for d in drops[:30]:
        print(f"  {d['id']} {d['type']} {d['before_f1']:.3f}->{d['after_f1']:.3f} ({d['delta_f1']:+.3f})")


if __name__ == "__main__":
    main()
