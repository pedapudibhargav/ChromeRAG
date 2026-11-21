"""Planned analysis of the human rating set (evaluations/2026-11-final/PROTOCOL.md).

Follows "Analysis plan for the human rating set (fixed before any rating)" and the amendments after it.
Inputs, all repository-relative except the label key:

  --ratings   pseudonymized rating files (default evaluations/2026-11-final/human_set_ratings/rater-*.json)
  --key       label key that maps the blind labels A, B, C of each item to tools, the item to its page and
              repeats to their originals (default evaluations/2026-11-final/human_set_ratings/label_key.json).
              Optional fields used when present: "calibration" (practice item ids), "anchors" (anchor item
              ids) and "output_chars" (characters of each labelled output, for the length analysis).
  --bundle    optional rating bundle (outputs as shown to raters); used for the practice-item ids and output
              lengths when the key lacks them. It holds third-party page text and is not redistributed.
  --part-plan optional part plan with the anchor items, when the key lacks them.

Page metadata (evaluations/2026-11-final/human_set/corpus_pages.json) and the AI judge verdicts
(evaluations/2026-11-final/results/human_set_ai_judges/) are read from the repository.

  PYTHONPATH=src:. python -m poc.human_set_analysis --out OUT_DIR [--key KEY.json] [--bundle BUNDLE.json]

Writes results.json and results.md. Readings of ambiguous points are listed in results.json under "readings".
`--export-key OUT.json` writes a key with the optional fields filled in from a full key, bundle and part plan
(item ids and integer lengths only; no page or output text), so the analysis runs from the repository alone.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

SEED = 20261120
ITERS = 10_000
TOOLS = ("chromerag", "trafilatura", "readability")
PAIRS = (("chromerag", "trafilatura"), ("chromerag", "readability"), ("trafilatura", "readability"))
JUDGES = ("gpt", "grok", "gemini")
MIN_GROUP = 8

# Careless-rater rule (amendment 2026-11-02), same constants as evaluators/author/analyze.py
CARE_MIN_MEDIAN_SECONDS = 30.0
CARE_MIN_REPEATS = 4
CARE_MIN_REPEAT_AGREE = 0.6
CARE_MIN_ITEMS_SAME = 10
CARE_MAX_SAME_SHARE = 0.9

# Length analysis, same constants as poc/final_page_length_analysis.py
SIMILAR_LENGTH_RATIO = 1.1
LEN_ITERS = 2000
LEN_FIT_ITERS = 500

ROOT = Path(__file__).resolve().parents[1]
FINAL = ROOT / "evaluations" / "2026-11-final"
DEFAULT_RATINGS = FINAL / "human_set_ratings"
DEFAULT_KEY = DEFAULT_RATINGS / "label_key.json"
CORPUS = FINAL / "human_set" / "corpus_pages.json"
JUDGE_DIR = FINAL / "results" / "human_set_ai_judges"


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return Path(path).name


def registrable_domain(site: str) -> str:
    host = site.split("/")[0].lower()
    labels = host.split(".")
    multi = {"co.uk", "ac.uk", "gov.uk", "org.uk", "com.au"}
    if len(labels) >= 3 and ".".join(labels[-2:]) in multi:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


# ---------------------------------------------------------------- loading


def add_input_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--ratings", type=Path, default=DEFAULT_RATINGS, help="Folder of pseudonymized rating files")
    ap.add_argument("--key", type=Path, default=DEFAULT_KEY, help="Label key (default: label_key.json beside the ratings)")
    ap.add_argument("--bundle", type=Path, help="Optional rating bundle (practice items, output lengths)")
    ap.add_argument("--part-plan", type=Path, help="Optional part plan (anchor items)")


def load(args):
    key_doc = read_json(args.key)
    bundle = read_json(args.bundle) if args.bundle else None
    part_plan = read_json(args.part_plan) if args.part_plan else None
    corpus = read_json(CORPUS)
    judges = {j: read_json(JUDGE_DIR / f"{j}.json") for j in JUDGES}
    paths = sorted(Path(args.ratings).glob("rater-*.json"))
    if not paths:
        sys.exit(f"no rater-*.json files in {args.ratings}")
    results = [read_json(p) for p in paths]
    seen: Counter = Counter()
    for res in results:  # two files with the same rater code are kept apart
        seen[res["rater"]] += 1
        if seen[res["rater"]] > 1:
            res["rater"] = f"{res['rater']}#{seen[res['rater']]}"
    return key_doc, bundle, part_plan, corpus, judges, results, [rel(p) for p in paths]


def calibration_ids(key_doc, bundle) -> set[str]:
    if "calibration" in key_doc:
        return set(key_doc["calibration"])
    if bundle is not None:
        return {it["item_id"] for it in bundle["calibration"]}
    sys.exit("the key has no 'calibration' list (practice item ids); pass --bundle so practice items can be left out")


def anchor_ids(key_doc, part_plan) -> set[str] | None:
    if "anchors" in key_doc:
        return set(key_doc["anchors"])
    if part_plan is not None:
        return set(part_plan["anchors"])
    return None


def prepare(args):
    """Load inputs and unblind; shared by the secondary scripts (score differences, AI judges by subset)."""
    key_doc, bundle, part_plan, corpus, judges, results, paths = load(args)
    cal = calibration_ids(key_doc, bundle)
    repeat_of = key_doc["repeat_of"]
    meta = {p["id"]: p for p in corpus}
    item_site, item_site_field, item_group = {}, {}, {}
    for i in key_doc["key"]:
        if i in cal:
            continue
        m = meta[key_doc["page_of"][repeat_of.get(i, i)]]
        item_site[i] = registrable_domain(m["site"])
        item_site_field[i] = m["site"]
        item_group[i] = m["page_type"]
        assert m["page_type"] == key_doc["page_types"][repeat_of.get(i, i)]
    per_rater, exclusions = unblind(results, key_doc, cal)
    return {
        "key_doc": key_doc, "bundle": bundle, "part_plan": part_plan, "judges": judges, "paths": paths,
        "cal": cal, "repeat_of": repeat_of, "item_site": item_site, "item_site_field": item_site_field,
        "item_group": item_group, "per_rater": per_rater, "exclusions": exclusions,
    }


def export_key(key_doc, bundle, part_plan, out: Path) -> None:
    """Key for publication: labels, pages, repeats, page types, practice and anchor item ids, output lengths.

    No page text and no output text."""
    reduced = {k: key_doc[k] for k in ("bundle_id", "tools", "key", "page_of", "repeat_of", "page_types") if k in key_doc}
    reduced["calibration"] = sorted(calibration_ids(key_doc, bundle))
    anchors = anchor_ids(key_doc, part_plan)
    if anchors is not None:
        reduced["anchors"] = sorted(anchors)
    chars = output_chars(key_doc, bundle)
    if chars is not None:
        reduced["output_chars"] = {i: chars[i] for i in sorted(chars)}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(reduced, indent=1) + "\n", encoding="utf-8")
    print(f"reduced key written to {out}")


def pairwise(best: set, a: str, b: str, all_same: bool) -> str:
    if all_same:
        return "tie"
    ha, hb = a in best, b in best
    if ha and not hb:
        return "a"
    if hb and not ha:
        return "b"
    return "tie"


def unblind(results, key_doc, cal):
    key = key_doc["key"]
    per_rater: dict[str, dict[str, dict]] = {}
    exclusions = []
    for res in results:
        r = res["rater"]
        per_rater[r] = {}
        for iid, e in res["items"].items():
            if iid in cal:
                continue
            if iid not in key:
                exclusions.append({"rater": r, "item_id": iid, "reason": "missing_key"})
                continue
            if e.get("skipped"):
                exclusions.append({"rater": r, "item_id": iid, "reason": "skipped"})
                continue
            sc = e.get("scores") or {}
            chosen = e.get("all_same") or e.get("none_good") or e.get("best")
            if not chosen or not all((sc.get(lab) or {}).get("content") and (sc.get(lab) or {}).get("chrome") for lab in key[iid]):
                exclusions.append({"rater": r, "item_id": iid, "reason": "incomplete"})
                continue
            labels = list(e.get("best") or [])
            order = list(e.get("shown_order") or sorted(key[iid]))
            best_tools = {key[iid][lab] for lab in labels if lab in key[iid]}
            v = {}
            for a, b in PAIRS:
                x = pairwise(best_tools, a, b, bool(e.get("all_same")))
                if e.get("none_good") and not best_tools:
                    x = "tie"
                v[(a, b)] = x
            per_rater[r][iid] = {
                "verdict": v,
                "full_answer": (tuple(sorted(best_tools)), bool(e.get("all_same")), bool(e.get("none_good"))),
                "scores": {key[iid][lab]: (float(s["content"]), float(s["chrome"])) for lab, s in sc.items() if lab in key[iid]},
                "seconds": float(e.get("seconds_spent") or 0),
                "answer_pattern": (
                    tuple(sorted(order.index(lab) for lab in labels if lab in order)),
                    bool(e.get("all_same")),
                    bool(e.get("none_good")),
                ),
            }
    return per_rater, exclusions


# ---------------------------------------------------------------- bootstrap helpers


def site_weights(sites: list[str], seed: int = SEED, iters: int = ITERS) -> np.ndarray:
    """Cluster bootstrap: draw len(sites) sites with replacement; W[i, s] = times site s drawn."""
    rng = np.random.default_rng(seed)
    n = len(sites)
    draws = rng.integers(0, n, size=(iters, n))
    W = np.zeros((iters, n), dtype=np.int32)
    for s in range(n):
        W[:, s] = (draws == s).sum(axis=1)
    return W


def pct(x: np.ndarray) -> list[float]:
    x = x[~np.isnan(x)]
    return [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]


def outcome_ci(page_outcomes: dict[str, str], page_site: dict[str, str]) -> dict:
    """Net and win/loss/tie shares with site-bootstrap percentile intervals."""
    pages = sorted(page_outcomes)
    n = len(pages)
    if n == 0:
        return {"n": 0}
    sites = sorted({page_site[p] for p in pages})
    sidx = {s: i for i, s in enumerate(sites)}
    M = np.zeros((len(sites), 3))  # wins, losses, ties per site
    for p in pages:
        M[sidx[page_site[p]], {"a": 0, "b": 1, "tie": 2}[page_outcomes[p]]] += 1
    W = site_weights(sites)
    B = W @ M
    tot = B.sum(axis=1)
    win, loss, tie = (B[:, k] / tot for k in range(3))
    w, lo, t = (int(M[:, k].sum()) for k in range(3))
    return {
        "n": n,
        "n_sites": len(sites),
        "wins": w,
        "losses": lo,
        "ties": t,
        "net": (w - lo) / n,
        "net_ci95": pct(win - loss),
        "win_share": w / n,
        "win_share_ci95": pct(win),
        "loss_share": lo / n,
        "loss_share_ci95": pct(loss),
        "tie_share": t / n,
        "tie_share_ci95": pct(tie),
    }


def majority(votes: list[str]) -> str:
    c = Counter(votes)
    best = max(c.values())
    winners = [k for k, v in c.items() if v == best]
    return winners[0] if len(winners) == 1 else "tie"


def kripp_alpha(coder_item: dict[str, dict[str, str]]) -> float | None:
    raters = sorted(coder_item)
    items = sorted({i for r in raters for i in coder_item[r]})
    vals = sorted({v for r in raters for v in coder_item[r].values()})
    if len(raters) < 2 or len(vals) < 2:
        return None if len(raters) < 2 else 1.0
    idx = {v: i for i, v in enumerate(vals)}
    C = np.zeros((len(vals), len(vals)))
    for i in items:
        obs = [coder_item[r][i] for r in raters if i in coder_item[r]]
        m = len(obs)
        if m < 2:
            continue
        for x in range(m):
            for y in range(m):
                if x != y:
                    C[idx[obs[x]], idx[obs[y]]] += 1 / (m - 1)
    n = C.sum()
    nc = C.sum(axis=1)
    do = (n - np.trace(C)) / n
    de = (n * n - (nc**2).sum()) / (n * (n - 1))
    return float(1 - do / de) if de > 0 else None


def kappa_from_conf(C: np.ndarray) -> np.ndarray:
    """C: (..., k, k) confusion counts -> Cohen's kappa (nan when undefined)."""
    n = C.sum(axis=(-1, -2))
    po = np.trace(C, axis1=-2, axis2=-1) / n
    pe = (C.sum(axis=-1) * C.sum(axis=-2)).sum(axis=-1) / (n * n)
    with np.errstate(invalid="ignore", divide="ignore"):
        k = (po - pe) / (1 - pe)
    return np.where(np.isclose(pe, 1.0), np.nan, k)


