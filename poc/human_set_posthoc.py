"""Post hoc robustness and disclosure analyses of the 2026-11 human rating set (revision 1).

Everything here is POST HOC: it was written after all ratings were in and after the planned analysis
(PROTOCOL.md, "Analysis plan for the human rating set") had been run. Nothing here changes the tool, the pages, the
ratings or the planned result. It reuses the planned loading rules and the same site bootstrap
(registrable domain of the corpus `site` field, 48 clusters; 10,000 draws; numpy default_rng(20261120); 95%
percentile intervals).

Inputs
  evaluations/2026-11-final/human_set_ratings/rater-0*.json   pseudonymized ratings (public)
  evaluations/2026-11-final/human_set/corpus_pages.json       page id, URL, site, page group (public)
  --key   label key of the rating bundle (key.json; author-held until released). Only aggregates and page ids
          are written; no item-level label key is written.
  --bundle  bundle_full.json of the rating bundle (author-held); only its practice item ids are read.
  --first-draw  folder with key.json and bundle.json of the first draw (replaced before any rater saw it;
          author-held); only page ids, page groups and the skipped count are read.
  --wcxb  WCXB release folder (dev/ground-truth/*.json carry the page URLs)
  poc/wcxb_strict_train_ids.json, poc/public_suffix_list.dat (registrable domains, as poc/strict_split.py)

Outputs (evaluations/2026-11-final/results/human_set_analysis/)
  posthoc.json, posthoc.md (error_analysis.md beside them is hand-coded from the cases listed in posthoc.json)

  .venv/bin/python -m poc.human_set_posthoc --key <key.json> --bundle <bundle_full.json> \
      --first-draw <first-draw folder> --wcxb data/wcxb
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from poc.psl import load_psl
from poc.psl import registrable_domain as psl_domain

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "evaluations" / "2026-11-final"
RATINGS = BASE / "human_set_ratings"
CORPUS = BASE / "human_set" / "corpus_pages.json"
TRAIN_IDS = ROOT / "poc" / "wcxb_strict_train_ids.json"
OUT = BASE / "results" / "human_set_analysis"

SEED = 20261120
ITERS = 10_000
PAIRS = (("chromerag", "trafilatura"), ("chromerag", "readability"))
ALL_PAIRS = (("chromerag", "trafilatura"), ("chromerag", "readability"), ("trafilatura", "readability"))
FORUM_TARGET_SHARE = 0.10  # forum share of the WCXB test split, rounded


# ------------------------------------------------- loading and unblinding (same rules as the planned analysis


def cluster_site(site: str) -> str:
    """Bootstrap cluster of the planned analysis: registrable domain of the corpus `site` field."""
    host = site.split("/")[0].lower()
    labels = host.split(".")
    multi = {"co.uk", "ac.uk", "gov.uk", "org.uk", "com.au"}
    if len(labels) >= 3 and ".".join(labels[-2:]) in multi:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def pairwise(best: set, a: str, b: str, all_same: bool) -> str:
    if all_same:
        return "tie"
    ha, hb = a in best, b in best
    if ha and not hb:
        return "a"
    if hb and not ha:
        return "b"
    return "tie"


def load_ratings() -> dict[str, dict]:
    out = {}
    for p in sorted(RATINGS.glob("rater-*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        out[d["rater"]] = d
    return out


def unblind(ratings: dict[str, dict], key_doc: dict, calibration: set[str]):
    """Per rater, per non-practice item: pairwise verdicts. Skipped and incomplete items are excluded."""
    key = key_doc["key"]
    per_rater: dict[str, dict[str, dict]] = {}
    for r, res in ratings.items():
        per_rater[r] = {}
        for iid, e in res["items"].items():
            if iid in calibration or iid not in key or e.get("skipped"):
                continue
            sc = e.get("scores") or {}
            chosen = e.get("all_same") or e.get("none_good") or e.get("best")
            if not chosen or not all((sc.get(lab) or {}).get("content") and (sc.get(lab) or {}).get("chrome") for lab in key[iid]):
                continue
            best_tools = {key[iid][lab] for lab in (e.get("best") or []) if lab in key[iid]}
            v = {}
            for a, b in ALL_PAIRS:
                x = pairwise(best_tools, a, b, bool(e.get("all_same")))
                if e.get("none_good") and not best_tools:
                    x = "tie"
                v[(a, b)] = x
            per_rater[r][iid] = v
    return per_rater


def majority(votes: list[str]) -> str:
    c = Counter(votes)
    top = max(c.values())
    winners = [k for k, v in c.items() if v == top]
    return winners[0] if len(winners) == 1 else "tie"


def page_votes(per_rater, repeat_of, pair, raters=None) -> dict[str, list[str]]:
    votes = defaultdict(list)
    for r, items in per_rater.items():
        if raters is not None and r not in raters:
            continue
        for iid, v in items.items():
            if iid in repeat_of:
                continue
            votes[iid].append(v[pair])
    return votes


# ------------------------------------------------- bootstrap


def site_weights(n_sites: int, seed: int = SEED, iters: int = ITERS) -> np.ndarray:
    """Same draws as the planned analysis: W[i, s] = times site s drawn in iteration i."""
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, n_sites, size=(iters, n_sites))
    W = np.zeros((iters, n_sites), dtype=np.int32)
    for s in range(n_sites):
        W[:, s] = (draws == s).sum(axis=1)
    return W


def pct(x: np.ndarray) -> list[float]:
    x = x[~np.isnan(x)]
    return [round(float(np.percentile(x, 2.5)), 4), round(float(np.percentile(x, 97.5)), 4)]


def outcome_ci(outcomes: dict[str, str], item_site: dict[str, str]) -> dict:
    pages = sorted(outcomes)
    if not pages:
        return {"n": 0}
    sites = sorted({item_site[p] for p in pages})
    sidx = {s: i for i, s in enumerate(sites)}
    M = np.zeros((len(sites), 3))
    for p in pages:
        M[sidx[item_site[p]], {"a": 0, "b": 1, "tie": 2}[outcomes[p]]] += 1
    B = site_weights(len(sites)) @ M
    tot = B.sum(axis=1)
    w, lo, t = (int(M[:, k].sum()) for k in range(3))
    return {"n": len(pages), "n_sites": len(sites), "wins": w, "losses": lo, "ties": t,
            "net": round((w - lo) / len(pages), 4), "net_ci95": pct((B[:, 0] - B[:, 1]) / tot)}


def sign_test_two_sided(wins: int, losses: int) -> float:
    """Exact two-sided binomial sign test, p = min(1, 2 * P(X <= min(w, l))), X ~ Bin(w + l, 1/2)."""
    n, k = wins + losses, min(wins, losses)
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def forum_reweighted(outcomes: dict[str, str], item_site: dict[str, str], is_forum: dict[str, bool],
                     share: float = FORUM_TARGET_SHARE) -> dict:
    """Net = share * (net over forum pages) + (1 - share) * (net over other pages).

    Equivalently: every forum page gets weight share / n_forum and every other page (1 - share) / n_other, so forum
    pages carry `share` of the total weight. Under the site bootstrap both nets are recomputed on the pages of the
    drawn sites; draws without any forum page (or without any other page) are dropped and counted.
    """
    pages = sorted(outcomes)
    sites = sorted({item_site[p] for p in pages})
    sidx = {s: i for i, s in enumerate(sites)}
    M = np.zeros((len(sites), 2, 3))  # site x (other, forum) x (win, loss, tie)
    for p in pages:
        M[sidx[item_site[p]], int(is_forum[p]), {"a": 0, "b": 1, "tie": 2}[outcomes[p]]] += 1
    W = site_weights(len(sites))
    B = np.einsum("is,sgk->igk", W, M)
    with np.errstate(invalid="ignore", divide="ignore"):
        net_g = (B[:, :, 0] - B[:, :, 1]) / B.sum(axis=2)
    bs = share * net_g[:, 1] + (1 - share) * net_g[:, 0]
    tot = M.sum(axis=0)
    point_g = (tot[:, 0] - tot[:, 1]) / tot.sum(axis=1)
    return {
        "rule": (f"net = {share:.2f} x net(forum pages) + {1 - share:.2f} x net(other pages); each forum page weighs "
                 f"{share:.2f}/n_forum and each other page {1 - share:.2f}/n_other"),
        "forum_share_target": share,
        "forum_pages": int(tot[1].sum()), "other_pages": int(tot[0].sum()),
        "net_forum_pages": round(float(point_g[1]), 4), "net_other_pages": round(float(point_g[0]), 4),
        "net": round(float(share * point_g[1] + (1 - share) * point_g[0]), 4),
        "net_ci95": pct(bs),
        "bootstrap_draws_dropped_no_forum_or_no_other": int(np.isnan(bs).sum()),
    }


# ------------------------------------------------- analyses


def robustness(per_rater, repeat_of, item_site, is_forum, pair, drop_labels) -> dict:
    votes = page_votes(per_rater, repeat_of, pair)
    maj = {i: majority(v) for i, v in votes.items()}
    c = Counter(maj.values())
    pooled = Counter(x for v in votes.values() for x in v)
    loro = {}
    for label, r in drop_labels:
        keep = set(per_rater) - {r}
        vv = page_votes(per_rater, repeat_of, pair, keep)
        loro[label] = {**outcome_ci({i: majority(v) for i, v in vv.items()}, item_site),
                       "pages_with_2_ratings_left": sum(len(v) == 2 for v in vv.values())}
    return {
        "primary_majority": outcome_ci(maj, item_site),
        "a_ties_excluded": {
            "decided_pages": c["a"] + c["b"], "wins": c["a"], "losses": c["b"],
            "win_share_of_decided": round(c["a"] / (c["a"] + c["b"]), 4),
            "sign_test_two_sided_p": round(sign_test_two_sided(c["a"], c["b"]), 6),
            "test": "exact binomial sign test on page majorities, ties dropped, H0 p = 0.5",
        },
        "b_opposite_verdicts": {
            "pages_with_at_least_one_vote_each_way": sum(("a" in v and "b" in v) for v in votes.values()),
            "pages": len(votes),
            "pages_all_raters_same_verdict": sum(len(set(v)) == 1 for v in votes.values()),
            "pages_win_and_tie_only": sum(set(v) == {"a", "tie"} for v in votes.values()),
            "pages_loss_and_tie_only": sum(set(v) == {"b", "tie"} for v in votes.values()),
            "pooled_ratings_win_loss_tie": [pooled["a"], pooled["b"], pooled["tie"]],
        },
        "c_leave_one_rater_out": loro,
        "d_forums_reweighted": forum_reweighted(maj, item_site, is_forum),
    }


def train_domains(wcxb: Path, psl) -> tuple[set[str], set[str], int]:
    ids = json.loads(TRAIN_IDS.read_text(encoding="utf-8"))
    doms, urls, missing = set(), set(), 0
    for pid in ids:
        p = wcxb / "dev" / "ground-truth" / f"{pid}.json"
        if not p.is_file():
            missing += 1
            continue
        url = json.loads(p.read_text(encoding="utf-8")).get("url", "") or ""
        if url:
            urls.add(url.rstrip("/").split("://", 1)[-1].removeprefix("www.").lower())
            d = psl_domain(url, psl)
            if d:
                doms.add(d)
    return doms, urls, missing


def overlap(per_rater, repeat_of, item_site, is_forum, item_page, meta, wcxb: Path) -> dict:
    psl = load_psl()
    doms, urls, missing = train_domains(wcxb, psl)
    items = sorted(i for i in item_site if i not in repeat_of)
    dom = {i: psl_domain(meta[item_page[i]]["url"], psl) for i in items}
    norm = {i: meta[item_page[i]]["url"].rstrip("/").split("://", 1)[-1].removeprefix("www.").lower() for i in items}
    hit = {i: dom[i] in doms for i in items}
    out = {
        "psl_version": psl.version_line,
        "strict_training_pages": len(json.loads(TRAIN_IDS.read_text(encoding="utf-8"))),
        "strict_training_pages_missing_ground_truth": missing,
        "strict_training_registrable_domains": len(doms),
        "rated_pages": len(items),
        "rated_pages_on_training_domain": sum(hit.values()),
        "rated_registrable_domains_on_training_domain": len({dom[i] for i in items if hit[i]}),
        "rated_registrable_domains_total": len(set(dom.values())),
        "bootstrap_sites_touched": len({item_site[i] for i in items if hit[i]}),
        "forum_pages_on_training_domain": sum(hit[i] and is_forum[i] for i in items),
        "forum_pages_total": sum(is_forum[i] for i in items),
        "exact_url_matches_with_training": sum(norm[i] in urls for i in items),
        "overlap_level": "registrable domain only; no rated URL is a training URL" if not any(norm[i] in urls for i in items)
        else "registrable domain; some URLs also match",
        "pages": sorted(({"page": item_page[i], "domain": dom[i], "group": meta[item_page[i]]["page_type"]}
                         for i in items if hit[i]), key=lambda x: (x["domain"], x["page"])),
        "nets": {},
    }
    for pair in PAIRS:
        votes = page_votes(per_rater, repeat_of, pair)
        maj = {i: majority(v) for i, v in votes.items()}
        out["nets"][f"{pair[0]}_vs_{pair[1]}"] = {
            "without_overlap": outcome_ci({i: v for i, v in maj.items() if not hit[i]}, item_site),
            "with_overlap": outcome_ci({i: v for i, v in maj.items() if hit[i]}, item_site),
            "without_overlap_without_forums": outcome_ci(
                {i: v for i, v in maj.items() if not hit[i] and not is_forum[i]}, item_site),
        }
    return out



# ------------------------------------------------- history of the set (AI judge totals before and after changes)

JUDGES = ("gpt", "grok", "gemini")
JUDGE_DIR = BASE / "results" / "human_set_ai_judges"
NEW_PAGES_JUDGE = BASE / "results" / "new_pages" / "new_pages_judge.json"
REMOVED_BY_RULE = BASE / "human_set" / "removed_by_rule.json"


def _totals(rows, pages=None) -> dict:
    out = {}
    for base in ("trafilatura", "readability"):
        c = Counter(r["winner"] for r in rows
                    if not r["swapped"] and r["baseline"] == base and (pages is None or r["id"] in pages))
        out[f"chromerag_vs_{base}"] = [c["chromerag"], c["baseline"], c["tie"]]
    return out


def history(first_dir: Path) -> dict:
    """AI judge totals (primary, non-swapped verdict; [ChromeRAG, baseline, tie]) on each version of the set."""
    fk = json.loads((first_dir / "key.json").read_text(encoding="utf-8"))
    fb = json.loads((first_dir / "bundle.json").read_text(encoding="utf-8"))
    fcal = {it["item_id"] for it in fb["calibration"]}
    first_main = {i for i in fk["key"] if i not in fk["repeat_of"] and i not in fcal}
    np_judge = json.loads(NEW_PAGES_JUDGE.read_text(encoding="utf-8"))["judgements"]
    swaps = {r["id"]: r["replaced_by"] for r in json.loads(REMOVED_BY_RULE.read_text(encoding="utf-8")) if r["replaced_by"]}
    added = set(swaps.values())
    judges = {}
    for j in JUDGES:
        prog = [json.loads(line) for line in (JUDGE_DIR / f"{j}.progress.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        final = json.loads((JUDGE_DIR / f"{j}.json").read_text(encoding="utf-8"))["judgements"]
        judges[j] = {
            "set_before_length_swaps": _totals([r for r in prog if r["id"] not in added]),
            "five_pages_swapped_out": _totals(prog, set(swaps)),
            "five_pages_swapped_in": _totals(final, added),
            "final_set": _totals(final),
        }
    return {
        "first_draw": {
            "seed": fk["seed"], "main_pages": len(first_main),
            "page_groups": dict(sorted(Counter(fk["page_types"][i] for i in first_main).items())),
            "candidates_skipped_for_short_tool_output": len(fk.get("skipped_short", [])),
            "gpt_on_296_pages": _totals(np_judge),
            "gpt_on_first_draw_pages_posthoc": _totals(np_judge, first_main),
        },
        "length_swaps": swaps,
        "ai_judges_on_approved_site_set": judges,
    }


# ------------------------------------------------- cases for the qualitative error analysis


def error_cases(per_rater, repeat_of, item_page, meta) -> dict:
    """Pages for the descriptive error analysis. Contrast wins: 15 drawn with random.Random(SEED) from the sorted
    page ids where the majority preferred ChromeRAG over Trafilatura, fixed before any page was read."""
    maj, counts = {}, {}
    for a, b in PAIRS:
        votes = page_votes(per_rater, repeat_of, (a, b))
        maj[b] = {item_page[i]: majority(v) for i, v in votes.items()}
        counts[b] = {item_page[i]: dict(Counter(v)) for i, v in votes.items()}

    def row(p):
        return {"page": p, "site": meta[p]["site"], "group": meta[p]["page_type"],
                "votes_vs_trafilatura": counts["trafilatura"][p], "votes_vs_readability": counts["readability"][p],
                "majority_vs_trafilatura": maj["trafilatura"][p], "majority_vs_readability": maj["readability"][p]}

    lost_t = sorted(p for p, v in maj["trafilatura"].items() if v == "b")
    lost_r = sorted(p for p, v in maj["readability"].items() if v == "b")
    won_t = sorted(p for p, v in maj["trafilatura"].items() if v == "a")
    contrast = sorted(random.Random(SEED).sample(won_t, 15))
    return {
        "vote_labels": "a = ChromeRAG preferred, b = baseline preferred, tie",
        "lost_to_trafilatura": [row(p) for p in lost_t],
        "lost_to_readability": [row(p) for p in lost_r],
        "contrast_wins_vs_trafilatura": [row(p) for p in contrast],
    }


# ------------------------------------------------- report


def _ci(o: dict) -> str:
    return f"{o['net']:+.2f} [{o['net_ci95'][0]:+.2f}, {o['net_ci95'][1]:+.2f}]"


def _p(p: float) -> str:
    return f"{p:.4f}" if p >= 0.0001 else f"{p:.1e}"


def render_md(rep: dict) -> str:
    L = ["# Human rating set: post hoc robustness and disclosure analyses", "",
         "**Post hoc.** Everything on this page was computed after all ratings were in and after the planned "
         "analysis had been run. None of it is in the analysis plan (PROTOCOL.md). It changes no rating, page, "
         "setting or tool. The planned result stays the primary result.", "",
         f"Unit: the plurality verdict of the raters per page (75 pages; equal top counts give a tie). Net = (pages "
         f"where the first tool wins minus pages where it loses) / pages. Intervals: 95% percentile, site bootstrap "
         f"(registrable domain of the corpus `site` field, {rep['n_sites']} sites; {ITERS:,} draws; seed {SEED}), "
         f"as in the planned analysis. Generated by `poc/human_set_posthoc.py`.", ""]
    for pk, b in rep["robustness"].items():
        a, c = pk.split("_vs_")
        m, te, ov, fr = b["primary_majority"], b["a_ties_excluded"], b["b_opposite_verdicts"], b["d_forums_reweighted"]
        L += [f"## {a} vs {c}", "",
              f"Primary (planned, for reference): {m['wins']} wins, {m['losses']} losses, {m['ties']} ties; "
              f"net {_ci(m)}.", "",
              "| Post hoc check | Result |", "|---|---|",
              f"| (a) Ties excluded | {te['wins']} of {te['decided_pages']} decided pages ({te['win_share_of_decided']:.0%}); "
              f"exact two-sided sign test p = {_p(te['sign_test_two_sided_p'])} |",
              f"| (b) Pages with opposite verdicts (at least one rater for each tool) | "
              f"{ov['pages_with_at_least_one_vote_each_way']} of {ov['pages']} |",
              f"| (b) Pages where all raters agreed / only win and tie / only loss and tie | "
              f"{ov['pages_all_raters_same_verdict']} / {ov['pages_win_and_tie_only']} / {ov['pages_loss_and_tie_only']} |",
              f"| (b) Pooled single ratings, win / loss / tie | {' / '.join(map(str, ov['pooled_ratings_win_loss_tie']))} |"]
        for lab, o in b["c_leave_one_rater_out"].items():
            L.append(f"| (c) Leave one rater out: {lab} | net {_ci(o)} ({o['wins']}/{o['losses']}/{o['ties']}; "
                     f"{o['pages_with_2_ratings_left']} pages left with 2 ratings) |")
        L.append(f"| (d) Forums reweighted to {fr['forum_share_target']:.0%} of the weight | net {_ci(fr)} "
                 f"(forum net {fr['net_forum_pages']:+.2f} on {fr['forum_pages']} pages, other net "
                 f"{fr['net_other_pages']:+.2f} on {fr['other_pages']} pages) |")
        L += ["", f"Rule for (d): {fr['rule']}. In each bootstrap draw both nets are recomputed on the pages of the "
              f"drawn sites; {fr['bootstrap_draws_dropped_no_forum_or_no_other']} of {ITERS:,} draws had no forum page "
              "and were dropped. The 10% is the forum share of the WCXB test split (51 of 511 pages).", ""]
    L += ["Leave-one-rater-out labels: rater codes were put in a fixed random order (seed "
          f"{SEED}) and numbered 1 to 5; the numbers are not the published codes. With a rater removed, the "
          "plurality of two disagreeing raters is a tie.", ""]
    o = rep["training_domain_overlap"]
    L += ["## Rated pages on registrable domains of the strict training set", "",
          f"Registrable domain = eTLD+1 under the Public Suffix List in `poc/public_suffix_list.dat` "
          f"({o['psl_version']}), as in `poc/strict_split.py`. Training domains: the URLs of the "
          f"{o['strict_training_pages']} WCXB dev pages in `poc/wcxb_strict_train_ids.json` "
          f"({o['strict_training_registrable_domains']} registrable domains).", "",
          f"- **{o['rated_pages_on_training_domain']} of {o['rated_pages']}** rated pages share a registrable domain "
          f"with at least one strict training page: {o['rated_registrable_domains_on_training_domain']} of the "
          f"{o['rated_registrable_domains_total']} registrable domains of the rated pages "
          f"({o['bootstrap_sites_touched']} of {rep['n_sites']} bootstrap sites); "
          f"{o['forum_pages_on_training_domain']} of the {o['forum_pages_total']} forum pages.",
          f"- Exact URL matches with training pages: {o['exact_url_matches_with_training']}. The overlap is at the "
          "domain level only: the rated pages are different pages from the training pages.",
          "- Domains: " + ", ".join(f"{d} ({n})" for d, n in sorted(Counter(p['domain'] for p in o['pages']).items())) + ".",
          "", "| Pair | Pages without overlap | Pages with overlap | Without overlap and without forums |",
          "|---|---|---|---|"]
    for pk, v in o["nets"].items():
        cells = [f"{x['n']} pages, {x['n_sites']} sites: {_ci(x)} ({x['wins']}/{x['losses']}/{x['ties']})"
                 for x in (v["without_overlap"], v["with_overlap"], v["without_overlap_without_forums"])]
        L.append(f"| {pk.replace('_vs_', ' vs ')} | " + " | ".join(cells) + " |")
    L += ["", "Cells: net [95% site-bootstrap interval] (wins/losses/ties). Subsets resample their own sites with the "
          "same seed.", ""]
    h = rep["history"]
    fd, aj = h["first_draw"], h["ai_judges_on_approved_site_set"]

    def t(x):
        return "-".join(map(str, x))

    L += ["## History of the human set", "",
          "Factual record from PROTOCOL.md, its git history and the author's status notes. Times are US Pacific. "
          "AI judge totals are primary (non-swapped) verdicts, ChromeRAG-baseline-tie; those marked post hoc were "
          "computed for this report.", "",
          f"**First draw (2026-11-01).** The set fixed in the protocol section \"Human rating set (2026-11-01)\" "
          f"(commit `ecc643d`, 22:19) was drawn by `evaluators/author/build_bundle.py` with seed {fd['seed']} from the "
          f"296 new pages: {fd['main_pages']} main pages ({', '.join(f'{g} {n}' for g, n in sorted(fd['page_groups'].items(), key=lambda x: (-x[1], x[0])))}), "
          f"5 repeats and 5 practice pages. In drawing, the builder skipped candidate pages whose tool output was short "
          f"({fd['candidates_skipped_for_short_tool_output']} skipped), a selection on tool output that the later set "
          f"dropped. Before the draw the GPT judge had already judged all 296 pages (results commit `01c16f3`, 21:27), "
          f"and those totals had been seen: {t(fd['gpt_on_296_pages']['chromerag_vs_trafilatura'])} against "
          f"Trafilatura, {t(fd['gpt_on_296_pages']['chromerag_vs_readability'])} against Readability. Its verdicts "
          f"on the drawn pages therefore existed; no record shows that totals for the drawn subset were computed at the "
          f"time. Post hoc, on the {fd['main_pages']} first-draw pages: "
          f"{t(fd['gpt_on_first_draw_pages_posthoc']['chromerag_vs_trafilatura'])} against Trafilatura, "
          f"{t(fd['gpt_on_first_draw_pages_posthoc']['chromerag_vs_readability'])} against Readability.", "",
          "**Why it was replaced (2026-11-02).** The first page collection had reached a site flagged as unsafe, and "
          "the set still held pages that could load live images. The amendment \"offline pages and safety filter\" "
          "(commit `4e5ea40`, 11:48) stripped links, images and remote styles from saved pages and added a mechanical "
          "safety filter that removed 8 of the 296 pages (2 of them in the first draw); it records a redraw from the "
          "remaining 288. The same day the amendment \"new human rating set from approved sites\" (commit `0683b94`, "
          "17:22) replaced the set altogether. No rater received the first draw or the redraw; the first draw's "
          "package is kept privately, unsent. The 296-page results are reported unchanged elsewhere.", "",
          "**Approved sites and swaps (2026-11-02).** `human_set/sites.json` lists 85 sites in 14 named groups, approved "
          "by the author by name before any contact; `approved_addresses.json` holds the 507 addresses that passed two "
          "text-only reviews (15 removed by the second). Collection gave 145 pages from 51 sites, 99 after the limit of "
          "2 per site (`c4aced6`, 17:46). Before any rating, pages were removed with recorded reasons: 6 after review "
          "for work safety or usability (`00d2c8c`, 17:53); forums added at a share fixed in advance at 10 of 75, "
          "knowing forums suit ChromeRAG (`78cc507`, 17:59; `5405840`, 18:15); 2 automated forum posts (`4d685af`, "
          "18:19); 2 terms pages (`70b7d93`, 18:39). The bundle seed was replaced after these removals; each seed-file "
          "hash is in PROTOCOL.md. The AI judge plan was fixed at `4f5ce3a` (18:52), and the three AI judges then "
          "judged the drawn set, whose totals were seen. Two tool-blind rules (all three tools under 80 words; page "
          "text over 8,000 words) were then adopted (`850cf98`, 19:14) and 5 drawn pages were swapped one for one ("
          + ", ".join(f"{a.removeprefix('human-')} to {b.removeprefix('human-')}" for a, b in sorted(h["length_swaps"].items()))
          + "; `5ebf4fb`). The 5 new pages were judged and all AI verdicts frozen (`3b4f43d`, 19:21); the verdicts on "
          "the 5 swapped-out pages remain in the `*.progress.jsonl` files. Rating began on 2026-11-04, after the "
          "remaining app and analysis amendments (2026-11-02 and 2026-11-03).", "",
          "| Judge | Pair | Set before length swaps | 5 pages swapped out | 5 pages swapped in | Final set |",
          "|---|---|---|---|---|---|"]
    for j, v in aj.items():
        for pk in ("chromerag_vs_trafilatura", "chromerag_vs_readability"):
            L.append(f"| {j} | {pk.replace('_vs_', ' vs ')} | {t(v['set_before_length_swaps'][pk])} | "
                     f"{t(v['five_pages_swapped_out'][pk])} | {t(v['five_pages_swapped_in'][pk])} | {t(v['final_set'][pk])} |")
    L += [""]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", type=Path, required=True, help="key.json of the rating bundle")
    ap.add_argument("--bundle", type=Path, required=True, help="bundle_full.json (practice item ids)")
    ap.add_argument("--first-draw", type=Path, required=True,
                    help="folder with key.json and bundle.json of the first (replaced, never sent) draw")
    ap.add_argument("--wcxb", type=Path, default=ROOT / "data" / "wcxb")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    key_doc = json.loads(args.key.read_text(encoding="utf-8"))
    repeat_of = key_doc["repeat_of"]
    page_of = key_doc["page_of"]
    meta = {p["id"]: p for p in json.loads(CORPUS.read_text(encoding="utf-8"))}
    calibration = {it["item_id"] for it in json.loads(args.bundle.read_text(encoding="utf-8"))["calibration"]}
    ratings = load_ratings()

    item_site, is_forum, item_page = {}, {}, {}
    for i in page_of:
        if i in calibration:
            continue
        base = repeat_of.get(i, i)
        m = meta[page_of[base]]
        assert m["page_type"] == key_doc["page_types"][base]
        item_site[i] = cluster_site(m["site"])
        is_forum[i] = m["page_type"] == "forum"
        item_page[i] = page_of[base]
    main_items = [i for i in item_site if i not in repeat_of]
    assert len(main_items) == 75, len(main_items)

    per_rater = unblind(ratings, key_doc, calibration)
    order = sorted(per_rater)
    random.Random(SEED).shuffle(order)
    drop_labels = [(f"drop rater {k + 1}", r) for k, r in enumerate(order)]

    rep = {
        "status": "post hoc; not in the analysis plan; computed after all ratings and after the planned analysis",
        "bootstrap": {"unit": "registrable domain of the corpus site field", "iterations": ITERS, "seed": SEED,
                      "interval": "95% percentile", "rng": "numpy default_rng"},
        "n_pages": len(main_items),
        "n_sites": len({item_site[i] for i in main_items}),
        "n_raters": len(per_rater),
        "robustness": {f"{a}_vs_{b}": robustness(per_rater, repeat_of, item_site, is_forum, (a, b), drop_labels)
                       for a, b in PAIRS},
        "training_domain_overlap": overlap(per_rater, repeat_of, item_site, is_forum, item_page, meta, args.wcxb),
        "history": history(args.first_draw),
        "error_analysis_cases": error_cases(per_rater, repeat_of, item_page, meta),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "posthoc.json").write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    (args.out / "posthoc.md").write_text(render_md(rep), encoding="utf-8")
    p = rep["robustness"]["chromerag_vs_trafilatura"]["primary_majority"]
    print(json.dumps({"chromerag_vs_trafilatura": [p["wins"], p["losses"], p["ties"], p["net"], p["net_ci95"]]}))


if __name__ == "__main__":
    main()
