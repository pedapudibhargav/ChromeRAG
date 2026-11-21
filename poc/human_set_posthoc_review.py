"""Post hoc checks on the human rating set added during final review (not planned).

1. Agreement among the three AI judges (GPT, Grok, Gemini) on the 75 main pages: pairwise Cohen's kappa,
   Fleiss' kappa and the number of pages on which all three give the same verdict (ChromeRAG / baseline / tie).
2. Overlap with the project's own earlier page sets: pages whose registrable domain occurs in the WCXB
   development or test split, or in the earlier landing, documentation and fresh-page sets
   (evaluations/2026-10-v0.1.3/evaluation_domains.csv), and the human-majority net without them.
3. The human-majority net without the five pages swapped in by the length rules after the AI judges' totals were
   seen (page ids from results/human_set_analysis/posthoc.json, key history.length_swaps).

Uses only public files (pseudonymized ratings, label key, AI judge files, corpus page list).

    PYTHONPATH=src:. python -m poc.human_set_posthoc_review --out out/human_set_review.json
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from poc import human_set_analysis as H
from poc.psl import registrable_domain

ROOT = Path(__file__).resolve().parents[1]
DOMAINS = ROOT / "evaluations" / "2026-10-v0.1.3" / "evaluation_domains.csv"
CORPUS = ROOT / "evaluations" / "2026-11-final" / "human_set" / "corpus_pages.json"
POSTHOC = ROOT / "evaluations" / "2026-11-final" / "results" / "human_set_analysis" / "posthoc.json"
DEFAULT_OUT = ROOT / "evaluations" / "2026-11-final" / "results" / "human_set_analysis" / "review_posthoc.json"
EARLIER_SETS = (
    "Landing dev companies (53)",
    "Landing heldout companies (47)",
    "Documentation/pricing/article corpus",
    "Fresh companies (51)",
)


def cohen_kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    cats = set(a) | set(b)
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return (po - pe) / (1 - pe)


def fleiss_kappa(rows: list[list[str]]) -> float:
    cats = sorted({c for r in rows for c in r})
    n = len(rows[0])
    m = np.array([[r.count(c) for c in cats] for r in rows], dtype=float)
    p_i = (m * (m - 1)).sum(axis=1) / (n * (n - 1))
    p_j = m.sum(axis=0) / (len(rows) * n)
    pe = float((p_j**2).sum())
    return float((p_i.mean() - pe) / (1 - pe))


def judge_agreement(d: dict) -> dict:
    key_doc, judges, cal, repeat_of = d["key_doc"], d["judges"], d["cal"], d["repeat_of"]
    main_pages = {key_doc["page_of"][i] for i in key_doc["key"] if i not in cal and i not in repeat_of}
    out = {}
    for base in ("trafilatura", "readability"):
        verdicts = {}
        for j in H.JUDGES:
            verdicts[j] = {
                r["id"]: r["winner"]
                for r in judges[j]["judgements"]
                if r["baseline"] == base and not r["swapped"] and r["id"] in main_pages
            }
        pages = sorted(set.intersection(*(set(v) for v in verdicts.values())))
        pair_k = {
            f"{a}-{b}": round(cohen_kappa([verdicts[a][p] for p in pages], [verdicts[b][p] for p in pages]), 4)
            for a, b in itertools.combinations(H.JUDGES, 2)
        }
        out[f"chromerag_vs_{base}"] = {
            "n_pages": len(pages),
            "all_three_same": sum(len({verdicts[j][p] for j in H.JUDGES}) == 1 for p in pages),
            "fleiss_kappa": round(fleiss_kappa([[verdicts[j][p] for j in H.JUDGES] for p in pages]), 4),
            "pairwise_cohen_kappa": pair_k,
            "verdict_counts": {j: dict(Counter(verdicts[j][p] for p in pages)) for j in H.JUDGES},
        }
    return out


def earlier_set_overlap(d: dict) -> dict:
    key_doc, per_rater, repeat_of, item_site = d["key_doc"], d["per_rater"], d["repeat_of"], d["item_site"]
    corpus = {p["id"]: p for p in json.loads(CORPUS.read_text(encoding="utf-8"))}
    sets: dict[str, set[str]] = defaultdict(set)
    with DOMAINS.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sets[row["set"]].add(registrable_domain(row["domain"]) or row["domain"])
    wcxb = sets["WCXB dev"] | sets["WCXB test"]
    earlier = set().union(*(sets[s] for s in EARLIER_SETS))
    out = {"earlier_sets": list(EARLIER_SETS)}
    for a, b in (("chromerag", "trafilatura"), ("chromerag", "readability")):
        votes = H.page_votes(per_rater, repeat_of, (a, b))
        outcome = {i: H.majority(v) for i, v in votes.items()}
        dom = {i: registrable_domain(corpus[key_doc["page_of"][i]]["url"]) for i in outcome}
        no_wcxb = {i: o for i, o in outcome.items() if dom[i] not in wcxb}
        neither = {i: o for i, o in no_wcxb.items() if dom[i] not in earlier}
        res = {}
        for name, sub in (("all", outcome), ("no_wcxb_domain", no_wcxb), ("no_wcxb_or_earlier_set_domain", neither)):
            r = H.outcome_ci(sub, {i: item_site[i] for i in sub})
            res[name] = {k: r[k] for k in ("n", "n_sites", "wins", "losses", "ties", "net", "net_ci95") if k in r}
        res["earlier_set_pages_among_no_wcxb"] = {
            s: sum(1 for i in no_wcxb if dom[i] in sets[s]) for s in EARLIER_SETS
        }
        out[f"{a}_vs_{b}"] = res
    return out


def without_swapped_in(d: dict) -> dict:
    key_doc, per_rater, repeat_of, item_site = d["key_doc"], d["per_rater"], d["repeat_of"], d["item_site"]
    swapped_in = set(json.loads(POSTHOC.read_text(encoding="utf-8"))["history"]["length_swaps"].values())
    out = {"swapped_in_pages": sorted(swapped_in)}
    for a, b in (("chromerag", "trafilatura"), ("chromerag", "readability")):
        votes = H.page_votes(per_rater, repeat_of, (a, b))
        outcome = {i: H.majority(v) for i, v in votes.items()}
        sw = [o for i, o in outcome.items() if key_doc["page_of"][i] in swapped_in]
        rest = {i: o for i, o in outcome.items() if key_doc["page_of"][i] not in swapped_in}
        r = H.outcome_ci(rest, {i: item_site[i] for i in rest})
        out[f"{a}_vs_{b}"] = {
            "swapped_in_outcomes": dict(Counter(sw)),
            "without_swapped_in": {k: r[k] for k in ("n", "n_sites", "wins", "losses", "ties", "net", "net_ci95") if k in r},
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    H.add_input_args(ap)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    d = H.prepare(args)
    rep = {
        "status": "post hoc, added during final review; not in the analysis plan",
        "bootstrap": {"unit": "site", "iterations": H.ITERS, "seed": H.SEED, "interval": "95% percentile"},
        "ai_judge_agreement": judge_agreement(d),
        "earlier_set_overlap": earlier_set_overlap(d),
        "without_length_swapped_in_pages": without_swapped_in(d),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