# ---------------------------------------------------------------- main analyses


def page_votes(per_rater, repeat_of, pair, raters=None):
    votes = defaultdict(list)
    for r, items in per_rater.items():
        if raters is not None and r not in raters:
            continue
        for iid, u in items.items():
            if iid in repeat_of:
                continue  # repeats count only toward repeat consistency
            votes[iid].append(u["verdict"][pair])
    return votes


def preference_block(per_rater, repeat_of, item_site, item_group, raters=None):
    out = {}
    for pair in PAIRS:
        pk = f"{pair[0]}_vs_{pair[1]}"
        votes = page_votes(per_rater, repeat_of, pair, raters)
        maj = {i: majority(v) for i, v in votes.items()}
        subsets = {
            "overall": maj,
            "forums_only": {i: v for i, v in maj.items() if item_group[i] == "forum"},
            "without_forums": {i: v for i, v in maj.items() if item_group[i] != "forum"},
        }
        groups = Counter(item_group[i] for i in maj)
        by_group = {
            g: outcome_ci({i: v for i, v in maj.items() if item_group[i] == g}, item_site)
            for g, n in sorted(groups.items())
            if n >= MIN_GROUP
        }
        per_rater_net = {}
        coder = {}
        for r, items in per_rater.items():
            if raters is not None and r not in raters:
                continue
            o = {i: u["verdict"][pair] for i, u in items.items() if i not in repeat_of}
            coder[r] = o
            per_rater_net[r] = outcome_ci(o, item_site)
        out[pk] = {
            **{k: outcome_ci(v, item_site) for k, v in subsets.items()},
            "by_page_group": by_group,
            "page_groups_below_8": {g: n for g, n in sorted(groups.items()) if n < MIN_GROUP},
            "per_rater": per_rater_net,
            "krippendorff_alpha_nominal": kripp_alpha(coder),
            "pages_with_fewer_than_3_ratings": sum(len(v) < 3 for v in votes.values()),
            "ratings_per_page": dict(sorted(Counter(len(v) for v in votes.values()).items())),
        }
    return out


