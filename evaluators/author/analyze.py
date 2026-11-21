"""Analyse blind human-rating result files against bundle + key.

  python -m evaluators.author.analyze \\
    --results evaluators/results \\
    --bundle path/to/bundle.json \\
    --key path/to/key.json \\
    --out report.json

Does not run on real evaluation corpora by default; pass paths explicitly.
NumPy is allowed here. Optional --judges compares with LM-judge JSON
(fields: judgements[].pid, winner in {ours,traf,tie}).
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

FOCUS_PAIR = ("chromerag", "trafilatura")

# Careless-rater rule, fixed before any rating was returned. Raters it flags stay in the main
# result and are left out only in a second, sensitivity result reported beside it.
CARE_MIN_MEDIAN_SECONDS = 30.0
CARE_MIN_REPEATS = 4  # the full set has 5 repeats; parts have 1 or 2, too few to judge
CARE_MIN_REPEAT_AGREE = 0.6  # fewer than 3 of 5 repeats agree
CARE_MIN_ITEMS_SAME = 10
CARE_MAX_SAME_SHARE = 0.9


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def pairwise_verdict(best_tools: set[str], tool_a: str, tool_b: str, *, all_same: bool) -> str:
    """Return 'a', 'b', or 'tie' for tool_a vs tool_b."""
    if all_same:
        return "tie"
    has_a = tool_a in best_tools
    has_b = tool_b in best_tools
    if has_a and not has_b:
        return "a"
    if has_b and not has_a:
        return "b"
    return "tie"


def unblind_item(entry: dict, key_for_item: dict[str, str]) -> dict:
    best_labels = list(entry.get("best") or [])
    order = list(entry.get("shown_order") or sorted(key_for_item))
    best_tools = {key_for_item[label] for label in best_labels if label in key_for_item}
    scores_by_tool = {}
    for lab, sc in (entry.get("scores") or {}).items():
        tool = key_for_item.get(lab)
        if tool:
            scores_by_tool[tool] = sc
    return {
        "best_tools": sorted(best_tools),
        "all_same": bool(entry.get("all_same")),
        "none_good": bool(entry.get("none_good")),
        "skipped": bool(entry.get("skipped")),
        "scores_by_tool": scores_by_tool,
        "seconds_spent": float(entry.get("seconds_spent") or 0),
        # Screen positions of the chosen outputs, for the same-answer check; labels are shuffled per rater.
        "answer_pattern": (
            tuple(sorted(order.index(lab) for lab in best_labels if lab in order)),
            bool(entry.get("all_same")),
            bool(entry.get("none_good")),
        ),
    }


def bootstrap_mean_ci(values: np.ndarray, iters: int = 5000, seed: int = 0) -> dict:
    if len(values) == 0:
        return {"mean": None, "lo": None, "hi": None, "n": 0}
    rng = np.random.default_rng(seed)
    bs = np.array([values[rng.integers(0, len(values), len(values))].mean() for _ in range(iters)])
    return {
        "mean": float(values.mean()),
        "lo": float(np.percentile(bs, 2.5)),
        "hi": float(np.percentile(bs, 97.5)),
        "n": int(len(values)),
    }


def net_preference(verdicts: list[str]) -> dict:
    """Net = (wins_a - wins_b) / n ; page-level bootstrap CI on that score."""
    if not verdicts:
        return {"net": None, "ci95": None, "wins_a": 0, "wins_b": 0, "ties": 0, "n": 0}
    scores = np.array(
        [1.0 if v == "a" else (-1.0 if v == "b" else 0.0) for v in verdicts], dtype=float
    )
    ci = bootstrap_mean_ci(scores)
    return {
        "net": ci["mean"],
        "ci95": [ci["lo"], ci["hi"]],
        "wins_a": int(sum(v == "a" for v in verdicts)),
        "wins_b": int(sum(v == "b" for v in verdicts)),
        "ties": int(sum(v == "tie" for v in verdicts)),
        "n": len(verdicts),
    }


def krippendorff_alpha_nominal(coder_item: dict[str, dict[str, str]]) -> float | None:
    """Krippendorff's alpha (nominal) over raters × items with values in a finite set."""
    raters = sorted(coder_item)
    if len(raters) < 2:
        return None
    items = sorted({iid for r in raters for iid in coder_item[r]})
    # Collect coincidence matrix
    values = sorted({coder_item[r][i] for r in raters for i in coder_item[r] if i in coder_item[r]})
    if len(values) < 2:
        return 1.0
    idx = {v: i for i, v in enumerate(values)}
    m = len(values)
    coincidence = np.zeros((m, m), dtype=float)
    for iid in items:
        observed = [coder_item[r][iid] for r in raters if iid in coder_item[r]]
        n = len(observed)
        if n < 2:
            continue
        for a in range(n):
            for b in range(n):
                if a == b:
                    continue
                coincidence[idx[observed[a]], idx[observed[b]]] += 1.0 / (n - 1)
    n_total = coincidence.sum()
    if n_total <= 0:
        return None
    # Observed disagreement
    do = 0.0
    for i in range(m):
        for j in range(m):
            if i != j:
                do += coincidence[i, j]
    do /= n_total
    # Expected disagreement
    n_c = coincidence.sum(axis=1)
    de = 0.0
    for i in range(m):
        for j in range(m):
            if i != j:
                de += n_c[i] * n_c[j]
    de /= n_total * (n_total - 1) if n_total > 1 else 1.0
    if de == 0:
        return 1.0 if do == 0 else 0.0
    return float(1.0 - (do / de))


