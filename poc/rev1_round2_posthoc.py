"""Post hoc analyses added in the second revision round (2026-11-20), from EXISTING per-page results only.

POST HOC. Written after every result below had been seen, in answer to review comments. Nothing here extracts a
page, scores a test page anew, calls a model or changes the tool, a page, a rating or a planned result.

1. Human set on development domains. Pages of the 75-page human set whose registrable domain (Public Suffix List)
   is the domain of any WCXB page used in development: the strict training pages, the WCXB test split (consulted
   during v0.1.3-v0.1.4 development) or any other WCXB dev/ page. Net preference (ChromeRAG vs Trafilatura and vs
   Readability) on the remaining pages, with the planned site bootstrap (`poc.human_set_posthoc`).
2. WCXB test forum gain by forum platform seen or not seen in the strict training pages. Platform is detected
   mechanically from the saved HTML and the host name (rule in PLATFORM_RULES below, first match wins); a platform
   is "seen" if the same rule finds it on at least one strict training page labelled forum. Per-page F1 comes from
   `results/revision_rows/p03_extra_rows.json` (rows); intervals resample sites as in `poc.revision_rows.site_boot`.
3. Old-code control: F1, without-rate and with-rate differences of 0.1.5 minus the freeze-0.1.3 code with the 0.1.5
   model, read from p03 (no recomputation needed; values copied with their intervals).
4. Exact counts of WCXB test-split use after the freeze-0.1.3 run, from `evaluations/2026-10-v0.1.3/HELD_OUT_LEDGER.csv`.

    PYTHONPATH=src:. python -m poc.rev1_round2_posthoc --wcxb <WCXB release folder with dev/ and test/>

Output: evaluations/2026-11-final/results/posthoc_round2/round2_posthoc.json and .md
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from poc.human_set_posthoc import (
    BASE,
    CORPUS,
    TRAIN_IDS,
    cluster_site,
    load_ratings,
    majority,
    outcome_ci,
    page_votes,
    unblind,
)
from poc.psl import load_psl
from poc.psl import registrable_domain as psl_domain
from poc.revision_rows import site_boot

ROOT = Path(__file__).resolve().parents[1]
KEY = BASE / "human_set_ratings" / "label_key.json"
P03 = BASE / "results" / "revision_rows" / "p03_extra_rows.json"
LEDGER = ROOT / "evaluations" / "2026-10-v0.1.3" / "HELD_OUT_LEDGER.csv"
OUT = BASE / "results" / "posthoc_round2"
PAIRS = (("chromerag", "trafilatura"), ("chromerag", "readability"))

# Stack Exchange network hosts (host rule, applied first).
STACKEXCHANGE_HOSTS = ("stackexchange.com", "stackoverflow.com", "superuser.com", "serverfault.com",
                       "askubuntu.com", "mathoverflow.net", "stackapps.com")
# Markers in the raw HTML, case-sensitive, first match wins.
PLATFORM_RULES = (
    # structural markers (template attributes, asset paths, generator tags) first
    ("discourse", r'name="generator" content="Discourse|data-discourse-'),
    ("xenforo", r'data-xf-init|<html[^>]*id="XF"|<html[^>]*id="XenForo"|XenForo'),
    ("vanilla", r"/applications/vanilla/"),
    ("invision", r"ipsLayout|ips4|Invision Community"),
    ("khoros", r'class="lia-'),
    ("gainsight_insided", r"insided|inSided"),
    ("wpforo", r"wpforo"),
    ("bbpress", r"bbpress|bbPress"),
    # product names that can also occur in page text
    ("vbulletin", r"vBulletin"),
    ("flarum", r"flarum"),
    ("phpbb", r"phpBB|viewtopic\.php"),
    ("nodebb", r"NodeBB|nodebb"),
    ("smf", r"Simple Machines|SMFTooltip"),
    ("mybb", r"MyBB"),
    ("ubbthreads", r"UBB\.threads"),
    ("jforum", r"JForum"),
)


def platform_of(html: str, host: str) -> str:
    h = host.lower()
    if any(h == s or h.endswith("." + s) for s in STACKEXCHANGE_HOSTS):
        return "stackexchange"
    for name, pat in PLATFORM_RULES:
        if re.search(pat, html):
            return name
    return "not_identified"


def read_html(wcxb: Path, split: str, pid: str) -> str:
    return gzip.open(wcxb / split / "html" / f"{pid}.html.gz").read().decode("utf-8", "replace")


def gt_url(wcxb: Path, split: str, pid: str) -> str:
    p = wcxb / split / "ground-truth" / f"{pid}.json"
    return (json.loads(p.read_text(encoding="utf-8")).get("url") or "") if p.is_file() else ""


# ------------------------------------------------- 1. human set on development domains


def human_dev_domains(wcxb: Path, psl) -> dict:
    train_ids = set(json.loads(TRAIN_IDS.read_text(encoding="utf-8")))
    train, test, other_dev = set(), set(), set()
    for split in ("dev", "test"):
        for p in sorted((wcxb / split / "ground-truth").glob("*.json")):
            d = psl_domain(gt_url(wcxb, split, p.stem), psl)
            if not d:
                continue
            if split == "test":
                test.add(d)
            elif p.stem in train_ids:
                train.add(d)
            else:
                other_dev.add(d)

    key_doc = json.loads(KEY.read_text(encoding="utf-8"))
    repeat_of, page_of, cal = key_doc["repeat_of"], key_doc["page_of"], set(key_doc["calibration"])
    meta = {p["id"]: p for p in json.loads(CORPUS.read_text(encoding="utf-8"))}
    item_site, is_forum, dom = {}, {}, {}
    for i in page_of:
        if i in cal or i in repeat_of:
            continue
        m = meta[page_of[i]]
        item_site[i] = cluster_site(m["site"])
        is_forum[i] = m["page_type"] == "forum"
        dom[i] = psl_domain(m["url"], psl)
    assert len(item_site) == 75, len(item_site)

    def cat(i: str) -> str:
        d = dom[i]
        if d in train:
            return "strict_training_domain"
        if d in test:
            return "test_split_domain"
        if d in other_dev:
            return "other_wcxb_dev_domain"
        return "no_wcxb_domain"

    c = {i: cat(i) for i in item_site}
    dev_hit = {i: c[i] != "no_wcxb_domain" for i in item_site}
    per_rater = unblind(load_ratings(), key_doc, cal)
    nets = {}
    for a, b in PAIRS:
        votes = page_votes(per_rater, repeat_of, (a, b))
        maj = {i: majority(v) for i, v in votes.items() if i in item_site}
        nets[f"{a}_vs_{b}"] = {
            "all_pages": outcome_ci(maj, item_site),
            "pages_on_development_domains": outcome_ci({i: v for i, v in maj.items() if dev_hit[i]}, item_site),
            "pages_on_test_split_domains_only": outcome_ci(
                {i: v for i, v in maj.items() if c[i] == "test_split_domain"}, item_site),
            "clean_pages_no_wcxb_domain": outcome_ci({i: v for i, v in maj.items() if not dev_hit[i]}, item_site),
            "clean_pages_without_forums": outcome_ci(
                {i: v for i, v in maj.items() if not dev_hit[i] and not is_forum[i]}, item_site),
            "clean_forum_pages": outcome_ci({i: v for i, v in maj.items() if not dev_hit[i] and is_forum[i]}, item_site),
        }
    by_cat = Counter(c.values())
    cnt_dom = lambda pred: len({dom[i] for i in item_site if pred(i)})  # noqa: E731
    votes_t = page_votes(per_rater, repeat_of, PAIRS[0])
    return {
        "definition": ("development domain = registrable domain (PSL) of any WCXB page: strict training page, WCXB test "
                       "page (test split consulted in v0.1.3-v0.1.4 development) or other WCXB dev/ page; category "
                       "order: training, then test, then other dev"),
        "wcxb_registrable_domains": {"strict_training": len(train), "test_split": len(test),
                                     "other_dev_only_pages": len(other_dev - train)},
        "pages": len(item_site),
        "sites_registrable": len(set(dom.values())),
        "pages_by_category": dict(by_cat),
        "pages_on_development_domains": sum(dev_hit.values()),
        "registrable_domains_on_development_domains": cnt_dom(lambda i: dev_hit[i]),
        "registrable_domains_on_test_split_only": sorted({dom[i] for i in item_site if c[i] == "test_split_domain"}),
        "forum_pages_total": sum(is_forum.values()),
        "forum_pages_on_development_domains": sum(dev_hit[i] and is_forum[i] for i in item_site),
        "forum_pages": sorted(({"page": page_of[i], "domain": dom[i], "category": c[i],
                                "human_majority_vs_trafilatura": majority(votes_t[i])}
                               for i in item_site if is_forum[i]), key=lambda x: x["page"]),
        "nets": nets,
    }


# ------------------------------------------------- 2. forum gain by platform seen in training


def forum_platforms(wcxb: Path) -> dict:
    meta = json.loads((wcxb / "metadata.json").read_text(encoding="utf-8"))["files"]
    train_ids = json.loads(TRAIN_IDS.read_text(encoding="utf-8"))
    seen_forum, seen_any = Counter(), Counter()
    for pid in train_ids:
        m = meta.get(pid, {})
        plat = platform_of(read_html(wcxb, "dev", pid), m.get("domain", ""))
        if plat == "not_identified":
            continue
        seen_any[plat] += 1
        if m.get("page_type") == "forum":
            seen_forum[plat] += 1
    train_forum_total = sum(meta.get(p, {}).get("page_type") == "forum" for p in train_ids)

    p03 = json.loads(P03.read_text(encoding="utf-8"))
    rows = [r for r in p03["rows"] if r["type"] == "forum"]
    pages = []
    for r in rows:
        host = meta[r["id"]]["domain"]
        plat = platform_of(read_html(wcxb, "test", r["id"]), host)
        status = ("not_identified" if plat == "not_identified" else
                  "seen_in_training_forum_pages" if seen_forum[plat] else "not_seen_in_training")
        pages.append({"id": r["id"], "host": host, "site": r["site"], "platform": plat, "status": status,
                      "chromerag_f1": round(r["chromerag_balanced"]["f1"], 4),
                      "trafilatura_f1": round(r["trafilatura"]["f1"], 4)})

    def diff(sel: list[dict]) -> dict:
        if not sel:
            return {"n_pages": 0}
        by = {r["id"]: r for r in rows}
        vals = [by[p["id"]]["chromerag_balanced"]["f1"] - by[p["id"]]["trafilatura"]["f1"] for p in sel]
        out = site_boot(vals, [p["site"] for p in sel])
        out["chromerag_mean_f1"] = sum(by[p["id"]]["chromerag_balanced"]["f1"] for p in sel) / len(sel)
        out["trafilatura_mean_f1"] = sum(by[p["id"]]["trafilatura"]["f1"] for p in sel) / len(sel)
        return {k: (round(v, 4) if isinstance(v, float) else [round(x, 4) for x in v] if isinstance(v, list) else v)
                for k, v in out.items()}

    groups = {
        "all_forum_pages": pages,
        "seen_in_training_forum_pages": [p for p in pages if p["status"] == "seen_in_training_forum_pages"],
        "not_seen_in_training": [p for p in pages if p["status"] == "not_seen_in_training"],
        "not_identified": [p for p in pages if p["status"] == "not_identified"],
        "not_seen_or_not_identified": [p for p in pages if p["status"] != "seen_in_training_forum_pages"],
        "seen_without_stackexchange": [p for p in pages if p["status"] == "seen_in_training_forum_pages"
                                       and p["platform"] != "stackexchange"],
    }
    by_plat = defaultdict(list)
    for p in pages:
        by_plat[p["platform"]].append(p)
    return {
        "rule": ("host on the Stack Exchange network -> stackexchange; else first matching HTML marker in PLATFORM_RULES "
                 "(poc/rev1_round2_posthoc.py); else not_identified. Seen = the rule finds the platform on at least "
                 "one strict training page labelled forum."),
        "rule_history": ("A first version of the rule checked product names that can occur in page text before asset-path "
                         "markers; it classed the one Vanilla training page (which names other forum products in its "
                         "text) as Flarum and one XenForo training page as vBulletin. Under that version 15 test forum "
                         "pages were 'not seen', balanced - Trafilatura +0.111 [-0.014, +0.246]. The rule was reordered "
                         "after seeing this, so the split is sensitive to the rule; both versions are reported."),
        "strict_training_forum_pages": train_forum_total,
        "strict_training_forum_pages_by_platform": dict(seen_forum.most_common()),
        "strict_training_pages_any_type_by_platform": dict(seen_any.most_common()),
        "test_forum_pages_by_platform": {k: len(v) for k, v in sorted(by_plat.items(), key=lambda kv: -len(kv[1]))},
        "balanced_minus_trafilatura_f1": {k: diff(v) for k, v in groups.items()},
        "by_platform": {k: diff(v) for k, v in sorted(by_plat.items(), key=lambda kv: -len(kv[1]))},
        "pages": pages,
    }


# ------------------------------------------------- 3. old-code control, 4. ledger counts


def old_code() -> dict:
    a = json.loads(P03.read_text(encoding="utf-8"))["all_511"]
    pr = a["paired"]["chromerag_balanced_minus_old013_balanced"]
    return {
        "source": "results/revision_rows/p03_extra_rows.json all_511 (paired chromerag_balanced_minus_old013_balanced)",
        "chromerag_0_1_5": {k: round(a["summary"]["chromerag_balanced"][k], 4) for k in ("f1", "without", "with")},
        "freeze_0_1_3_code_with_0_1_5_model": {k: round(a["summary"]["old013_balanced"][k], 4)
                                               for k in ("f1", "without", "with")},
        "difference_0_1_5_minus_old": {k: {"mean": round(v["mean"], 4), "ci95": [round(x, 4) for x in v["ci95"]]}
                                       for k, v in pr.items()},
    }


def ledger_counts() -> dict:
    rows = list(csv.DictReader(LEDGER.open(encoding="utf-8")))
    freeze = 0  # row 1: the freeze-0.1.3 run itself
    assert rows[freeze]["set"] == "wcxb_test" and rows[freeze]["tool_version_or_commit"] == "2d436bb"
    after = list(enumerate(rows, 1))[freeze + 1:]
    full = [i for i, r in after if r["set"] == "wcxb_test" and r["n_pages"] == "511"]
    subset_scoring = [i for i, r in after if r["set"] in ("wcxb_clean", "wcxb_test") and r["judge_model"] == "n/a"
                      and r["n_pages"] != "511"]
    judge_test = [i for i, r in after if r["set"] in ("wcxb_test", "wcxb_clean") and r["judge_model"] != "n/a"
                  and "derived from" not in r["notes"]]
    derived = [i for i, r in after if r["set"] == "wcxb_test" and "derived from" in r["notes"]]
    mixed = [i for i, r in after if "wcxb_clean" in r["set"] and r["set"] != "wcxb_clean" and r["judge_model"] != "n/a"]
    judges = Counter(rows[i - 1]["judge_model"] for i in judge_test + mixed)
    return {
        "source": "evaluations/2026-10-v0.1.3/HELD_OUT_LEDGER.csv (Table S1a row numbers)",
        "freeze_run_row": freeze + 1,
        "full_511_page_f1_scorings_after_freeze_run": {"count": len(full), "rows": full},
        "subset_f1_rescorings_after_freeze_run": {"count": len(subset_scoring), "rows": subset_scoring,
                                                  "note": "row 6 is an aggregate of the freeze run; row 31 accompanies row 32"},
        "ai_judge_runs_on_test_pages_only": {"count": len(judge_test), "rows": judge_test},
        "ai_judge_runs_on_mixed_sets_including_test_pages": {"count": len(mixed), "rows": mixed},
        "derived_subsets_not_separate_runs": derived,
        "ai_judge_runs_including_test_pages_by_judge": dict(judges),
    }


# ------------------------------------------------- report


def fmt(o: dict, d: int = 2) -> str:
    if not o or o.get("n", o.get("n_pages", 0)) == 0:
        return "no pages"
    if "net" in o:
        lo, hi = o["net_ci95"]
        return f"{o['net']:+.{d}f} [{lo:+.{d}f}, {hi:+.{d}f}] ({o['wins']}/{o['losses']}/{o['ties']}; {o['n']} pages, {o['n_sites']} sites)"
    lo, hi = o["ci95"]
    return f"{o['mean']:+.3f} [{lo:+.3f}, {hi:+.3f}] ({o['n_pages']} pages, {o['n_sites']} sites)"


def render_md(rep: dict) -> str:
    h, f, oc, lc = rep["human_set_development_domains"], rep["wcxb_forum_platforms"], rep["old_code_control"], rep["ledger_counts"]
    L = ["# Post hoc analyses, revision round 2 (2026-11-20)", "", rep["status"], "",
         "## 1. Human set pages on WCXB development domains", "", h["definition"] + ".", "",
         f"Pages on development domains: {h['pages_on_development_domains']} of {h['pages']} "
         f"({h['registrable_domains_on_development_domains']} of {h['sites_registrable']} registrable domains); by category: "
         + ", ".join(f"{k} {v}" for k, v in sorted(h["pages_by_category"].items())) + ". "
         f"Forum pages on development domains: {h['forum_pages_on_development_domains']} of {h['forum_pages_total']}. "
         "Test-split-only domains: " + ", ".join(h["registrable_domains_on_test_split_only"]) + ".", "",
         "| Pair | Subset | Net [95% CI] (W/L/T; pages, sites) |", "|---|---|---|"]
    for pair, v in h["nets"].items():
        for k, o in v.items():
            L.append(f"| {pair} | {k} | {fmt(o)} |")
    L += ["", "Forum pages: " + "; ".join(f"{p['page']} {p['domain']} ({p['category']}, majority {p['human_majority_vs_trafilatura']})"
                                       for p in h["forum_pages"]) + ".", "",
          "## 2. WCXB test forum gain by platform seen in training", "", "Rule: " + f["rule"], "",
          f"Strict training forum pages: {f['strict_training_forum_pages']}; by platform: "
          + ", ".join(f"{k} {v}" for k, v in f["strict_training_forum_pages_by_platform"].items()) + ".",
          "Rule history: " + f["rule_history"],
          "Test forum pages by platform: " + ", ".join(f"{k} {v}" for k, v in f["test_forum_pages_by_platform"].items()) + ".", "",
          "| Group | Balanced − Trafilatura F1 [95% CI] |", "|---|---|"]
    L += [f"| {k} | {fmt(o)} |" for k, o in f["balanced_minus_trafilatura_f1"].items()]
    L += ["", "| Platform | Balanced − Trafilatura F1 [95% CI] |", "|---|---|"]
    L += [f"| {k} | {fmt(o)} |" for k, o in f["by_platform"].items()]
    d = oc["difference_0_1_5_minus_old"]
    L += ["", "## 3. Old-code control (0.1.5 minus freeze-0.1.3 code with the 0.1.5 model, 511 pages)", "",
          "; ".join(f"{k} {v['mean']:+.4f} [{v['ci95'][0]:+.4f}, {v['ci95'][1]:+.4f}]" for k, v in d.items())
          + f". Source: {oc['source']}.", "",
          "## 4. WCXB test-split use after the freeze-0.1.3 run (Table S1a)", "",
          f"Full 511-page F1 scorings: {lc['full_511_page_f1_scorings_after_freeze_run']['count']} (rows "
          + ", ".join(map(str, lc["full_511_page_f1_scorings_after_freeze_run"]["rows"])) + "). "
          f"Subset re-scorings: rows {lc['subset_f1_rescorings_after_freeze_run']['rows']}. "
          f"AI-judge runs on test pages only: {lc['ai_judge_runs_on_test_pages_only']['count']} (rows "
          + ", ".join(map(str, lc["ai_judge_runs_on_test_pages_only"]["rows"])) + "); on mixed sets that include test pages: "
          f"{lc['ai_judge_runs_on_mixed_sets_including_test_pages']['count']} (rows "
          + ", ".join(map(str, lc["ai_judge_runs_on_mixed_sets_including_test_pages"]["rows"])) + "); derived subsets, not separate runs: rows "
          + ", ".join(map(str, lc["derived_subsets_not_separate_runs"])) + ". By judge: "
          + ", ".join(f"{k} {v}" for k, v in lc["ai_judge_runs_including_test_pages_by_judge"].items()) + ".", ""]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wcxb", type=Path, default=ROOT / "data" / "wcxb")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    psl = load_psl()
    rep = {
        "status": ("POST HOC (revision round 2, 2026-11-20). Computed from existing per-page results, ratings and saved "
                   "HTML after all results had been seen; no extraction, no new scoring, no model call. Not in any "
                   "analysis plan."),
        "psl_version": psl.version_line,
        "human_set_development_domains": human_dev_domains(args.wcxb, psl),
        "wcxb_forum_platforms": forum_platforms(args.wcxb),
        "old_code_control": old_code(),
        "ledger_counts": ledger_counts(),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "round2_posthoc.json").write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    (args.out / "round2_posthoc.md").write_text(render_md(rep), encoding="utf-8")
    print(render_md(rep))


if __name__ == "__main__":
    main()