def mean_scores(per_rater, repeat_of, item_site, raters=None):
    rows = []  # (site, tool, content, chrome)
    for r, items in per_rater.items():
        if raters is not None and r not in raters:
            continue
        for iid, u in items.items():
            if iid in repeat_of:
                continue
            for t, (c, ch) in u["scores"].items():
                rows.append((item_site[iid], t, c, ch))
    sites = sorted({x[0] for x in rows})
    sidx = {s: i for i, s in enumerate(sites)}
    W = site_weights(sites)
    out = {}
    for t in TOOLS:
        M = np.zeros((len(sites), 3))
        for s, tt, c, ch in rows:
            if tt == t:
                M[sidx[s]] += (c, ch, 1)
        B = W @ M
        out[t] = {
            "n_ratings": int(M[:, 2].sum()),
            "content": float(M[:, 0].sum() / M[:, 2].sum()),
            "content_ci95": pct(B[:, 0] / B[:, 2]),
            "chrome": float(M[:, 1].sum() / M[:, 2].sum()),
            "chrome_ci95": pct(B[:, 1] / B[:, 2]),
        }
    # differences ChromeRAG minus each baseline, same draws
    return out


def repeat_consistency(per_rater, repeat_of):
    out = {}
    for r, items in per_rater.items():
        groups = defaultdict(list)
        for iid, u in items.items():
            groups[repeat_of.get(iid, iid)].append(u)
        multi = [g for g in groups.values() if len(g) > 1]
        rec = {"n_repeat_pairs": len(multi)}
        for pair in PAIRS:
            agree = sum(g[0]["verdict"][pair] == g[1]["verdict"][pair] for g in multi)
            rec[f"{pair[0]}_vs_{pair[1]}_agree"] = agree
            rec[f"{pair[0]}_vs_{pair[1]}_rate"] = agree / len(multi) if multi else None
        fa = sum(g[0]["full_answer"] == g[1]["full_answer"] for g in multi)
        rec["full_answer_agree"] = fa
        rec["full_answer_rate"] = fa / len(multi) if multi else None
        out[r] = rec
    return out


