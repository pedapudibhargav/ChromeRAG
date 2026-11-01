"""Strict dev-only component ablation on site-grouped 5-fold CV models.

Scores only pages in poc/wcxb_strict_train_ids.json. Each page uses the fold model that never
saw its site (data/outputs/lbc/cv/fold_K/). Writes evaluations/2026-10-v0.1.3/strict_ablation_cv.json.

  python -m poc.ablation_cv
  python -m poc.ablation_cv --configs baseline,no_lbc --jobs 4
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
import time
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
IDS_PATH = ROOT / "poc" / "wcxb_strict_train_ids.json"
CV_MODEL_DIR = ROOT / "data" / "outputs" / "lbc" / "cv"
STACK_MODEL_DIR = ROOT / "data" / "outputs" / "lbc" / "cv_stack"
CACHE_DIR = ROOT / "data" / "outputs" / "ablation_cv"
CV_PATH = ROOT / "evaluations" / "2026-10-v0.1.3" / "strict_dev_cv.json"
OUT_PATH = ROOT / "evaluations" / "2026-10-v0.1.3" / "strict_ablation_cv.json"
LBC_DATA = ROOT / "data" / "outputs" / "lbc" / "lbc_strict.npz"

BOOTSTRAP_ITERS = 5000
BOOTSTRAP_SEED = 0

TF_RULE_PREFIXES = (
    "tf.share",
    "tf.related",
    "tf.comments",
    "tf.newsletter",
    "tf.sidebar",
    "tf.ads",
    "tf.author",
    "tf.pagination",
    "tf.skip",
    "tf.footer",
    "tf.tools",
    "tf.tags",
)

CHROME_ABLATIONS = (
    ("chrome_no_toc", "chrome_drop_toc"),
    ("chrome_no_pager", "chrome_drop_pager"),
    ("chrome_no_comments", "chrome_drop_comments"),
    ("chrome_no_related", "chrome_drop_related"),
    ("chrome_no_cta", "chrome_drop_cta"),
    ("chrome_no_share", "chrome_drop_share"),
    ("chrome_no_newsletter", "chrome_drop_newsletter"),
    ("chrome_no_author", "chrome_drop_author_bio"),
    ("chrome_no_tail", "chrome_trim_tail"),
    ("chrome_no_attr_junk", "chrome_drop_attr_junk"),
)

YAML_SKIP_ABLATIONS = (
    ("no_yaml_consent", frozenset({"consent"})),
    ("no_yaml_docs_generators", frozenset({"docs_generators"})),
    ("no_yaml_share_related", frozenset({"share_related"})),
    ("no_yaml_trafilatura_inspired", frozenset({"trafilatura_inspired"})),
)


@dataclass
class AblationSpec:
    name: str
    cfg: dict[str, Any] = field(default_factory=dict)
    skip_rule_stems: frozenset[str] | None = None
    rule_disabled_prefixes: frozenset[str] | None = None
    stack: bool = False


def all_specs() -> list[AblationSpec]:
    specs = [AblationSpec("baseline")]
    specs.extend(
        [
            AblationSpec("no_lbc", {"enable_lbc": False}),
            AblationSpec("no_lbc_structure", {"enable_lbc_structure_rules": False}),
            AblationSpec("no_chrome_prune", {"enable_chrome_prune": False}),
            AblationSpec("no_generic_chrome", {"enable_generic_chrome": False}),
            AblationSpec("no_rules", {"enable_rules": False}),
            AblationSpec("no_trafilatura_ideas", {"enable_trafilatura_rules": False}),
            AblationSpec("no_table_rescue", {"lbc_rescue_tables": False}),
            AblationSpec(
                "filter_only",
                {
                    "enable_lbc": True,
                    "enable_rules": False,
                    "enable_generic_chrome": False,
                    "enable_chrome_prune": False,
                    "enable_trafilatura_rules": False,
                },
            ),
            AblationSpec(
                "rules_only",
                {
                    "enable_lbc": False,
                    "enable_dvdf": False,
                    "max_rejected_drop_chars": 0,
                    "enable_rules": True,
                    "enable_generic_chrome": True,
                    "enable_chrome_prune": True,
                    "enable_trafilatura_rules": True,
                },
            ),
        ]
    )
    for name, stems in YAML_SKIP_ABLATIONS:
        specs.append(AblationSpec(name, skip_rule_stems=stems))
    for name, flag in CHROME_ABLATIONS:
        specs.append(AblationSpec(name, {flag: False}))
    for prefix in TF_RULE_PREFIXES:
        specs.append(AblationSpec(f"no_{prefix.replace('.', '_')}", rule_disabled_prefixes=frozenset({prefix})))
    specs.append(AblationSpec("stack_stage2", stack=True))
    return specs


def _spec_map() -> dict[str, AblationSpec]:
    return {s.name: s for s in all_specs()}


def _page_fold(url: str) -> int:
    from poc.learn_tokens import site_of

    return zlib.crc32(site_of(url).encode()) % 5


def _load_pages():
    from poc.wcxb import load_split

    allow = frozenset(json.loads(IDS_PATH.read_text(encoding="utf-8")))
    return [p for p in load_split("dev") if p.id in allow]


def _model_for_fold(fold: int, *, stack: bool):
    from chromerag.lbc import TwoStageModel

    base = STACK_MODEL_DIR if stack else CV_MODEL_DIR
    model = TwoStageModel.load(base / f"fold_{fold}")
    if model is None or (stack and model.second is None):
        raise SystemExit(f"missing fold model {base / f'fold_{fold}'}; refusing the shipped model, it saw held-out sites")
    return model


def _rule_index(spec: AblationSpec):
    from chromerag.rules_engine import RuleIndex, load_rules

    if spec.skip_rule_stems:
        return RuleIndex(load_rules(skip_stems=spec.skip_rule_stems))
    return None


def _score_page(page, spec: AblationSpec, models: dict):
    from chromerag import ChromeRAG, ContentPriority, PipelineConfig
    from poc.wcxb import snippet_rate, strip_front_matter, word_f1

    fold = _page_fold(page.url)
    cfg_kw = dict(spec.cfg)
    cfg = PipelineConfig.from_priority(ContentPriority.BALANCED, **cfg_kw)
    rule_index = _rule_index(spec)
    prefixes = set(spec.rule_disabled_prefixes) if spec.rule_disabled_prefixes else None
    rag = ChromeRAG(
        config=cfg,
        lbc_model=models[(fold, spec.stack)],
        rule_index=rule_index,
        rule_disabled_prefixes=prefixes,
    )
    t0 = time.perf_counter()
    md = strip_front_matter(rag.extract(page.html, url=page.url or None).markdown)
    ms = (time.perf_counter() - t0) * 1000.0
    p, r, f1 = word_f1(md, page.main_content)
    return {
        "p": p,
        "r": r,
        "f1": f1,
        "with": snippet_rate(md, page.with_snippets),
        "without": snippet_rate(md, page.without_snippets),
        "ms": ms,
    }


def _score_config(spec: AblationSpec, pages, jobs: int):
    models = {(k, spec.stack): _model_for_fold(k, stack=spec.stack) for k in range(5)}
    cache = CACHE_DIR / f"{spec.name}.pkl"
    if cache.is_file():
        return pickle.loads(cache.read_bytes())

    rows: dict[str, dict] = {}
    if jobs <= 1:
        for page in pages:
            rows[page.id] = {"type": page.page_type, **_score_page(page, spec, models)}
    else:
        try:
            with ProcessPoolExecutor(max_workers=jobs) as pool:
                futs = {pool.submit(_score_page, page, spec, models): page for page in pages}
                for fut in as_completed(futs):
                    page = futs[fut]
                    rows[page.id] = {"type": page.page_type, **fut.result()}
        except (PermissionError, OSError):
            for page in pages:
                rows[page.id] = {"type": page.page_type, **_score_page(page, spec, models)}
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(pickle.dumps(rows))
    return rows


def _paired_bootstrap(
    baseline: dict[str, dict],
    other: dict[str, dict],
    key: str,
    site_of_id: dict[str, str],
) -> tuple[float, float, float]:
    """Paired bootstrap resampling whole sites, since pages of one site are not independent."""
    ids = sorted(baseline.keys())
    diffs = np.array([other[i][key] - baseline[i][key] for i in ids], dtype=np.float64)
    mean = float(diffs.mean())
    by_site: dict[str, list[int]] = {}
    for pos, i in enumerate(ids):
        by_site.setdefault(site_of_id[i], []).append(pos)
    site_sums = np.array([diffs[v].sum() for v in by_site.values()], dtype=np.float64)
    site_sizes = np.array([len(v) for v in by_site.values()], dtype=np.float64)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    n = len(site_sums)
    samples = np.empty(BOOTSTRAP_ITERS, dtype=np.float64)
    for j in range(BOOTSTRAP_ITERS):
        pick = rng.integers(0, n, n)
        samples[j] = site_sums[pick].sum() / site_sizes[pick].sum()
    lo, hi = float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))
    return mean, lo, hi


def _trafilatura_rows(pages) -> dict[str, dict]:
    from poc.baselines import BASELINES
    from poc.wcxb import strip_front_matter, word_f1

    traf_fn = BASELINES["trafilatura"]
    out: dict[str, dict] = {}
    for page in pages:
        try:
            md = strip_front_matter(traf_fn(page.html))
        except Exception:  # noqa: BLE001
            md = ""
        p, r, f1 = word_f1(md, page.main_content)
        out[page.id] = {"p": p, "r": r, "f1": f1}
    return out


def _stack_model_bytes() -> int:
    total = 0
    for fold in range(5):
        d = STACK_MODEL_DIR / f"fold_{fold}"
        for name in ("lbc_stage1.npz", "lbc_stage2.npz"):
            p = d / name
            if p.is_file():
                total += p.stat().st_size
    return total


def _build_fold_train_npz(holdout: int, dest: Path) -> None:
    z = np.load(LBC_DATA)
    keep = z["fold"] != holdout
    pages_kept = np.unique(z["page"][keep])
    remap = {int(old): new for new, old in enumerate(pages_kept)}
    page = np.array([remap[int(p)] for p in z["page"][keep]], dtype=np.int32)
    dest.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        dest,
        X=z["X"][keep],
        y=z["y"][keep],
        w=z["w"][keep],
        page=page,
        half=z["half"][keep],
        types=z["types"][pages_kept],
        ids=z["ids"][pages_kept],
        chars=z["chars"][keep],
        box=z["box"][keep],
        fold=z["fold"][keep],
    )


def _train_stack_for_holdout(holdout: int) -> None:
    from sklearn.ensemble import HistGradientBoostingClassifier

    from chromerag.lbc import TwoStageModel
    from poc.train_lbc import export, stacked

    out = STACK_MODEL_DIR / f"fold_{holdout}"
    if (out / "lbc_stage1.npz").is_file() and (out / "lbc_stage2.npz").is_file():
        return
    subset = STACK_MODEL_DIR / f"train_fold_{holdout}.npz"
    if not subset.is_file():
        _build_fold_train_npz(holdout, subset)
    z = np.load(subset)
    X, y, w = z["X"].astype(np.float64), z["y"], z["w"]
    chars, box, page, fold = z["chars"], z["box"], z["page"], z["fold"]
    idx = np.arange(len(y))
    present = sorted(int(v) for v in np.unique(fold))

    def make():
        return HistGradientBoostingClassifier(
            max_iter=300,
            max_depth=6,
            learning_rate=0.06,
            l2_regularization=1.0,
            min_samples_leaf=40,
            random_state=0,
        )

    oof = np.zeros(len(y))
    for k in present:
        fit = idx[fold != k]
        hold = idx[fold == k]
        if len(hold) == 0:
            continue
        oof[hold] = make().fit(X[fit], y[fit], sample_weight=w[fit]).predict_proba(X[hold])[:, 1]
    first = make().fit(X, y, sample_weight=w)
    X2 = np.hstack([X, stacked(oof, chars, box, page)])
    second = make().fit(X2, y, sample_weight=w)
    model = TwoStageModel(export(first), export(second))
    out.mkdir(parents=True, exist_ok=True)
    model.save(out)


def _train_stack_models(jobs: int) -> None:
    if not LBC_DATA.is_file():
        raise SystemExit(f"Missing {LBC_DATA}; run poc.lbc_data with strict ids first.")

    if jobs == 1:
        for k in range(5):
            _train_stack_for_holdout(k)
    else:
        with ProcessPoolExecutor(max_workers=min(5, jobs)) as pool:
            list(pool.map(_train_stack_for_holdout, range(5)))


def _aggregate(
    specs: list[AblationSpec],
    per_config: dict[str, dict[str, dict]],
    pages,
    traf: dict[str, dict],
) -> dict:
    baseline = per_config["baseline"]
    page_ids = sorted(baseline.keys())
    types = sorted({baseline[i]["type"] for i in page_ids})
    from poc.learn_tokens import site_of

    site_of_id = {p.id: site_of(p.url) for p in pages}
    cv_rows = json.loads(CV_PATH.read_text(encoding="utf-8"))
    bad = [r["id"] for r in cv_rows if abs(r["chromerag"]["f1"] - baseline[r["id"]]["f1"]) > 1e-6]
    if len(cv_rows) != len(page_ids) or bad:
        raise SystemExit(f"baseline differs from strict_dev_cv.json on {len(bad)} pages, e.g. {bad[:5]}")

    summary: dict[str, Any] = {}
    for spec in specs:
        rows = per_config[spec.name]
        ms = [rows[i]["ms"] for i in page_ids]
        entry: dict[str, Any] = {
            "mean_f1": float(np.mean([rows[i]["f1"] for i in page_ids])),
            "mean_without": float(np.mean([rows[i]["without"] for i in page_ids])),
            "median_ms": float(np.median(ms)),
        }
        if spec.name != "baseline":
            df1 = _paired_bootstrap(baseline, rows, "f1", site_of_id)
            dw = _paired_bootstrap(baseline, rows, "without", site_of_id)
            entry["delta_f1"] = {"mean": df1[0], "ci95": [df1[1], df1[2]]}
            entry["delta_without"] = {"mean": dw[0], "ci95": [dw[1], dw[2]]}
        if spec.stack:
            entry["stack_model_bytes"] = _stack_model_bytes()
        summary[spec.name] = entry

    by_type: dict[str, list[dict]] = {}
    for t in types:
        ids_t = [i for i in page_ids if baseline[i]["type"] == t]
        ranked = []
        for spec in specs:
            if spec.name == "baseline":
                continue
            rows = per_config[spec.name]
            deltas = [rows[i]["f1"] - baseline[i]["f1"] for i in ids_t]
            ranked.append({"config": spec.name, "mean_delta_f1": float(np.mean(deltas)) if deltas else float("nan")})
        ranked.sort(key=lambda x: x["mean_delta_f1"])
        by_type[t] = ranked

    loss_rank = []
    for pid in page_ids:
        gap = baseline[pid]["f1"] - traf[pid]["f1"]
        loss_rank.append(
            {
                "id": pid,
                "delta_f1_vs_trafilatura": gap,
                "baseline_p": baseline[pid]["p"],
                "baseline_r": baseline[pid]["r"],
                "trafilatura_p": traf[pid]["p"],
                "trafilatura_r": traf[pid]["r"],
            }
        )
    loss_rank.sort(key=lambda x: x["delta_f1_vs_trafilatura"])
    worst40 = loss_rank[:40]

    per_page = []
    for pid in page_ids:
        row = {"id": pid, "type": baseline[pid]["type"], "baseline": {k: baseline[pid][k] for k in ("p", "r", "f1", "with", "without")}}
        row["configs"] = {
            name: {k: per_config[name][pid][k] for k in ("p", "r", "f1", "with", "without")}
            for name in per_config
            if name != "baseline"
        }
        for name in per_config:
            if name == "baseline":
                continue
            b, c = baseline[pid], per_config[name][pid]
            row.setdefault("delta", {})[name] = {"f1": c["f1"] - b["f1"], "without": c["without"] - b["without"]}
        per_page.append(row)

    return {
        "protocol": {
            "pages": len(page_ids),
            "ids_file": "poc/wcxb_strict_train_ids.json",
            "cv_models": "data/outputs/lbc/cv/fold_{0..4}",
            "priority": "balanced",
            "bootstrap_iters": BOOTSTRAP_ITERS,
            "bootstrap_seed": BOOTSTRAP_SEED,
        },
        "summary": summary,
        "mean_delta_f1_by_type_sorted": by_type,
        "baseline_vs_trafilatura_worst40": worst40,
        "pages": per_page,
    }


def _print_table(summary: dict) -> None:
    print(f"{'config':32s} {'dF1':>8s} {'95% CI':>18s} {'d w/o':>8s} {'95% CI':>18s}")
    for name, row in summary.items():
        if name == "baseline":
            print(f"{name:32s} {'—':>8s} {'':>18s} {'—':>8s} {'':>18s}")
            continue
        df1 = row["delta_f1"]
        dw = row["delta_without"]
        ci1 = f"[{df1['ci95'][0]:+.4f}, {df1['ci95'][1]:+.4f}]"
        ciw = f"[{dw['ci95'][0]:+.4f}, {dw['ci95'][1]:+.4f}]"
        print(f"{name:32s} {df1['mean']:+.4f} {ci1:>18s} {dw['mean']:+.4f} {ciw:>18s}")


def _stack_ready() -> bool:
    return all((STACK_MODEL_DIR / f"fold_{k}" / "lbc_stage2.npz").is_file() for k in range(5))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=None, help="parallel workers per config")
    ap.add_argument("--configs", default=None, help="comma-separated subset (default: all)")
    ap.add_argument("--train-stack", action="store_true", help="train stacked fold models if missing")
    ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args()

    if a.no_cache and CACHE_DIR.is_dir():
        for p in CACHE_DIR.glob("*.pkl"):
            p.unlink()

    smap = _spec_map()
    if a.configs:
        names = [n.strip() for n in a.configs.split(",") if n.strip()]
        specs = [smap[n] for n in names]
    else:
        specs = all_specs()
        if not _stack_ready():
            _train_stack_models(a.jobs or 1)

    pages = _load_pages()
    jobs = a.jobs or max(1, min(8, (os.cpu_count() or 4) - 1))

    per_config: dict[str, dict[str, dict]] = {}
    for spec in specs:
        per_config[spec.name] = _score_config(spec, pages, jobs)

    if "baseline" not in per_config:
        per_config["baseline"] = _score_config(smap["baseline"], pages, jobs)

    traf = _trafilatura_rows(pages)
    run_specs = specs if a.configs else [s for s in all_specs() if s.name in per_config]
    report = _aggregate(run_specs, per_config, pages, traf)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    _print_table(report["summary"])
    if "stack_stage2" in report["summary"]:
        st = report["summary"]["stack_stage2"]
        print(
            f"stack_stage2: median_ms={st['median_ms']:.1f} bytes={st.get('stack_model_bytes', 0)} "
            f"dF1={st['delta_f1']['mean']:+.4f}"
        )
    print("wrote", OUT_PATH.relative_to(ROOT))


if __name__ == "__main__":
    main()
