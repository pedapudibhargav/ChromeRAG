"""Aggregate the Claude sub-agent judgements (poc/claude_judge_build.py) into win rates by page type.

  python -m poc.claude_judge_aggregate --set wcxb_clean --dir /tmp/cr/judge --out evaluations/.../FINAL/claude_judge_v014d_wcxb_clean.json
"""

from __future__ import annotations

import argparse
import glob
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


def load(dir_: str, name: str):
    key = json.loads((Path(dir_) / "key" / f"{name}.json").read_text())
    rows = []
    for f in sorted(glob.glob(f"{dir_}/results/{name}_[0-9]*.json")):
        for r in json.loads(Path(f).read_text()):
            k = key.get(r["pid"])
            if not k:
                continue
            better = str(r.get("better", "tie")).upper()
            winner = "tie" if better not in ("A", "B") else ("chromerag" if k[better] == "chromerag" else "trafilatura")
            ours = "A" if k["A"] == "chromerag" else "B"
            theirs = "B" if ours == "A" else "A"
            rows.append({"pid": r["pid"], "type": k["type"], "url": k["url"], "winner": winner,
                         "content_ours": r.get(f"content_{ours}"), "content_traf": r.get(f"content_{theirs}"),
                         "chrome_ours": r.get(f"chrome_{ours}"), "chrome_traf": r.get(f"chrome_{theirs}"), "reason": r.get("reason", "")})
    return rows


def summarize(rows, rng=np.random.default_rng(0)):
    out = {}
    types = sorted({r["type"] for r in rows})
    for t in [*types, "ALL"]:
        rs = rows if t == "ALL" else [r for r in rows if r["type"] == t]
        if not rs:
            continue
        w = sum(r["winner"] == "chromerag" for r in rs)
        l = sum(r["winner"] == "trafilatura" for r in rs)
        score = np.array([1 if r["winner"] == "chromerag" else -1 if r["winner"] == "trafilatura" else 0 for r in rs], float)
        bs = [score[rng.integers(0, len(score), len(score))].mean() for _ in range(4000)]
        mean = lambda k: float(np.mean([r[k] for r in rs if isinstance(r[k], (int, float))]))
        out[t] = {"n": len(rs), "wins": w, "losses": l, "ties": len(rs) - w - l, "net": float(score.mean()),
                  "net_ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
                  "content_ours": mean("content_ours"), "content_traf": mean("content_traf"),
                  "chrome_ours": mean("chrome_ours"), "chrome_traf": mean("chrome_traf")}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True)
    ap.add_argument("--dir", default="/tmp/cr/judge")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    rows = load(a.dir, a.set)
    s = summarize(rows)
    print(f"{a.set}: {len(rows)} judgements")
    print(f"{'type':14s}{'n':>5s}{'win':>5s}{'loss':>5s}{'tie':>5s}  net [95% CI]            content ours/traf   chrome ours/traf")
    for t, v in s.items():
        print(f"{t:14s}{v['n']:5d}{v['wins']:5d}{v['losses']:5d}{v['ties']:5d}  {v['net']:+.2f} [{v['net_ci95'][0]:+.2f},{v['net_ci95'][1]:+.2f}]   {v['content_ours']:.2f}/{v['content_traf']:.2f}        {v['chrome_ours']:.2f}/{v['chrome_traf']:.2f}")
    if a.out:
        Path(a.out).write_text(json.dumps({"summary": s, "judgements": rows}, indent=1))


if __name__ == "__main__":
    main()