def care_flags(items, rep):
    flags, detail = [], {}
    times = [u["seconds"] for u in items.values()]
    med = float(np.median(times))
    detail["median_seconds"] = med
    if med < CARE_MIN_MEDIAN_SECONDS:
        flags.append("fast")
    rate = rep["chromerag_vs_trafilatura_rate"]
    detail["repeat_pairs"] = rep["n_repeat_pairs"]
    detail["repeat_agree_rate_focus_pair"] = rate
    if rep["n_repeat_pairs"] >= CARE_MIN_REPEATS and rate < CARE_MIN_REPEAT_AGREE:
        flags.append("inconsistent_repeats")
    detail["repeat_check_full_answer_would_flag"] = bool(
        rep["n_repeat_pairs"] >= CARE_MIN_REPEATS and rep["full_answer_rate"] < CARE_MIN_REPEAT_AGREE
    )
    ans = [u["answer_pattern"] for u in items.values()]
    top = max(Counter(ans).values()) / len(ans)
    detail["top_answer_share_by_position"] = top
    detail["n_rated_items"] = len(ans)
    if len(ans) >= CARE_MIN_ITEMS_SAME and top >= CARE_MAX_SAME_SHARE:
        flags.append("same_answer")
    return flags, detail


def anchor_agreement(per_rater, anchors):
    out = {}
    for pair in PAIRS:
        pk = f"{pair[0]}_vs_{pair[1]}"
        coder = {r: {i: u["verdict"][pair] for i, u in items.items() if i in anchors} for r, items in per_rater.items()}
        agree = tot = 0
        match_major = match_tot = 0
        per_anchor = []
        for a in sorted(anchors):
            vs = [coder[r][a] for r in coder if a in coder[r]]
            for x in range(len(vs)):
                for y in range(x + 1, len(vs)):
                    tot += 1
                    agree += vs[x] == vs[y]
            m = majority(vs)
            match_major += sum(v == m for v in vs)
            match_tot += len(vs)
            per_anchor.append({"n_raters": len(vs), "counts": dict(Counter(vs)), "majority": m})
        out[pk] = {
            "mean_pairwise_agreement": agree / tot,
            "share_of_ratings_matching_anchor_majority": match_major / match_tot,
            "krippendorff_alpha_nominal_anchors": kripp_alpha(coder),
            "per_anchor": per_anchor,  # anonymous order (sorted item ids); no tool labels exposed
        }
    return out