def cohen_kappa(a: list[str], b: list[str]) -> float | None:
    if not a or len(a) != len(b):
        return None
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = 0.0
    for lab in labels:
        pe += (sum(x == lab for x in a) / n) * (sum(y == lab for y in b) / n)
    if pe == 1:
        return 1.0
    return float((po - pe) / (1 - pe))


def majority_verdict(votes: list[str]) -> str:
    if not votes:
        return "tie"
    counts = {k: votes.count(k) for k in ("a", "b", "tie")}
    # Prefer decisive votes; ties if tied counts
    best = max(counts.values())
    winners = [k for k, v in counts.items() if v == best]
    if len(winners) > 1:
        return "tie"
    return winners[0]


def base_item_id(item_id: str) -> str:
    return re.sub(r"__r\d+$", "", item_id)


def _pair_reports(per_rater: dict[str, dict[str, dict]], tools: list[str], repeat_of: dict) -> dict[str, Any]:
    pairs = []
    for i, a in enumerate(tools):
        for b in tools[i + 1 :]:
            pairs.append((a, b))
    if FOCUS_PAIR[0] in tools and FOCUS_PAIR[1] in tools:
        # ensure focus pair is first
        pairs = [FOCUS_PAIR] + [p for p in pairs if p != FOCUS_PAIR]

    pair_reports: dict[str, Any] = {}
    for tool_a, tool_b in pairs:
        pair_key = f"{tool_a}_vs_{tool_b}"
        rater_nets = {}
        coder_item: dict[str, dict[str, str]] = {}
        item_votes: dict[str, list[str]] = defaultdict(list)

        for rater, items in per_rater.items():
            verdicts = []
            coder_item[rater] = {}
            for iid, u in items.items():
                if iid in repeat_of:
                    # A repeat is the same page seen again; it counts only toward repeat consistency.
                    continue
                v = pairwise_verdict(set(u["best_tools"]), tool_a, tool_b, all_same=u["all_same"])
                if u["none_good"] and not u["best_tools"]:
                    v = "tie"
                verdicts.append(v)
                coder_item[rater][iid] = v
                item_votes[iid].append(v)
            rater_nets[rater] = net_preference(verdicts)

        maj_verdicts = [majority_verdict(item_votes[iid]) for iid in sorted(item_votes)]
        pair_reports[pair_key] = {
            "tool_a": tool_a,
            "tool_b": tool_b,
            "per_rater_net": rater_nets,
            "majority_net": net_preference(maj_verdicts),
            "krippendorff_alpha": krippendorff_alpha_nominal(coder_item),
        }
    return pair_reports


