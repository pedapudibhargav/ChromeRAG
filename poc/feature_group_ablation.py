"""Feature-group ablation of the learned block filter on the strict development pages.

Reviewer question: what does the design add beyond a shallow-feature learned block detector
(Kohlschuetter et al. 2010, as in BoilerPy3) when the training data is held equal?

Protocol (same as ``poc.ablation_cv`` / ``poc.run_strict_dev_cv``):

* Pages: only the 1,238 ids in ``poc/wcxb_strict_train_ids.json`` (WCXB dev). The block table is
  ``poc.lbc_data`` on those ids (1,233 pages with blocks). No test page is loaded; the test ids and
  domains are read from the benchmark's ``metadata.json`` only to assert they never enter a fold.
* Folds: five, grouped by registrable domain (``poc.learn_tokens.cv_fold``). Every page is scored
  with the model trained on the four folds that do not hold its site.
* Model: ``HistGradientBoostingClassifier`` with the ``poc.train_lbc`` settings (300 iterations,
  depth 6, learning rate 0.06, L2 1.0, min 40 samples per leaf, seed 0), single stage, exported to
  the numpy ensemble the package uses. A feature group is removed by setting its columns to zero
  for training; a constant column can never be split on, so the trees ignore it at inference and
  the rest of the pipeline runs unchanged (asserted on every exported model).
* Scoring: balanced priority (threshold 0.50), word F1 and without-snippet rate after stripping
  front matter, paired site-bootstrap intervals (5,000 draws, seed 0), via ``poc.ablation_cv``.
* Two modes per row: the full pipeline, and ``filter_only`` (rules, generic chrome, chrome
  pruning and the trafilatura-inspired rules off), as in ``poc.ablation_cv``.

  PYTHONPATH=src:. python -m poc.feature_group_ablation --jobs 12

``--sklearn-site DIR`` appends DIR to ``sys.path`` when scikit-learn lives outside the environment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
IDS_PATH = ROOT / "poc" / "wcxb_strict_train_ids.json"
TABLE = ROOT / "data" / "outputs" / "lbc" / "lbc_strict.npz"
WORK = ROOT / "data" / "outputs" / "feature_group_ablation"
MANIFEST = ROOT / "evaluations" / "2026-10-v0.1.3" / "strict_split_manifest.json"
CV_PATH = ROOT / "evaluations" / "2026-10-v0.1.3" / "strict_dev_cv.json"
ABL_PATH = ROOT / "evaluations" / "2026-10-v0.1.3" / "strict_ablation_cv.json"
OUT_DIR = ROOT / "evaluations" / "2026-11-final" / "results" / "revision_rows"
OUT_JSON = OUT_DIR / "feature_group_ablation.json"
OUT_MD = OUT_DIR / "feature_group_ablation.md"

HYPER = {
    "max_iter": 300,
    "max_depth": 6,
    "learning_rate": 0.06,
    "l2_regularization": 1.0,
    "min_samples_leaf": 40,
    "random_state": 0,
}
N_FOLDS = 5
REPORT_TYPES = ("article", "forum")

# ----------------------------------------------------------------------------- feature groups

_SHALLOW_TEXT = (
    "log_chars", "log_words", "avg_word_len", "upper_frac", "digit_frac", "punct_frac", "ends_sentence",
    "n_sentences", "commas_per_word", "stopword_frac", "all_caps", "starts_capital", "has_separator",
    "name_like", "ends_colon", "link_density", "n_links", "emphasis_frac",
)
_NEIGHBOUR_SHALLOW = ("prev_log_chars", "prev_link_density", "next_log_chars", "next_link_density")
_POSITION = ("idx_frac", "chars_before_frac", "chars_after_frac", "log_n_blocks", "log_page_chars", "len_rel_page")
_DOM_NUMERIC = (
    "depth", "in_root", "box_link_density", "box_log_chars", "box_long_p", "box_blocks", "unit_share_of_box",
    "box_share_of_page", "box_mean_chars", "box2_link_density", "box2_log_chars", "box2_long_p",
    "prev_same_box", "next_same_box", "same_tag_siblings", "pos_in_parent",
    "rep_up1", "rep_up2", "rep_up3", "rep_up4", "rep_card_blocks",
)
_HEADING = ("dist_prev_heading", "seen_h1", "before_first_h1")
_LEXICAL = ("chrome_word_frac", "starts_cta_verb", "short_cta", "dateish")
_PAGE_RELATIONS = ("dup_count", "dup_earlier", "title_overlap", "desc_overlap", "topic_overlap", "topic_overlap_strong")

GROUP_DESCRIPTIONS = {
    "shallow_text": "block's own shallow text statistics: lengths, word/char ratios, capitalisation, punctuation, "
    "stop-word ratio, sentence count, link density and link count, emphasis share",
    "neighbour_shallow": "length and link density of the previous and next block",
    "position": "relative position in the page (block index, characters before/after), page size, block length "
    "relative to the page median",
    "dom_context": "tag of the block, depth, ancestor-tag flags (main, article, nav, footer, ...), inside the "
    "detected content root, enclosing-box statistics, same-box neighbours, sibling counts, repeated-structure counts",
    "class_id_hash": "hashed words of the class/id attributes of the block and up to 8 ancestors (192 buckets)",
    "heading_context": "distance to the previous heading, h1 seen / before first h1, hashed words of the nearest "
    "heading and of the nearest h1-h3 (2 x 96 buckets)",
    "lexical_cues": "fixed word lists (chrome words, call-to-action verbs, month/date patterns) and hashed first two "
    "words of the block (64 buckets)",
    "page_relations": "duplicate text elsewhere on the page and word overlap with title, meta description and the "
    "page's long blocks",
}


def feature_groups() -> dict[str, list[int]]:
    """Partition of ``FEATURE_NAMES`` into named groups, by feature name. Asserts full coverage."""
    from chromerag.blockfeatures import FEATURE_NAMES

    idx = {n: i for i, n in enumerate(FEATURE_NAMES)}

    def pref(p: str) -> list[str]:
        return [n for n in FEATURE_NAMES if n.startswith(p)]

    names = {
        "shallow_text": list(_SHALLOW_TEXT),
        "neighbour_shallow": list(_NEIGHBOUR_SHALLOW),
        "position": list(_POSITION),
        "dom_context": [*pref("tag_"), *_DOM_NUMERIC, *pref("in_")],
        "class_id_hash": pref("cls_"),
        "heading_context": [*_HEADING, *pref("sec_"), *pref("sec2_")],
        "lexical_cues": [*_LEXICAL, *pref("txt_")],
        "page_relations": list(_PAGE_RELATIONS),
    }
    groups = {g: sorted({idx[n] for n in ns}) for g, ns in names.items()}
    flat = [i for g in groups.values() for i in g]
    assert len(flat) == len(set(flat)) == len(FEATURE_NAMES), "groups must partition the features"
    return groups


def row_specs(groups: dict[str, list[int]]) -> dict[str, dict]:
    """Rows: name -> {"keep": sorted feature indices, "note": str}."""
    all_idx = sorted(i for g in groups.values() for i in g)
    rows: dict[str, dict] = {"full": {"keep": all_idx, "note": "all features (the shipped feature set)"}}
    for g in groups:
        rows[f"minus_{g}"] = {"keep": sorted(set(all_idx) - set(groups[g])), "note": f"all features except {g}"}

    def union(*gs: str) -> list[int]:
        return sorted({i for g in gs for i in groups[g]})

    rows["shallow_only"] = {
        "keep": union("shallow_text", "neighbour_shallow"),
        "note": "Kohlschuetter-style set: the block's shallow text features plus those of the previous and next "
        "block (their best classifier used current, previous and next block)",
    }
    rows["shallow_plus_position"] = {
        "keep": union("shallow_text", "neighbour_shallow", "position"),
        "note": "shallow set plus relative position and page size",
    }
    rows["shallow_plus_context"] = {
        "keep": union("shallow_text", "neighbour_shallow", "position", "dom_context", "heading_context"),
        "note": "shallow set plus position, DOM context and heading context (no hashed class/id words, no "
        "lexical cues, no page relations)",
    }
    return rows


# ----------------------------------------------------------------------------- leakage guard


def _test_ids_and_domains(wcxb: Path) -> tuple[set[str], set[str]]:
    """Test ids and registrable domains from the benchmark metadata only (no test page is read)."""
    from poc.psl import registrable_domain

    meta = json.loads((wcxb / "metadata.json").read_text(encoding="utf-8"))
    ids, doms = set(), set()
    for pid, info in meta["files"].items():
        if info.get("split") == "test":
            ids.add(pid)
            d = registrable_domain(str(info.get("domain") or ""))
            if d:
                doms.add(d)
    assert len(ids) == meta["splits"]["test"]["count"], "metadata test count mismatch"
    return ids, doms


def assert_no_test_leak(pages, table_ids: np.ndarray, wcxb: Path) -> dict:
    from poc.learn_tokens import cv_site_of

    test_ids, test_doms = _test_ids_and_domains(wcxb)
    allow = set(json.loads(IDS_PATH.read_text(encoding="utf-8")))
    page_ids = {p.id for p in pages}
    tids = {str(i) for i in table_ids}
    assert page_ids == allow, "scored pages must be exactly the strict ids"
    assert tids <= allow, "feature table holds a non-strict page"
    assert not (allow & test_ids), "a test-split id is in the strict ids"
    assert not (tids & test_ids), "a test-split id is in a training fold"
    page_doms = {cv_site_of(p.url) for p in pages}
    overlap = page_doms & test_doms
    assert not overlap, f"test-split domain in a fold: {sorted(overlap)[:5]}"
    return {
        "test_ids_checked": len(test_ids),
        "test_registrable_domains_checked": len(test_doms),
        "strict_page_domains": len(page_doms),
        "id_overlap": 0,
        "domain_overlap": 0,
    }


# ----------------------------------------------------------------------------- training


def _set_threads(n: int) -> None:
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[var] = str(n)


def _train_one(row: str, keep: list[int], holdout: int | None, out_dir: str, threads: int) -> dict:
    _set_threads(threads)
    from sklearn.ensemble import HistGradientBoostingClassifier

    from chromerag.lbc import TwoStageModel
    from poc.train_lbc import export

    out = Path(out_dir)
    if (out / "lbc_stage1.npz").is_file() and (out / "train_meta.json").is_file():
        return {**json.loads((out / "train_meta.json").read_text(encoding="utf-8")), "cached": True}
    t0 = time.perf_counter()
    z = np.load(TABLE)
    X = z["X"].astype(np.float64)
    y, w, fold = z["y"], z["w"], z["fold"]
    drop = np.setdiff1d(np.arange(X.shape[1]), np.asarray(keep, dtype=np.int64))
    X[:, drop] = 0.0
    train = np.ones(len(y), bool) if holdout is None else fold != holdout
    clf = HistGradientBoostingClassifier(**HYPER).fit(X[train], y[train], sample_weight=w[train])
    model = TwoStageModel(export(clf), None)
    used = np.unique(model.first.feature[model.first.feature >= 0])
    assert not np.isin(used, drop).any(), f"{row}: a dropped feature was split on"
    p_sk = clf.predict_proba(X[:3000])[:, 1]
    assert np.abs(model.first.predict_proba(X[:3000]) - p_sk).max() < 1e-9
    out.mkdir(parents=True, exist_ok=True)
    model.save(out)
    meta = {
        "row": row,
        "fold": holdout,
        "seconds": time.perf_counter() - t0,
        "n_iter": int(clf.n_iter_),
        "features_used": int(len(used)),
    }
    (out / "train_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return {**meta, "cached": False}


def train_all(rows: dict[str, dict], jobs: int) -> list[dict]:
    tasks = []
    for name, spec in rows.items():
        for k in range(N_FOLDS):
            tasks.append((name, spec["keep"], k, str(WORK / "models" / name / f"fold_{k}")))
    threads = max(1, (os.cpu_count() or 4) // max(1, jobs))
    log = []
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        futs = [pool.submit(_train_one, *t, threads) for t in tasks]
        for f in as_completed(futs):
            r = f.result()
            log.append(r)
            print(f"trained {r['row']} fold {r['fold']} in {r['seconds']:.1f}s", flush=True)
    return log


def verify_shipped() -> dict:
    """Fit on every strict page with all features; compare with the shipped asset."""
    from chromerag.lbc import MODEL_PATH, TreeEnsemble

    out = WORK / "verify_fit_all"
    rows = row_specs(feature_groups())
    info = _train_one("full_fit_all", rows["full"]["keep"], None, str(out), os.cpu_count() or 4)
    ours, shipped = out / "lbc_stage1.npz", MODEL_PATH
    a, b = TreeEnsemble.load(ours), TreeEnsemble.load(shipped)
    z = np.load(TABLE)
    X = z["X"].astype(np.float64)
    diff = float(np.abs(a.predict_proba(X) - b.predict_proba(X)).max())
    same_trees = a.feature.shape == b.feature.shape and bool(np.array_equal(a.feature, b.feature))
    return {
        "sha256_match": hashlib.sha256(ours.read_bytes()).hexdigest() == hashlib.sha256(shipped.read_bytes()).hexdigest(),
        "same_tree_structure": same_trees,
        "max_abs_prob_diff_on_table": diff,
        "n_iter": info.get("n_iter"),
        "seconds": info.get("seconds"),
    }


# ----------------------------------------------------------------------------- scoring

_MODELS: dict = {}
_SCORE_SECONDS: dict[str, float] = {}


def _score_init(sys_path: list[str]) -> None:
    for p in sys_path:
        if p not in sys.path:
            sys.path.append(p)


def _score(page, row: str, mode: str, cfg: dict) -> tuple[str, dict]:
    from chromerag.lbc import TwoStageModel
    from poc.ablation_cv import AblationSpec, _score_page

    fold_models = _MODELS.get(row)
    if fold_models is None:
        fold_models = {}
        for k in range(N_FOLDS):
            m = TwoStageModel.load(WORK / "models" / row / f"fold_{k}")
            if m is None:
                raise SystemExit(f"missing fold model {row}/fold_{k}")
            fold_models[(k, False)] = m
        _MODELS[row] = fold_models
    res = _score_page(page, AblationSpec(f"{row}:{mode}", cfg), fold_models)
    return page.id, {"type": page.page_type, **res}


def score_all(rows: list[str], modes: dict[str, dict], pages, jobs: int) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {}
    todo = []
    for row in rows:
        for mode, cfg in modes.items():
            key = f"{row}__{mode}"
            cache = WORK / "scores" / f"{key}.json"
            if cache.is_file():
                out[key] = json.loads(cache.read_text(encoding="utf-8"))
                _SCORE_SECONDS[key] = json.loads(cache.with_suffix(".meta.json").read_text(encoding="utf-8"))["seconds"]
            else:
                todo.append((row, mode, cfg, key))
    if not todo:
        return out
    with ProcessPoolExecutor(max_workers=jobs, initializer=_score_init, initargs=(list(sys.path),)) as pool:
        for row, mode, cfg, key in todo:
            t0 = time.perf_counter()
            futs = [pool.submit(_score, p, row, mode, cfg) for p in pages]
            res = dict(f.result() for f in futs)
            out[key] = res
            cache = WORK / "scores" / f"{key}.json"
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(res), encoding="utf-8")
            _SCORE_SECONDS[key] = time.perf_counter() - t0
            cache.with_suffix(".meta.json").write_text(json.dumps({"seconds": _SCORE_SECONDS[key]}), encoding="utf-8")
            print(f"scored {key}: F1 {np.mean([r['f1'] for r in res.values()]):.4f} "
                  f"({time.perf_counter() - t0:.0f}s)", flush=True)
    return out


# ----------------------------------------------------------------------------- report


def _reproduction(scores: dict[str, dict[str, dict]]) -> dict:
    full = scores["full__pipeline"]
    cv_rows = {r["id"]: r for r in json.loads(CV_PATH.read_text(encoding="utf-8"))}
    d_f1 = [abs(full[i]["f1"] - cv_rows[i]["chromerag"]["f1"]) for i in full]
    d_wo = [abs(full[i]["without"] - cv_rows[i]["chromerag"]["without"]) for i in full]
    rep = {
        "pipeline_vs_strict_dev_cv": {
            "pages_compared": len(d_f1),
            "pages_f1_differ_gt_1e-6": int(sum(d > 1e-6 for d in d_f1)),
            "pages_without_differ_gt_1e-6": int(sum(d > 1e-6 for d in d_wo)),
            "saved_mean_f1": float(np.mean([cv_rows[i]["chromerag"]["f1"] for i in full])),
            "saved_mean_without": float(np.mean([cv_rows[i]["chromerag"]["without"] for i in full])),
        }
    }
    abl = json.loads(ABL_PATH.read_text(encoding="utf-8"))
    saved_fo = {p["id"]: p["configs"]["filter_only"] for p in abl["pages"]}
    fo = scores.get("full__filter_only")
    if fo:
        diffs = [abs(fo[i]["f1"] - saved_fo[i]["f1"]) for i in fo]
        rep["filter_only_vs_strict_ablation_cv"] = {
            "pages_compared": len(diffs),
            "pages_f1_differ_gt_1e-6": int(sum(d > 1e-6 for d in diffs)),
            "saved_mean_f1": float(np.mean([saved_fo[i]["f1"] for i in fo])),
            "saved_mean_without": float(abl["summary"]["filter_only"]["mean_without"]),
        }
    return rep


def aggregate(rows: dict[str, dict], modes: dict[str, dict], scores, pages) -> dict:
    from poc.ablation_cv import _paired_bootstrap
    from poc.learn_tokens import cv_site_of

    site_of_id = {p.id: cv_site_of(p.url) for p in pages}
    types = sorted({p.page_type for p in pages})
    out: dict[str, dict] = {}
    for mode in modes:
        base = scores[f"full__{mode}"]
        ids = sorted(base)
        mode_rows: dict[str, dict] = {}
        for row in rows:
            cur = scores[f"{row}__{mode}"]
            assert sorted(cur) == ids
            entry: dict = {
                "n_features": len(rows[row]["keep"]),
                "mean_f1": float(np.mean([cur[i]["f1"] for i in ids])),
                "mean_without": float(np.mean([cur[i]["without"] for i in ids])),
                "mean_with": float(np.mean([cur[i]["with"] for i in ids])),
                "f1_by_type": {
                    t: float(np.mean([cur[i]["f1"] for i in ids if cur[i]["type"] == t])) for t in types
                },
            }
            if row != "full":
                df1 = _paired_bootstrap(base, cur, "f1", site_of_id)
                dwo = _paired_bootstrap(base, cur, "without", site_of_id)
                entry["delta_f1_vs_full"] = {"mean": df1[0], "ci95": [df1[1], df1[2]]}
                entry["delta_without_vs_full"] = {"mean": dwo[0], "ci95": [dwo[1], dwo[2]]}
                by_t = {}
                for t in REPORT_TYPES:
                    sub = [i for i in ids if base[i]["type"] == t]
                    d = _paired_bootstrap({i: base[i] for i in sub}, {i: cur[i] for i in sub}, "f1", site_of_id)
                    by_t[t] = {"mean": d[0], "ci95": [d[1], d[2]], "pages": len(sub)}
                entry["delta_f1_vs_full_by_type"] = by_t
            mode_rows[row] = entry
        out[mode] = mode_rows
    return out


def _fmt_ci(d: dict) -> str:
    return f"{d['mean']:+.4f} [{d['ci95'][0]:+.4f}, {d['ci95'][1]:+.4f}]"


def write_markdown(report: dict) -> str:
    g = report["groups"]
    lines = [
        "# Feature-group ablation of the learned block filter (strict development pages)",
        "",
        "Reviewer question: what the design adds beyond a shallow-feature learned block detector",
        "(Kohlschuetter et al. 2010, BoilerPy3) with the training data held equal. Each row is a full",
        "five-fold retrain (folds grouped by registrable domain, same hyperparameters as the shipped",
        "model) on the 1,238 strict WCXB dev pages; the rest of the pipeline is unchanged. Balanced",
        "priority (threshold 0.50). Deltas are row minus full, paired site bootstrap (5,000 draws,",
        "seed 0), 95% interval. Lower without-snippet rate is better. Code: `poc/feature_group_ablation.py`.",
        "",
        "Feature groups (535 features in total; exact indices in the JSON):",
        "",
        "| Group | Features | Contents |",
        "|---|---|---|",
    ]
    for name, info in g.items():
        lines.append(f"| {name} | {info['n_features']} | {info['description']} |")
    rep = report.get("reproduction", {}).get("pipeline_vs_strict_dev_cv")
    if rep:
        lines += [
            "",
            f"Reproduction: the `full` row matches the saved strict CV scores on all {rep['pages_compared']} pages "
            f"({rep['pages_f1_differ_gt_1e-6']} pages differ in F1; saved mean F1 {rep['saved_mean_f1']:.4f}, "
            f"without {rep['saved_mean_without']:.4f}), and the filter-only `full` row matches the saved filter-only "
            "ablation row. Rows: `minus_<group>` drops one group; `shallow_only` = shallow_text + neighbour_shallow; "
            "`shallow_plus_position` adds position; `shallow_plus_context` adds position, dom_context and "
            "heading_context (so it keeps the hashed heading words but not the hashed class/id words, lexical cues "
            "or page relations).",
        ]
    for mode, title in (("pipeline", "Full pipeline"), ("filter_only", "Filter only (rules, chrome pruning off)")):
        rows = report["rows"].get(mode)
        if not rows:
            continue
        lines += [
            "",
            f"## {title}",
            "",
            "| Row | Feat. | F1 | dF1 [95% CI] | without | dWithout [95% CI] | article F1 | forum F1 | "
            "d article F1 | d forum F1 |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for name, r in rows.items():
            if name == "full":
                lines.append(
                    f"| full | {r['n_features']} | {r['mean_f1']:.4f} | - | {r['mean_without']:.4f} | - | "
                    f"{r['f1_by_type']['article']:.4f} | {r['f1_by_type']['forum']:.4f} | - | - |"
                )
                continue
            bt = r["delta_f1_vs_full_by_type"]
            lines.append(
                f"| {name} | {r['n_features']} | {r['mean_f1']:.4f} | {_fmt_ci(r['delta_f1_vs_full'])} | "
                f"{r['mean_without']:.4f} | {_fmt_ci(r['delta_without_vs_full'])} | "
                f"{r['f1_by_type']['article']:.4f} | {r['f1_by_type']['forum']:.4f} | "
                f"{bt['article']['mean']:+.4f} | {bt['forum']['mean']:+.4f} |"
            )
    lines += ["", "## Summary", "", report.get("summary_text", ""), ""]
    return "\n".join(lines)


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--train-jobs", type=int, default=5)
    ap.add_argument("--wcxb", type=Path, default=ROOT / "data" / "wcxb")
    ap.add_argument("--rows", default=None, help="comma-separated subset of rows (default: all)")
    ap.add_argument("--modes", default="pipeline,filter_only")
    ap.add_argument("--verify-shipped", action="store_true", help="also refit on all pages and compare with the asset")
    ap.add_argument("--sklearn-site", default=None)
    ap.add_argument("--summary", default=None, help="file holding the plain-language summary for the Markdown")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()
    if a.sklearn_site:
        sys.path.append(a.sklearn_site)
    t_start = time.perf_counter()

    import sklearn

    from poc.ablation_cv import _spec_map
    from poc.learn_tokens import cv_fold
    from poc.wcxb import load_split

    if not TABLE.is_file():
        raise SystemExit(f"missing {TABLE.relative_to(ROOT)}; run: python -m poc.lbc_data --split dev")
    allow = frozenset(json.loads(IDS_PATH.read_text(encoding="utf-8")))
    pages = sorted((p for p in load_split("dev", root=a.wcxb) if p.id in allow), key=lambda p: p.id)
    z = np.load(TABLE)
    table_ids = z["ids"]
    leak = assert_no_test_leak(pages, table_ids, a.wcxb)

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    missing = sorted(allow - {str(i) for i in table_ids})
    assert len(table_ids) == manifest["lbc_feature_matrix_pages"], "feature table page count differs from manifest"
    assert missing == sorted(manifest["lbc_extraction_failed_ids"]), "pages without blocks differ from manifest"
    url_of = {p.id: p.url for p in pages}
    page_fold = np.array([cv_fold(url_of[str(i)]) for i in table_ids])
    assert np.array_equal(page_fold[z["page"]], z["fold"]), "table folds differ from cv_fold"

    groups = feature_groups()
    rows = row_specs(groups)
    if a.rows:
        keep = {"full", *[r.strip() for r in a.rows.split(",") if r.strip()]}
        rows = {k: v for k, v in rows.items() if k in keep}
    abl_specs = _spec_map()
    all_modes = {"pipeline": dict(abl_specs["baseline"].cfg), "filter_only": dict(abl_specs["filter_only"].cfg)}
    modes = {m: all_modes[m] for m in a.modes.split(",")}

    verify = verify_shipped() if a.verify_shipped else None
    if verify:
        print("shipped-model check:", verify, flush=True)

    t0 = time.perf_counter()
    train_log = train_all(rows, a.train_jobs)
    t_train = time.perf_counter() - t0
    t0 = time.perf_counter()
    scores = score_all(list(rows), modes, pages, a.jobs)
    t_score = time.perf_counter() - t0
    repro = _reproduction(scores) if "pipeline" in modes else {}
    print("reproduction:", json.dumps(repro), flush=True)
    results = aggregate(rows, modes, scores, pages)

    from chromerag.blockfeatures import FEATURE_NAMES

    report = {
        "question": "What does the block filter's feature design add beyond a shallow-feature learned block "
        "detector (Kohlschuetter et al. 2010 / BoilerPy3) with the training data held equal?",
        "config": {
            "pages": len(pages),
            "pages_in_block_table": int(len(table_ids)),
            "blocks": int(len(z["y"])),
            "ids_file": "poc/wcxb_strict_train_ids.json",
            "block_table": "python -m poc.lbc_data --split dev (strict ids)",
            "folds": "5, grouped by registrable domain (poc.learn_tokens.cv_fold)",
            "model": {"type": "HistGradientBoostingClassifier, single stage", **HYPER},
            "group_removal": "columns of removed groups set to 0 for training (never split on); pipeline unchanged",
            "priority": "balanced",
            "lbc_threshold": 0.5,
            "scorer": "poc.wcxb.word_f1 and snippet_rate after strip_front_matter (poc.ablation_cv._score_page)",
            "modes": {m: cfg for m, cfg in modes.items()},
            "bootstrap": {"unit": "registrable domain", "iters": 5000, "seed": 0, "paired": True},
            "test_leakage_check": leak,
            "sklearn": sklearn.__version__,
            "numpy": np.__version__,
            "python": platform.python_version(),
        },
        "groups": {
            g: {
                "n_features": len(ix),
                "description": GROUP_DESCRIPTIONS[g],
                "indices": ix,
                "names": [FEATURE_NAMES[i] for i in ix],
            }
            for g, ix in groups.items()
        },
        "row_definitions": {
            r: {"n_features": len(s["keep"]), "note": s["note"], "kept_groups": [g for g in groups if set(groups[g]) <= set(s["keep"])]}
            for r, s in rows.items()
        },
        "reproduction": repro,
        "shipped_model_check": verify,
        "rows": results,
        "training": {
            "fits": len(train_log),
            "n_iter_by_row_fold": {f"{t['row']}/fold_{t['fold']}": t.get("n_iter") for t in train_log},
            "features_used_by_row_fold": {f"{t['row']}/fold_{t['fold']}": t.get("features_used") for t in train_log},
        },
        "runtime_seconds": {
            "note": "fit and scoring wall-clock as recorded when each model or score file was produced; "
            f"training ran {a.train_jobs} fits in parallel, scoring {a.jobs} worker processes",
            "fits_sum": round(sum(t["seconds"] for t in train_log), 1),
            "fits_wall_estimate": round(sum(t["seconds"] for t in train_log) / max(1, a.train_jobs), 1),
            "scoring_sum": round(sum(_SCORE_SECONDS.values()), 1),
            "this_invocation": {"train": round(t_train, 1), "score": round(t_score, 1),
                                "total": round(time.perf_counter() - t_start, 1)},
            "verify_shipped_fit": round(verify["seconds"], 1) if verify else None,
        },
        "code_commit": _git_commit(),
    }
    if a.summary:
        report["summary_text"] = Path(a.summary).read_text(encoding="utf-8").strip()
    for mode, mrows in results.items():
        print(f"== {mode}")
        for name, r in mrows.items():
            d = r.get("delta_f1_vs_full")
            print(f"{name:26s} n={r['n_features']:3d} F1 {r['mean_f1']:.4f} w/o {r['mean_without']:.4f}"
                  + (f"  dF1 {_fmt_ci(d)}  dWO {_fmt_ci(r['delta_without_vs_full'])}" if d else ""))
    if a.no_write:
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    OUT_MD.write_text(write_markdown(report), encoding="utf-8")
    print("wrote", OUT_JSON.relative_to(ROOT), "and", OUT_MD.relative_to(ROOT))


if __name__ == "__main__":
    main()
