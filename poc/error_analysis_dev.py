"""WCXB strict-dev error analysis: where balanced ChromeRAG loses to Trafilatura.

Uses pages in poc/wcxb_strict_train_ids.json only. Scores each page with the held-out
site-grouped fold model (zlib.crc32(site_of(url)) % 5), matching strict_dev_cv.json protocol.
Stage attribution via config ablations; fix candidates tested with in-script overrides only.

Run from repo root:
  PYTHONPATH=src:../sk-overlay:. .venv/bin/python -m poc.error_analysis_dev --jobs 6
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import zlib
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SK_OVERLAY = ROOT.parent / "sk-overlay"
for p in (str(SK_OVERLAY), str(ROOT / "src"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from chromerag import ChromeRAG, ContentPriority, PipelineConfig  # noqa: E402
from chromerag.lbc import TwoStageModel  # noqa: E402
from poc.baselines import BASELINES  # noqa: E402
from poc.learn_tokens import site_of  # noqa: E402
from poc.wcxb import load_split, snippet_rate, strip_front_matter, tokenize, word_f1  # noqa: E402

STRICT_CV = ROOT / "evaluations" / "2026-10-v0.1.3" / "strict_dev_cv.json"
TRAIN_IDS = ROOT / "poc" / "wcxb_strict_train_ids.json"
DEFAULT_WCXB = ROOT / "data" / "wcxb"
DEFAULT_MODELS = "data/outputs/lbc/cv/fold_{fold}"
CV_F1_TOL = 1e-6
OUT_DIR = ROOT / "data" / "outputs"
OUT_JSON = OUT_DIR / "error_analysis_dev.json"
OUT_MD = OUT_DIR / "error_analysis_dev.md"

STAGE_ABLATIONS: list[tuple[str, dict[str, Any]]] = [
    ("learned_filter", {"enable_lbc": False}),
    ("chrome_prune", {"enable_chrome_prune": False}),
    ("generic_detectors", {"enable_generic_chrome": False}),
    ("tail_trim", {"chrome_trim_tail": False}),
    ("trafilatura_rules", {"enable_trafilatura_rules": False}),
    ("rule_index", {"enable_rules": False}),
    ("lbc_structure_rules", {"enable_lbc_structure_rules": False}),
    ("lbc_stage2_off", {"enable_lbc_stage2": False}),
]

CAUSE_GROUPS: dict[str, str] = {
    "learned_filter": "lost_content",
    "lbc_structure_rules": "lost_content",
    "lbc_stage2_off": "lost_content",
    "chrome_prune": "lost_content",
    "generic_detectors": "lost_content",
    "tail_trim": "lost_content",
    "trafilatura_rules": "lost_content",
    "rule_index": "lost_content",
    "unattributed": "lost_content",
    "residual_chrome": "residual_chrome",
    "no_gold_loss": "residual_chrome",
    "suspect_gold": "suspect",
    "immaterial": "immaterial",
}

FIXES: dict[str, dict[str, Any]] = {
    "lower_lbc_threshold": {"lbc_threshold": 0.40},
    "disable_repeat_text_drop": {"lbc_drop_repeats": False},
    "relax_chrome_prune": {"enable_chrome_prune": False},
    "disable_tail_trim": {"chrome_trim_tail": False},
    "disable_trafilatura_micro": {"trafilatura_micro": False},
}


def fold_for(url: str) -> int:
    return zlib.crc32(site_of(url).encode()) % 5


def load_train_pages(wcxb_root: Path) -> list:
    allow = frozenset(json.loads(TRAIN_IDS.read_text(encoding="utf-8")))
    return [p for p in load_split("dev", root=wcxb_root) if p.id in allow]


def rank_worst(cv_rows: list[dict], pages_by_id: dict) -> list[str]:
    scored = []
    for r in cv_rows:
        pid = r["id"]
        if pid not in pages_by_id:
            continue
        gap = r["trafilatura"]["f1"] - r["chromerag"]["f1"]
        scored.append((gap, pid, r["type"]))
    scored.sort(reverse=True)
    top = [pid for _, pid, _ in scored[:40]]
    types = Counter(t for _, _, t in scored[:40])
    if types.get("product", 0) < 5:
        extra = [pid for _, pid, t in scored if t == "product" and pid not in top][:10]
        top.extend(extra)
    if types.get("listing", 0) < 5:
        extra = [pid for _, pid, t in scored if t == "listing" and pid not in top][:10]
        top.extend(extra)
    return top


_models: dict[int, TwoStageModel] = {}
_model_dirs: dict[int, Path] = {}
_model_pattern = ""


def _worker_init(pattern: str) -> None:
    global _model_pattern
    _model_pattern = pattern


def _expected_model_dir(fold: int) -> Path:
    p = Path(_model_pattern.format(fold=fold))
    return p if p.is_absolute() else ROOT / p


def _fold_model(fold: int) -> TwoStageModel:
    expected = _expected_model_dir(fold)
    if fold not in _models:
        if not expected.is_dir():
            raise FileNotFoundError(f"missing fold model directory: {expected}")
        _model_dirs[fold] = expected
        _models[fold] = TwoStageModel.load(expected)
    if _model_dirs[fold] != expected:
        raise AssertionError(f"fold {fold}: loaded {_model_dirs[fold]} but expected {expected}")
    return _models[fold]


def _assert_page_fold_model(url: str | None) -> int:
    fold = fold_for(url or "")
    _fold_model(fold)
    return fold


def extract_md(html: str, url: str | None, overrides: dict[str, Any] | None = None) -> str:
    overrides = overrides or {}
    fold = _assert_page_fold_model(url)
    cfg = PipelineConfig.from_priority(ContentPriority.BALANCED, **overrides)
    try:
        res = ChromeRAG(config=cfg, lbc_model=_fold_model(fold)).extract(html, url=url)
        return strip_front_matter(res.markdown)
    except Exception:
        return ""


def trafilatura_md(html: str) -> str:
    try:
        return strip_front_matter(BASELINES["trafilatura"](html))
    except Exception:
        return ""


def _verify_one(row: dict) -> dict | None:
    pid, url, html, ref = row["id"], row["url"], row["html"], row["ref"]
    exp = row["expected"]
    fold = _assert_page_fold_model(url)
    if fold != fold_for(url):
        return {"id": pid, "field": "fold", "got": fold, "expected": fold_for(url)}
    bal = extract_md(html, url)
    traf = trafilatura_md(html)
    f_bal = word_f1(bal, ref)[2]
    f_traf = word_f1(traf, ref)[2]
    out: dict | None = None
    if abs(f_bal - exp["chromerag"]["f1"]) > CV_F1_TOL:
        out = {
            "id": pid,
            "field": "chromerag.f1",
            "got": f_bal,
            "expected": exp["chromerag"]["f1"],
            "fold": fold,
        }
    if abs(f_traf - exp["trafilatura"]["f1"]) > CV_F1_TOL:
        traf_m = {
            "id": pid,
            "field": "trafilatura.f1",
            "got": f_traf,
            "expected": exp["trafilatura"]["f1"],
            "fold": fold,
        }
        return traf_m if out is None else out
    return out


def verify_strict_cv(pages: list, cv_by_id: dict[str, dict], jobs: int, model_pattern: str) -> None:
    """Recompute balanced ChromeRAG and Trafilatura F1; abort if any page differs from strict_dev_cv."""
    payload = [
        {
            "id": p.id,
            "url": p.url,
            "html": p.html,
            "ref": p.main_content,
            "expected": cv_by_id[p.id],
        }
        for p in pages
        if p.id in cv_by_id
    ]
    missing_cv = {p.id for p in pages} - set(cv_by_id)
    if missing_cv:
        raise SystemExit(f"strict_dev_cv.json missing {len(missing_cv)} train pages (e.g. {next(iter(missing_cv))})")

    _worker_init(model_pattern)
    if jobs == 1:
        bad = [m for m in (_verify_one(r) for r in payload) if m]
    else:
        with ProcessPoolExecutor(max_workers=jobs, initializer=_worker_init, initargs=(model_pattern,)) as pool:
            bad = [m for m in pool.map(_verify_one, payload, chunksize=8) if m]

    if bad:
        sample = bad[:20]
        msg = (
            f"CV F1 verification failed for {len(bad)}/{len(payload)} pages "
            f"(tolerance {CV_F1_TOL}). First mismatches:\n"
            + "\n".join(json.dumps(m) for m in sample)
        )
        raise SystemExit(msg)
    print(f"verified chromerag/trafilatura F1 for {len(payload)} strict dev pages (±{CV_F1_TOL})")


def attribute_lost_words(page, cache: dict[tuple, str]) -> tuple[str, Counter, list[str]]:
    ref_c = Counter(tokenize(page.main_content))
    bal = cache.setdefault(("bal", page.id), extract_md(page.html, page.url))
    lost = ref_c - Counter(tokenize(bal))
    if not sum(lost.values()):
        return "no_gold_loss", Counter(), []
    samples = [w for w, _ in lost.most_common(40)]
    stage_hits: Counter = Counter()
    excerpts: list[str] = []
    for w in samples:
        stage = "unattributed"
        for name, kw in STAGE_ABLATIONS:
            key = (name, page.id)
            if key not in cache:
                cache[key] = extract_md(page.html, page.url, kw)
            if w in set(tokenize(cache[key])):
                stage = name
                break
        stage_hits[stage] += 1
        if len(excerpts) < 5:
            excerpts.append(w)
    primary = stage_hits.most_common(1)[0][0]
    return primary, stage_hits, excerpts


def residual_chrome_words(page, bal: str, traf: str) -> Counter:
    ref = set(tokenize(page.main_content))
    bal_c, traf_c = Counter(tokenize(bal)), Counter(tokenize(traf))
    extra = bal_c - traf_c
    noise = Counter()
    for w, n in extra.items():
        if w not in ref:
            noise[w] = n
    return noise


def classify_page(page, cv_row: dict, cache: dict) -> dict:
    gap = cv_row["trafilatura"]["f1"] - cv_row["chromerag"]["f1"]
    bal = cache.setdefault(("bal", page.id), extract_md(page.html, page.url))
    traf = cache.setdefault(("traf", page.id), trafilatura_md(page.html))
    _, _, f_bal = word_f1(bal, page.main_content)
    _, _, f_traf = word_f1(traf, page.main_content)

    suspect = f_traf > 0.95 and f_bal < 0.5 and gap > 0.3
    immaterial = gap < 0.02

    primary, hits, excerpts = attribute_lost_words(page, cache)
    if suspect:
        cause = "suspect_gold"
    elif immaterial:
        cause = "immaterial"
    elif primary == "no_gold_loss":
        noise = residual_chrome_words(page, bal, traf)
        if sum(noise.values()) >= 20:
            cause = "residual_chrome"
            primary = "residual_chrome"
        else:
            cause = "no_gold_loss"
    else:
        cause = primary

    return {
        "id": page.id,
        "type": page.page_type,
        "gap": gap,
        "f_bal": f_bal,
        "f_traf": f_traf,
        "cause": cause,
        "cause_group": CAUSE_GROUPS.get(cause, "lost_content"),
        "stage_hits": dict(hits),
        "excerpts": excerpts,
    }


def site_bootstrap(deltas_by_site: dict[str, float], iters: int = 5000) -> tuple[float, float, float]:
    sites = list(deltas_by_site.values())
    if not sites:
        return (float("nan"), float("nan"), float("nan"))
    mean = float(np.mean(sites))
    rng = np.random.default_rng(0)
    n = len(sites)
    bs = [float(np.mean([sites[rng.integers(0, n)] for _ in range(n)])) for _ in range(iters)]
    return mean, float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def eval_fixes(pages, jobs: int, model_pattern: str) -> dict[str, Any]:
    payload = [
        {
            "id": p.id,
            "url": p.url,
            "html": p.html,
            "ref": p.main_content,
            "without": p.without_snippets,
            "site": site_of(p.url),
        }
        for p in pages
    ]

    def one(row: dict) -> tuple[str, str, dict[str, tuple[float, float]]]:
        scores: dict[str, tuple[float, float]] = {}
        for name, kw in [("baseline", {})] + list(FIXES.items()):
            md = extract_md(row["html"], row["url"], kw)
            f1 = word_f1(md, row["ref"])[2]
            wo = snippet_rate(md, row["without"])
            scores[name] = (f1, wo)
        return row["id"], row["site"], scores

    rows: list[tuple[str, str, dict]] = []
    if jobs == 1:
        _worker_init(model_pattern)
        rows = [one(r) for r in payload]
    else:
        with ProcessPoolExecutor(max_workers=jobs, initializer=_worker_init, initargs=(model_pattern,)) as pool:
            rows = list(pool.map(one, payload, chunksize=4))

    out: dict[str, Any] = {}
    for fix in FIXES:
        d_f1: dict[str, float] = defaultdict(list)
        d_wo: dict[str, float] = defaultdict(list)
        for _pid, site, scores in rows:
            b_f1, b_wo = scores["baseline"]
            f_f1, f_wo = scores[fix]
            d_f1[site].append(f_f1 - b_f1)
            d_wo[site].append(f_wo - b_wo)
        site_f1 = {s: float(np.mean(v)) for s, v in d_f1.items()}
        site_wo = {s: float(np.mean(v)) for s, v in d_wo.items()}
        m, lo, hi = site_bootstrap(site_f1)
        wm, wlo, whi = site_bootstrap(site_wo)
        out[fix] = {
            "delta_f1_mean": m,
            "delta_f1_ci": [lo, hi],
            "delta_without_mean": wm,
            "delta_without_ci": [wlo, whi],
        }
    return out


def build_markdown(
    cause_table: list[dict],
    fix_results: dict[str, Any],
    evidence: dict[str, list[str]],
    notes: list[str],
) -> str:
    lines = [
        "# WCXB strict dev: balanced vs Trafilatura (worst-gap analysis)",
        "",
        "Pages: `poc/wcxb_strict_train_ids.json` only. Fold: `crc32(site) % 5` held-out LBC models.",
        "",
        "## Causes (worst-gap cohort)",
        "",
        "| Cause | Group | Pages | Σ F1 gap | Generic fix | ΔF1 (site bootstrap 95% CI) | Δ without-snippet |",
        "|---|---|---:|---:|---|---:|---:|",
    ]
    fix_for_cause = {
        "learned_filter": "lower_lbc_threshold",
        "chrome_prune": "relax_chrome_prune",
        "tail_trim": "disable_tail_trim",
        "trafilatura_rules": "disable_trafilatura_micro",
        "residual_chrome": "lower_lbc_threshold",
        "no_gold_loss": "disable_repeat_text_drop",
    }
    for row in cause_table:
        fix_key = fix_for_cause.get(row["cause"], "")
        fr = fix_results.get(fix_key, {})
        d_f1 = fr.get("delta_f1_mean")
        ci = fr.get("delta_f1_ci", [None, None])
        d_wo = fr.get("delta_without_mean")
        fix_label = fix_key.replace("_", " ") if fix_key else "—"
        ci_s = f"{d_f1:+.4f} [{ci[0]:+.4f}, {ci[1]:+.4f}]" if d_f1 is not None else "—"
        wo_s = f"{d_wo:+.4f}" if d_wo is not None else "—"
        lines.append(
            f"| {row['cause']} | {row['group']} | {row['pages']} | {row['f1_lost']:.3f} | {fix_label} | {ci_s} | {wo_s} |"
        )
    lines.extend(["", "## Fix evaluation (all strict dev pages, paired vs baseline balanced)", ""])
    lines.append("| Fix | ΔF1 mean | 95% CI | Δ without-snippet mean | 95% CI |")
    lines.append("|---|---:|---|---:|---|")
    for fix, fr in fix_results.items():
        ci = fr["delta_f1_ci"]
        wci = fr["delta_without_ci"]
        lines.append(
            f"| {fix} | {fr['delta_f1_mean']:+.4f} | [{ci[0]:+.4f}, {ci[1]:+.4f}] | "
            f"{fr['delta_without_mean']:+.4f} | [{wci[0]:+.4f}, {wci[1]:+.4f}] |"
        )
    lines.extend(["", "## Evidence excerpts (lost gold words)", ""])
    for cause, ex in evidence.items():
        lines.append(f"### {cause}")
        for e in ex[:3]:
            lines.append(f"- `{e}`")
        lines.append("")
    if notes:
        lines.extend(["## Notes", ""] + [f"- {n}" for n in notes])
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wcxb-root", type=Path, default=Path(os.environ.get("CHROMERAG_WCXB", DEFAULT_WCXB)))
    ap.add_argument("--models", default=str(DEFAULT_MODELS))
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--skip-fix-eval", action="store_true")
    a = ap.parse_args()

    pages = load_train_pages(a.wcxb_root)
    by_id = {p.id: p for p in pages}
    cv = json.loads(STRICT_CV.read_text(encoding="utf-8"))
    cv_by_id = {r["id"]: r for r in cv}

    global _model_pattern
    _model_pattern = a.models
    verify_strict_cv(pages, cv_by_id, a.jobs, a.models)

    worst_ids = rank_worst(cv, by_id)
    if a.jobs == 1:
        _worker_init(a.models)

    cache: dict = {}
    analyses = [classify_page(by_id[pid], cv_by_id[pid], cache) for pid in worst_ids if pid in by_id]

    grouped: dict[str, list] = defaultdict(list)
    for row in analyses:
        grouped[row["cause"]].append(row)

    cause_table = []
    evidence: dict[str, list[str]] = defaultdict(list)
    for cause, rows in sorted(grouped.items(), key=lambda kv: -sum(r["gap"] for r in kv[1])):
        cause_table.append(
            {
                "cause": cause,
                "group": CAUSE_GROUPS.get(cause, "lost_content"),
                "pages": len(rows),
                "f1_lost": sum(r["gap"] for r in rows),
            }
        )
        for r in rows:
            for ex in r["excerpts"]:
                if len(evidence[cause]) < 3 and ex not in evidence[cause]:
                    evidence[cause].append(ex)

    notes = []
    suspect_n = sum(1 for r in analyses if r["cause"] == "suspect_gold")
    immaterial_n = sum(1 for r in analyses if r["cause"] == "immaterial")
    if suspect_n:
        notes.append(f"{suspect_n} worst-gap pages flagged suspect_gold (Trafilatura F1≈1, balanced recall collapse).")
    if immaterial_n:
        notes.append(f"{immaterial_n} pages have gap < 0.02 (immaterial).")
    top_cause = cause_table[0]["cause"] if cause_table else "—"
    notes.append(f"Largest cause bucket in worst-gap cohort: {top_cause} ({cause_table[0]['pages']} pages).")

    fix_results = {}
    if not a.skip_fix_eval:
        fix_results = eval_fixes(pages, a.jobs, a.models)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(
            {
                "worst_ids": worst_ids,
                "analyses": analyses,
                "cause_table": cause_table,
                "fix_results": fix_results,
                "evidence": evidence,
                "notes": notes,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    OUT_MD.write_text(
        build_markdown(cause_table, fix_results, evidence, notes),
        encoding="utf-8",
    )
    print("wrote", OUT_MD)


if __name__ == "__main__":
    main()