def care_flags(items: dict[str, dict], repeat: dict) -> list[str]:
    """Planned checks for careless rating (protocol, 2026-11-02). Used only for the sensitivity result."""
    flags = []
    times = [u["seconds_spent"] for u in items.values()]
    if times and float(np.median(times)) < CARE_MIN_MEDIAN_SECONDS:
        flags.append("fast")
    if (repeat.get("n_groups") or 0) >= CARE_MIN_REPEATS and repeat["agree_rate"] < CARE_MIN_REPEAT_AGREE:
        flags.append("inconsistent_repeats")
    # The same answer by screen position on nearly every item means the text was not read.
    answers = [u["answer_pattern"] for u in items.values()]
    if len(answers) >= CARE_MIN_ITEMS_SAME:
        top = max(answers.count(a) for a in set(answers))
        if top / len(answers) >= CARE_MAX_SAME_SHARE:
            flags.append("same_answer")
    return flags


def analyse(
    results: list[dict],
    bundle: dict,
    key_doc: dict,
    judges: dict | None = None,
) -> dict:
    key = key_doc["key"]
    repeat_of = key_doc.get("repeat_of") or {}
    cal_ids = {it["item_id"] for it in bundle.get("calibration", [])}
    tools = list(key_doc.get("tools") or sorted({t for m in key.values() for t in m.values()}))

    # Per rater, per item (exclude calibration)
    per_rater: dict[str, dict[str, dict]] = {}
    exclusions: list[dict] = []
    for res in results:
        rater = res["rater"]
        per_rater.setdefault(rater, {})
        for iid, entry in (res.get("items") or {}).items():
            if iid in cal_ids:
                continue
            if iid not in key:
                exclusions.append({"rater": rater, "item_id": iid, "reason": "missing_key"})
                continue
            if entry.get("skipped"):
                exclusions.append({"rater": rater, "item_id": iid, "reason": "skipped"})
                continue
            scores = entry.get("scores") or {}
            chosen = entry.get("all_same") or entry.get("none_good") or entry.get("best")
            if not chosen or not all(
                (scores.get(lab) or {}).get("content") and (scores.get(lab) or {}).get("chrome") for lab in key[iid]
            ):
                exclusions.append({"rater": rater, "item_id": iid, "reason": "incomplete"})
                continue
            per_rater[rater][iid] = unblind_item(entry, key[iid])

    pair_reports = _pair_reports(per_rater, tools, repeat_of)

    # Repeat consistency: same base id, same rater, same pairwise focus verdict
    repeat_consistency: dict[str, Any] = {}
    ta, tb = FOCUS_PAIR if FOCUS_PAIR[0] in tools else (tools[0], tools[1] if len(tools) > 1 else tools[0])
    for rater, items in per_rater.items():
        groups: dict[str, list[str]] = defaultdict(list)
        for iid, u in items.items():
            v = pairwise_verdict(set(u["best_tools"]), ta, tb, all_same=u["all_same"])
            if u["none_good"] and not u["best_tools"]:
                v = "tie"
            groups[repeat_of.get(iid, base_item_id(iid))].append(v)
        multi = {k: vs for k, vs in groups.items() if len(vs) > 1}
        if not multi:
            repeat_consistency[rater] = {"n_groups": 0, "agree_rate": None}
            continue
        agree = sum(1 for vs in multi.values() if len(set(vs)) == 1)
        repeat_consistency[rater] = {
            "n_groups": len(multi),
            "agree_rate": agree / len(multi),
        }

    care = {r: care_flags(items, repeat_consistency[r]) for r, items in per_rater.items()}
    kept = {r: items for r, items in per_rater.items() if not care[r]}
    sensitivity = {
        "rule": "leave out raters with a median under 30 s per item, fewer than 60% agreeing repeats "
        "(only with 4 or more repeats), or one answer by screen position on 90% or more of 10 or more items",
        "flags": {r: f for r, f in care.items() if f},
        "raters_kept": sorted(kept),
        "pairs": _pair_reports(kept, tools, repeat_of) if kept else None,
    }

    # Mean scores per tool
    score_acc: dict[str, list[tuple[float, float]]] = defaultdict(list)
    times: list[float] = []
    missing_notes: list[dict[str, str]] = []
    for rater, items in per_rater.items():
        for iid, u in items.items():
            times.append(u["seconds_spent"])
            for tool, sc in u["scores_by_tool"].items():
                note = str(sc.get("missing") or "").strip()
                if note:
                    missing_notes.append({"rater": rater, "item_id": iid, "tool": tool, "note": note})
                if "content" in sc and "chrome" in sc:
                    score_acc[tool].append((float(sc["content"]), float(sc["chrome"])))

    mean_scores = {}
    for tool, rows in score_acc.items():
        arr = np.array(rows, dtype=float)
        mean_scores[tool] = {
            "content": float(arr[:, 0].mean()),
            "chrome": float(arr[:, 1].mean()),
            "n": int(len(rows)),
        }

    report: dict[str, Any] = {
        "bundle_id": bundle.get("bundle_id"),
        "n_result_files": len(results),
        "raters": sorted(per_rater),
        "tools": tools,
        "pairs": pair_reports,
        "focus_pair": f"{ta}_vs_{tb}",
        "repeat_consistency": repeat_consistency,
        "sensitivity_without_flagged_raters": sensitivity,
        "mean_scores": mean_scores,
        "missing_notes": missing_notes,
        "time_per_item_seconds": {
            "mean": float(np.mean(times)) if times else None,
            "n": len(times),
        },
        "exclusions": exclusions,
        "calibration_excluded": sorted(cal_ids),
    }

    if judges is not None:
        # Map page id -> LM verdict for chromerag vs trafilatura (winner: ours|traf|tie)
        lm: dict[str, str] = {}
        for j in judges.get("judgements") or []:
            w = j.get("winner")
            pid = j.get("pid")
            if w == "ours":
                lm[pid] = "a"
            elif w == "traf":
                lm[pid] = "b"
            else:
                lm[pid] = "tie"
        focus_votes: dict[str, list[str]] = defaultdict(list)
        for items in per_rater.values():
            for iid, u in items.items():
                v = pairwise_verdict(set(u["best_tools"]), ta, tb, all_same=u["all_same"])
                if u["none_good"] and not u["best_tools"]:
                    v = "tie"
                focus_votes[repeat_of.get(iid, base_item_id(iid))].append(v)
        human_a: list[str] = []
        lm_a: list[str] = []
        for base, votes in sorted(focus_votes.items()):
            if base not in lm:
                continue
            human_a.append(majority_verdict(votes))
            lm_a.append(lm[base])
        report["cohen_kappa_vs_judges"] = {
            "pair": f"{ta}_vs_{tb}",
            "kappa": cohen_kappa(human_a, lm_a),
            "n": len(human_a),
        }

    return report


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Analyse blind rating results")
    p.add_argument("--results", type=Path, required=True, help="Directory or single result JSON")
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--key", type=Path, required=True)
    p.add_argument("--judges", type=Path, default=None)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)

    bundle = load_json(args.bundle)
    key_doc = load_json(args.key)
    if args.results.is_dir():
        paths = sorted(args.results.glob("*.json"))
    else:
        paths = [args.results]
    results = [load_json(x) for x in paths]
    # Raters choose their own names, so two files can carry the same one. Keep them apart.
    seen: dict[str, int] = {}
    for path, res in zip(paths, results):
        name = res["rater"]
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            res["rater"] = f"{name}#{seen[name]}"
            print(f"Rater name {name!r} used again in {path.name}; counted as {res['rater']!r}")
    judges = load_json(args.judges) if args.judges else None
    report = analyse(results, bundle, key_doc, judges=judges)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}")
    focus = report["pairs"].get(report["focus_pair"], {})
    maj = focus.get("majority_net") or {}
    print(
        f"Focus {report['focus_pair']}: majority net={maj.get('net')} "
        f"ci95={maj.get('ci95')} alpha={focus.get('krippendorff_alpha')}"
    )


if __name__ == "__main__":
    main()