def ai_judges(judges, per_rater, repeat_of, key_doc, item_site):
    page_of = key_doc["page_of"]
    item_of_page = {p: i for i, p in page_of.items() if i not in repeat_of}
    out = {}
    for base in ("trafilatura", "readability"):
        pair = ("chromerag", base)
        votes = page_votes(per_rater, repeat_of, pair)
        human = {i: majority(v) for i, v in votes.items()}
        out[f"chromerag_vs_{base}"] = {}
        for j in JUDGES:
            ai = {}
            for r in judges[j]["judgements"]:
                if r["swapped"] or r["baseline"] != base:
                    continue
                ai[item_of_page[r["id"]]] = {"chromerag": "a", "baseline": "b"}.get(r["winner"], "tie")
            common = sorted(set(ai) & set(human))
            sites = sorted({item_site[i] for i in common})
            sidx = {s: k for k, s in enumerate(sites)}
            lab = {"a": 0, "b": 1, "tie": 2}
            C = np.zeros((len(sites), 3, 3))
            for i in common:
                C[sidx[item_site[i]], lab[human[i]], lab[ai[i]]] += 1
            W = site_weights(sites)
            Bc = np.einsum("is,sjk->ijk", W, C)
            agree_bs = np.trace(Bc, axis1=1, axis2=2) / Bc.sum(axis=(1, 2))
            kap_bs = kappa_from_conf(Bc)
            Ctot = C.sum(axis=0)
            disagreements = Counter((human[i], ai[i]) for i in common if human[i] != ai[i])
            out[f"chromerag_vs_{base}"][j] = {
                "n": len(common),
                "agreement": float(np.trace(Ctot) / Ctot.sum()),
                "agreement_ci95": pct(agree_bs),
                "cohen_kappa": float(kappa_from_conf(Ctot)),
                "cohen_kappa_ci95": pct(kap_bs),
                "kappa_undefined_resamples": int(np.isnan(kap_bs).sum()),
                "confusion_human_rows_ai_cols_[chromerag,baseline,tie]": Ctot.astype(int).tolist(),
                "disagreements_human_to_ai": {f"{h}->{a}": n for (h, a), n in sorted(disagreements.items())},
                "ai_net_preference": outcome_ci(ai, item_site),
                "human_majority_net_same_pages": outcome_ci({i: human[i] for i in common}, item_site),
            }
    return out


# ------------------------------------------------- length analysis (replica of final_page_length_analysis.py)


def _net(rows):
    return sum((r["winner"] == "chromerag") - (r["winner"] == "baseline") for r in rows) / len(rows) if rows else None


def _interval(rows):
    if not rows:
        return None
    rng = random.Random(0)
    vals = sorted(_net(rng.choices(rows, k=len(rows))) for _ in range(LEN_ITERS))
    return [round(vals[int(LEN_ITERS * 0.025)], 3), round(vals[int(LEN_ITERS * 0.975)], 3)]


def _stratum(rows):
    w = sum(r["winner"] == "chromerag" for r in rows)
    lo = sum(r["winner"] == "baseline" for r in rows)
    v = _net(rows)
    return {"pairs": len(rows), "chromerag": w, "baseline": lo, "tie": len(rows) - w - lo,
            "net": None if v is None else round(v, 3), "ci95": _interval(rows)}


def _fit(rows):
    decided = [r for r in rows if r["winner"] != "tie"]
    b0 = b1 = 0.0
    for _ in range(50):
        g0 = g1 = h00 = h01 = h11 = 0.0
        for r in decided:
            x = r["log_ratio"]
            p = 1 / (1 + math.exp(-max(-30.0, min(30.0, b0 + b1 * x))))  # clamp: separation on small samples
            y = float(r["winner"] == "chromerag")
            w = max(p * (1 - p), 1e-6)
            g0 += y - p
            g1 += (y - p) * x
            h00 += w
            h01 += w * x
            h11 += w * x * x
        det = h00 * h11 - h01 * h01
        if det <= 1e-9:
            break
        b0 += (h11 * g0 - h01 * g1) / det
        b1 += (h00 * g1 - h01 * g0) / det
    return 1 / (1 + math.exp(-max(-30.0, min(30.0, b0))))


def _length_block(rows):
    low, high = 1 / SIMILAR_LENGTH_RATIO, SIMILAR_LENGTH_RATIO
    rng = random.Random(0)
    decided = [r for r in rows if r["winner"] != "tie"]
    fits = sorted(_fit(rng.choices(decided, k=len(decided))) for _ in range(LEN_FIT_ITERS))
    return {
        "all": _stratum(rows),
        "similar_length": _stratum([r for r in rows if low <= r["ratio"] <= high]),
        "chromerag_longer": _stratum([r for r in rows if r["ratio"] > high]),
        "baseline_longer": _stratum([r for r in rows if r["ratio"] < low]),
        "chromerag_longer_share": round(sum(r["ratio"] > 1 for r in rows) / len(rows), 3),
        "win_probability_at_equal_length": {
            "estimate": round(_fit(decided), 3),
            "ci95": [round(fits[12], 3), round(fits[487], 3)],
        },
    }


