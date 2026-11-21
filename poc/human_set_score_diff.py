"""Planned secondary outcome of the human rating set: 1-5 score differences, ChromeRAG minus baseline.

Per page, the mean over raters of (ChromeRAG score - baseline score); site bootstrap as in
poc/human_set_analysis.py (registrable domain, 10,000 draws, seed 20261120). Prints one line per
baseline and score; Table S6 of evaluations/2026-11-final/SUPPLEMENT.md quotes these lines.

  PYTHONPATH=src:. python -m poc.human_set_score_diff [--key KEY.json] [--bundle BUNDLE.json] > score_diff_output.txt
"""

from __future__ import annotations

import argparse

import numpy as np

from poc import human_set_analysis as A


def score_diff(d: dict, base: str, dim: int, keep) -> str:
    rep, site = d["repeat_of"], d["item_site"]
    diffs: dict[str, list[float]] = {}
    for items in d["per_rater"].values():
        for iid, u in items.items():
            if iid in rep or not keep(iid):
                continue
            s = u["scores"]
            if "chromerag" in s and base in s:
                diffs.setdefault(iid, []).append(s["chromerag"][dim] - s[base][dim])
    pages = sorted(diffs)
    vals = np.array([np.mean(diffs[p]) for p in pages])
    sites = sorted({site[p] for p in pages})
    si = {s: k for k, s in enumerate(sites)}
    M = np.zeros((len(sites), 2))
    for p, v in zip(pages, vals):
        M[si[site[p]]] += (v, 1)
    B = A.site_weights(sites) @ M
    est = B[:, 0] / B[:, 1]
    return (f"{vals.mean():+.2f} [{np.percentile(est, 2.5):+.2f}, {np.percentile(est, 97.5):+.2f}] "
            f"n={len(pages)} sites={len(sites)}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    A.add_input_args(ap)
    d = A.prepare(ap.parse_args(argv))
    group = d["item_group"]
    for base in ("trafilatura", "readability"):
        for dim, name in ((0, "content"), (1, "chrome")):
            print(base, name, "all", score_diff(d, base, dim, lambda i: True),
                  "| no forums", score_diff(d, base, dim, lambda i: group[i] != "forum"))


if __name__ == "__main__":
    main()
