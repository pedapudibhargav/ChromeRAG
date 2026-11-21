"""Post hoc: how much of the page-judge lead remains once output length is accounted for.

Uses saved verdicts and output lengths only; makes no model calls. Added after the verdicts
were seen, so it is exploratory and never replaces the planned counts.

  python -m poc.final_page_length_analysis
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evaluations" / "2026-11-final" / "results" / "new_pages"
REFERENCE = "chromerag"
BASELINES = ("trafilatura", "readability", "markitdown")
SIMILAR_LENGTH_RATIO = 1.1
ITERATIONS = 2000


def net(rows: list[dict]) -> float | None:
    if not rows:
        return None
    return sum((r["winner"] == "chromerag") - (r["winner"] == "baseline") for r in rows) / len(rows)


def interval(rows: list[dict]) -> list[float] | None:
    if not rows:
        return None
    rng = random.Random(0)
    vals = sorted(net(rng.choices(rows, k=len(rows))) for _ in range(ITERATIONS))
    return [round(vals[int(ITERATIONS * 0.025)], 3), round(vals[int(ITERATIONS * 0.975)], 3)]


def stratum(rows: list[dict]) -> dict:
    wins = sum(r["winner"] == "chromerag" for r in rows)
    losses = sum(r["winner"] == "baseline" for r in rows)
    value = net(rows)
    return {
        "pairs": len(rows),
        "chromerag": wins,
        "baseline": losses,
        "tie": len(rows) - wins - losses,
        "net": None if value is None else round(value, 3),
        "ci95": interval(rows),
    }


def fit_equal_length_lead(rows: list[dict]) -> float:
    """Logistic fit on decided pairs: chromerag win ~ intercept + log length ratio.

    The intercept is the chromerag win probability at equal length, on the log-odds scale.
    """
    decided = [r for r in rows if r["winner"] != "tie"]
    b0 = b1 = 0.0
    for _ in range(50):
        g0 = g1 = h00 = h01 = h11 = 0.0
        for r in decided:
            x = r["log_ratio"]
            p = 1 / (1 + math.exp(-(b0 + b1 * x)))
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
    return 1 / (1 + math.exp(-b0))


def analyse(judge: dict, extract: dict) -> dict:
    out: dict = {}
    primary = [r for r in judge["judgements"] if not r["swapped"]]
    for base in BASELINES:
        rows = []
        for r in primary:
            if r["baseline"] != base:
                continue
            ours = extract["per_page"][r["id"]][REFERENCE]["chars"]
            theirs = extract["per_page"][r["id"]][base]["chars"]
            rows.append({**r, "ratio": (ours + 1) / (theirs + 1), "log_ratio": math.log((ours + 1) / (theirs + 1))})
        low, high = 1 / SIMILAR_LENGTH_RATIO, SIMILAR_LENGTH_RATIO
        rng = random.Random(0)
        decided = [r for r in rows if r["winner"] != "tie"]
        fits = sorted(fit_equal_length_lead(rng.choices(decided, k=len(decided))) for _ in range(500))
        out[base] = {
            "all": stratum(rows),
            "similar_length": stratum([r for r in rows if low <= r["ratio"] <= high]),
            "chromerag_longer": stratum([r for r in rows if r["ratio"] > high]),
            "baseline_longer": stratum([r for r in rows if r["ratio"] < low]),
            "chromerag_longer_share": round(sum(r["ratio"] > 1 for r in rows) / len(rows), 3),
            "win_probability_at_equal_length": {
                "estimate": round(fit_equal_length_lead(decided), 3),
                "ci95": [round(fits[12], 3), round(fits[487], 3)],
            },
        }
    return out


def main() -> None:
    judge = json.loads((RESULTS / "new_pages_judge.json").read_text(encoding="utf-8"))
    extract = json.loads((RESULTS / "new_pages_extract.json").read_text(encoding="utf-8"))
    report = {"post_hoc": True, "basis": "saved verdicts and output lengths", **analyse(judge, extract)}
    (RESULTS / "length_analysis_posthoc.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