def output_chars(key_doc, bundle) -> dict[str, dict[str, int]] | None:
    """Characters of each labelled output as shown to raters: item id -> label -> length."""
    if "output_chars" in key_doc:
        return key_doc["output_chars"]
    if bundle is not None:
        return {it["item_id"]: {lab: len(t) for lab, t in it["outputs"].items()} for it in bundle["items"]}
    return None


def length_analysis(judges, item_chars, key_doc, per_rater, repeat_of):
    page_of = key_doc["page_of"]
    chars = {}
    for iid, by_label in item_chars.items():
        if iid in repeat_of or iid not in key_doc["key"]:
            continue
        chars[page_of[iid]] = {key_doc["key"][iid][lab]: n for lab, n in by_label.items()}
    out = {"post_hoc_method_replicated": True, "basis": "saved verdicts; chars = len(output text) as shown to raters"}
    for base in ("trafilatura", "readability"):
        out[base] = {}
        for j in JUDGES:
            rows = []
            for r in judges[j]["judgements"]:
                if r["swapped"] or r["baseline"] != base:
                    continue
                o, t = chars[r["id"]]["chromerag"], chars[r["id"]][base]
                rows.append({"winner": r["winner"], "ratio": (o + 1) / (t + 1), "log_ratio": math.log((o + 1) / (t + 1))})
            out[base][j] = _length_block(rows)
        # Exploratory, not in the plan: human majority in the same length strata
        votes = page_votes(per_rater, repeat_of, ("chromerag", base))
        rows = []
        for iid, v in sorted(votes.items()):  # item-id order, independent of rater file names and codes
            m = majority(v)
            o, t = chars[page_of[iid]]["chromerag"], chars[page_of[iid]][base]
            rows.append({"winner": {"a": "chromerag", "b": "baseline"}.get(m, "tie"),
                         "ratio": (o + 1) / (t + 1), "log_ratio": math.log((o + 1) / (t + 1))})
        out[base]["human_majority_exploratory"] = _length_block(rows)
    return out


# ---------------------------------------------------------------- driver


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_input_args(ap)
    ap.add_argument("--out", type=Path, help="Output folder for results.json and results.md")
    ap.add_argument("--export-key", type=Path, help="Write a reduced key for publication and stop")
    args = ap.parse_args(argv)
    if args.export_key:
        key_doc = read_json(args.key)
        export_key(key_doc, read_json(args.bundle) if args.bundle else None,
                   read_json(args.part_plan) if args.part_plan else None, args.export_key)
        return
    if not args.out:
        ap.error("--out is required unless --export-key is given")
    d = prepare(args)
    key_doc, bundle, judges = d["key_doc"], d["bundle"], d["judges"]
    cal, repeat_of, per_rater = d["cal"], d["repeat_of"], d["per_rater"]
    item_site, item_site_field, item_group = d["item_site"], d["item_site_field"], d["item_group"]
    main_items = [i for i in key_doc["key"] if i not in cal and i not in repeat_of]
    assert len(main_items) == 75, len(main_items)

    # Sanity check against the page-level analyzer (evaluators/author/analyze.py)
    v = page_votes(per_rater, repeat_of, ("chromerag", "trafilatura"))
    maj = Counter(majority(x) for x in v.values())
    sanity = {"chromerag_vs_trafilatura_majority": [maj["a"], maj["b"], maj["tie"]],
              "net": (maj["a"] - maj["b"]) / sum(maj.values()), "n": sum(maj.values())}

    rep = repeat_consistency(per_rater, repeat_of)
    care = {r: care_flags(items, rep[r]) for r, items in per_rater.items()}
    all_raters = sorted(per_rater)
    flagged = {r: f for r, (f, _) in care.items() if f}
    kept = [r for r in all_raters if r not in flagged]
    anchors = anchor_ids(key_doc, d["part_plan"])
    item_chars = output_chars(key_doc, bundle)

    report = {
        "plan": "evaluations/2026-11-final/PROTOCOL.md, 'Analysis plan for the human rating set' + amendments",
        "bootstrap": {"unit": "registrable domain (site)", "iterations": ITERS, "seed": SEED,
                      "interval": "95% percentile", "rng": "numpy default_rng"},
        "inputs": {"result_files": d["paths"]},
        "n_main_pages": 75,
        "n_sites_registrable": len({item_site[i] for i in main_items}),
        "n_sites_site_field": len({item_site_field[i] for i in main_items}),
        "page_groups": dict(Counter(item_group[i] for i in main_items)),
        "sanity_vs_existing_report": sanity,
        "exclusions": dict(Counter(e["reason"] for e in d["exclusions"])),
        "valid_ratings_per_rater": {r: {"main": sum(i not in repeat_of for i in it), "repeats": sum(i in repeat_of for i in it)}
                                    for r, it in per_rater.items()},
        "main": preference_block(per_rater, repeat_of, item_site, item_group),
        "mean_scores_main": mean_scores(per_rater, repeat_of, item_site),
        "repeat_consistency": rep,
        "careless_checks": {r: {"flags": f, **dd} for r, (f, dd) in care.items()},
        "sensitivity_without_flagged_raters": {
            "flagged": flagged, "raters_kept": kept,
            "results": preference_block(per_rater, repeat_of, item_site, item_group, set(kept)),
            "mean_scores": mean_scores(per_rater, repeat_of, item_site, set(kept)),
        },
        "check_bootstrap_on_site_field_instead_of_registrable_domain": {
            pk: outcome_ci({i: majority(x) for i, x in page_votes(per_rater, repeat_of, pr).items()}, item_site_field)
            for pr in PAIRS for pk in [f"{pr[0]}_vs_{pr[1]}"]
        },
        "anchor_agreement": anchor_agreement(per_rater, anchors) if anchors else None,
        "human_vs_ai_judges": ai_judges(judges, per_rater, repeat_of, key_doc, item_site),
        "ai_judge_length_analysis": (length_analysis(judges, item_chars, key_doc, per_rater, repeat_of)
                                     if item_chars is not None else None),
    }
    report["readings"] = READINGS
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    (args.out / "results.md").write_text(render_md(report), encoding="utf-8")
    print(json.dumps(sanity))


READINGS = [
    "Outcome per page = plurality of rater verdicts (a / b / tie); equal top counts give a tie. Same rule as "
    "evaluators/author/analyze.py. 'Share of items where raters prefer each' is read as shares of pages by this majority.",
    "Pairwise verdict from the 'best' set: tool in best and other not = win; both or neither, 'all the same', or "
    "'none good' with no best = tie (analyze.py rule).",
    "Exclusions: practice items; skipped items; incomplete items (no choice or a missing score). Repeats count only "
    "toward repeat consistency (amendment 'smaller parts'), so they are left out of votes, alpha AND mean scores "
    "(analyze.py includes repeats in mean scores).",
    "Site = registrable domain of the corpus 'site' field (aws.amazon.com + docs.aws.amazon.com -> amazon.com; "
    "learn.microsoft.com + its Q&A forum -> microsoft.com): 48 clusters. The 50-site 'site field' clustering is "
    "reported as a check.",
    "Site bootstrap: resample sites with replacement, keep all pages of each drawn site; 10,000 iterations, numpy "
    "default_rng(20261120), 95% percentile intervals. Subsets (forums, groups, per rater) resample their own sites "
    "with the same seed.",
    "Mean scores pool every rating (rater x page) and use a ratio estimator under the site bootstrap.",
    "Careless rule as in analyze.py: repeat check uses the ChromeRAG-vs-Trafilatura verdict; median time over all "
    "rated non-practice items incl. repeats; position answer = chosen screen positions + all_same + none_good. "
    "Reading 'verdict' as the full answer flags the same rater.",
    "Pages with fewer than 3 ratings are counted after skips/incomplete exclusions; with raters removed, majority of "
    "2 disagreeing raters is a tie.",
    "AI judges: primary (non-swapped) verdict per page; only ChromeRAG vs Trafilatura and vs Readability were judged. "
    "Agreement and kappa over the 3 outcomes (ChromeRAG / baseline / tie), site bootstrap.",
    "Length analysis replicates poc/final_page_length_analysis.py exactly (chars = len of output text as shown to "
    "raters and judges; ratio 1.1 band; page-level random.Random(0) bootstrap, 2000 / 500 iterations), with the "
    "logistic exponent clamped at +-30 to avoid overflow under separation in small resamples. The human-majority "
    "row in the same strata is exploratory and not in the plan.",
]


def _ci(x, lo, hi, signed=False):
    f = "{:+.2f}" if signed else "{:.2f}"
    return f"{f.format(x)} [{lo:.2f}, {hi:.2f}]"


def _row(label, o):
    return (f"| {label} | {o['n']} | {o['n_sites']} | {_ci(o['net'], *o['net_ci95'], signed=True)} | "
            f"{_ci(o['win_share'], *o['win_share_ci95'])} | {_ci(o['loss_share'], *o['loss_share_ci95'])} | "
            f"{_ci(o['tie_share'], *o['tie_share_ci95'])} |")


def render_md(rep):
    L = ["# Human rating set: planned analysis", "",
         f"Majority verdict per page; 95% percentile intervals from a site bootstrap "
         f"({rep['bootstrap']['iterations']:,} draws, seed {rep['bootstrap']['seed']}, {rep['n_sites_registrable']} sites). "
         "Net = wins minus losses over pages, for the first tool named.", ""]
    hdr = ["| Subset | Pages | Sites | Net | Wins | Losses | Ties |", "|---|---|---|---|---|---|---|"]
    blocks = [("All raters (main result)", rep["main"]),
              ("Without raters flagged as careless (" + ", ".join(
                  f"{r}: {', '.join(f)}" for r, f in rep["sensitivity_without_flagged_raters"]["flagged"].items()) + ")",
               rep["sensitivity_without_flagged_raters"]["results"])]
    for pk in rep["main"]:
        a, b = pk.split("_vs_")
        L += [f"## {a} vs {b}", ""] + hdr
        m = rep["main"][pk]
        L.append(_row("Overall", m["overall"]))
        L.append(_row("Forums only", m["forums_only"]))
        L.append(_row("Without forums", m["without_forums"]))
        for g, o in m["by_page_group"].items():
            L.append(_row(f"Group: {g}", o))
        for r, o in m["per_rater"].items():
            L.append(_row(f"Rater {r}", o))
        for name, blk in blocks[1:]:
            L.append(_row(name + ", overall", blk[pk]["overall"]))
            L.append(_row(name + ", without forums", blk[pk]["without_forums"]))
        line = (f"Krippendorff's alpha (nominal): all raters {m['krippendorff_alpha_nominal']:.2f}; "
                f"without flagged {blocks[1][1][pk]['krippendorff_alpha_nominal']:.2f}.")
        if rep["anchor_agreement"]:
            aa = rep["anchor_agreement"][pk]
            line += (f" Anchor pages: mean pairwise agreement {aa['mean_pairwise_agreement']:.2f}, "
                     f"alpha {aa['krippendorff_alpha_nominal_anchors']:.2f}.")
        L += ["", line, ""]
    L += ["## Mean scores (1 to 5)", "", "| Tool | Ratings | Content | Noise (chrome) |", "|---|---|---|---|"]
    for t, o in rep["mean_scores_main"].items():
        L.append(f"| {t} | {o['n_ratings']} | {_ci(o['content'], *o['content_ci95'])} | {_ci(o['chrome'], *o['chrome_ci95'])} |")
    L += ["", "## Repeat consistency and careless checks", "",
          "| Rater | Repeat pairs | Same verdict (ChromeRAG vs Trafilatura) | Same full answer | Median s/item | Top position share | Flags |",
          "|---|---|---|---|---|---|---|"]
    for r, c in rep["careless_checks"].items():
        rc = rep["repeat_consistency"][r]
        L.append(f"| {r} | {rc['n_repeat_pairs']} | {rc['chromerag_vs_trafilatura_agree']}/{rc['n_repeat_pairs']} | "
                 f"{rc['full_answer_agree']}/{rc['n_repeat_pairs']} | {c['median_seconds']:.0f} | "
                 f"{c['top_answer_share_by_position']:.2f} | {', '.join(c['flags']) or 'none'} |")
    L += ["", "Repeat check applies only with 4 or more repeat pairs.", "",
          "## Human majority vs AI judges", "",
          "| Pair | Judge | Pages | Agreement | Cohen's kappa | AI judge net | Human net, same pages |",
          "|---|---|---|---|---|---|---|"]
    for pk, v in rep["human_vs_ai_judges"].items():
        for j, o in v.items():
            a, h = o["ai_net_preference"], o["human_majority_net_same_pages"]
            L.append(f"| {pk.replace('_vs_', ' vs ')} | {j} | {o['n']} | {_ci(o['agreement'], *o['agreement_ci95'])} | "
                     f"{_ci(o['cohen_kappa'], *o['cohen_kappa_ci95'])} | {_ci(a['net'], *a['net_ci95'], signed=True)} | "
                     f"{_ci(h['net'], *h['net_ci95'], signed=True)} |")
    L += ["", "## AI judge length analysis on these pages (method of the 296-page post hoc analysis; page bootstrap)", "",
          "| Baseline | Judge | Similar length (n, net) | ChromeRAG longer | Baseline longer | Win prob. at equal length |",
          "|---|---|---|---|---|---|"]
    for base, v in (rep["ai_judge_length_analysis"] or {}).items():
        if not isinstance(v, dict):
            continue
        for j, o in v.items():
            cells = []
            for s in ("similar_length", "chromerag_longer", "baseline_longer"):
                x = o[s]
                cells.append(f"{x['pairs']}, {_ci(x['net'], *x['ci95'], signed=True)}")
            w = o["win_probability_at_equal_length"]
            lab = "human majority (exploratory)" if j.startswith("human") else j
            L.append(f"| {base} | {lab} | {' | '.join(cells)} | {_ci(w['estimate'], *w['ci95'])} |")
    m = rep["main"]["chromerag_vs_trafilatura"]
    L += ["", "## Coverage", "",
          f"Pages with fewer than 3 ratings after skips: {m['pages_with_fewer_than_3_ratings']} of 75 "
          f"(ratings per page: {m['ratings_per_page']}); without flagged raters: "
          f"{rep['sensitivity_without_flagged_raters']['results']['chromerag_vs_trafilatura']['pages_with_fewer_than_3_ratings']}.",
          f"Excluded ratings: {rep['exclusions']}.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    main()
