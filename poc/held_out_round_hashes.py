"""Regenerate final2 ChromeRAG/Trafilatura outputs under candidate commits and compare.

Rounds v014c / v014d / final ran on 2026-10-02 between about 19:05 and 20:49. Candidate
commits on that day from ``git log freeze-0.1.3..v0.1.4`` that change extractor code are
9b0afed (17:14) and d396e64 (20:26). Rounds at 19:05–19:48 fall between those commits, so
a 9b0afed checkout may not be the exact code of those rounds (uncommitted work possible).

Follows poc/claude_judge_build.py extraction: ChromeRAG balanced, Trafilatura baseline,
YAML front-matter stripped from ChromeRAG. No judge or API calls.

  PYTHONPATH=src:. python -m poc.held_out_round_hashes
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Checkout that holds the git-ignored data and the original file times.
MAIN = Path(os.environ.get("CHROMERAG_MAIN_CHECKOUT", str(ROOT)))
FINAL = ROOT / "evaluations/2026-10-v0.1.3/FINAL"
OUT_JSON = ROOT / "evaluations/2026-10-v0.1.3/held_out_round_hashes.json"
WORKTREE_ROOT = Path(tempfile.gettempdir()) / "chromerag-p01-commits"
CANDIDATE_COMMITS = ("9b0afed", "d396e64")
_FRONT = re.compile(r"\A---\n.*?\n---\n+", re.S)
_FINAL2_KINDS = {"articles": "article", "forums": "forum", "listings": "listing", "services": "service"}

ROUND_FILES = {
    "v014c": {
        "gpt": "gpt_judge_v014c_final2.json",
    },
    "v014d": {
        "gpt": "gpt_judge_v014d_final2.json",
        "claude": "claude_judge_v014d_final2.json",
        "gemini": "gemini_judge_v014d_final2.json",
    },
    "final": {
        "gpt": "gpt_judge_final_final2.json",
        "claude": "claude_judge_final_final2.json",
        "gemini": "gemini_judge_final_final2.json",
    },
}


def _git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def _find_preserved_judge_items() -> dict:
    """Judge batch items hold clipped A/B extractions; aggregates in FINAL do not."""
    checked = {
        "FINAL_judge_json_fields": sorted(
            json.loads((FINAL / "gpt_judge_final_final2.json").read_text())["judgements"][0].keys()
        ),
        "tmp_cr_judge": Path("/tmp/cr/judge").exists(),
        "main_tmp_batches": False,
        "preserved_outputs": False,
        "note": (
            "Aggregated FINAL/*_final2.json judgements keep winner/scores/reason only — not A/B "
            "extraction text. poc/claude_judge_build writes batches under /tmp/cr/judge (gitignored, "
            "ephemeral). No preserved batch/key trees found for a direct hash comparison."
        ),
    }
    # shallow search for leftover batch files that embed "A"/"B" extraction text
    for base in (MAIN, Path("/tmp"), Path("/private/tmp")):
        for pattern in ("**/batches/final2_*.json", "**/cr/judge/batches/*.json"):
            hits = list(base.glob(pattern)) if base.exists() else []
            if hits:
                checked["main_tmp_batches"] = True
                # confirm structure
                sample = json.loads(hits[0].read_text())
                if sample and isinstance(sample, list) and "A" in sample[0] and "B" in sample[0]:
                    checked["preserved_outputs"] = True
                    checked["example_batch"] = str(hits[0])
                    break
        if checked["preserved_outputs"]:
            break
    return checked


def _final2_pages(data_root: Path) -> list[tuple[str, str, str, str]]:
    """Return (pid, page_type, url, html) like claude_judge_build.pages('final2')."""
    rows = []
    for kind, ptype in _FINAL2_KINDS.items():
        for meta in sorted((data_root / "extra_raw_final2" / kind).glob("*.meta.json")):
            m = json.loads(meta.read_text())
            html = (meta.parent / f"{m['id']}.html").read_text(encoding="utf-8", errors="ignore")
            rows.append((f"{kind}-{m['id']}", ptype, m["url"], html))
    return rows


def _pids_328() -> list[str]:
    data = json.loads((FINAL / "gpt_judge_final_final2.json").read_text())
    return sorted({j["pid"] for j in data["judgements"]})


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _extract_at(worktree: Path, pages: list[tuple[str, str, str, str]], pids: set[str]) -> dict:
    """Import chromerag/baselines from worktree; return pid -> {chromerag, trafilatura, hashes}."""
    # Ensure worktree src is imported, not this checkout's
    for key in list(sys.modules):
        if key == "chromerag" or key.startswith("chromerag.") or key == "poc" or key.startswith("poc."):
            del sys.modules[key]
    sys.path.insert(0, str(worktree / "src"))
    sys.path.insert(0, str(worktree))
    try:
        from chromerag import ChromeRAG, ContentPriority, PipelineConfig  # type: ignore
        from poc.baselines import BASELINES  # type: ignore

        rag = ChromeRAG(config=PipelineConfig.from_priority(ContentPriority.BALANCED))
        out = {}
        for pid, _ptype, url, html in pages:
            if pid not in pids:
                continue
            ours = _FRONT.sub("", rag.extract(html, url=url or None).markdown)
            try:
                theirs = BASELINES["trafilatura"](html) or ""
            except Exception:  # noqa: BLE001 — same as claude_judge_build
                theirs = ""
            if not ours.strip() or not theirs.strip():
                continue
            out[pid] = {
                "type": _ptype_for(pid, pages),
                "chromerag": ours,
                "trafilatura": theirs,
                "chromerag_sha256": hashlib.sha256(ours.encode()).hexdigest(),
                "trafilatura_sha256": hashlib.sha256(theirs.encode()).hexdigest(),
                "chromerag_words": _word_count(ours),
                "trafilatura_words": _word_count(theirs),
            }
        return out
    finally:
        sys.path[:] = [p for p in sys.path if p not in (str(worktree), str(worktree / "src"))]
        for key in list(sys.modules):
            if key == "chromerag" or key.startswith("chromerag.") or key == "poc" or key.startswith("poc."):
                del sys.modules[key]


def _ptype_for(pid: str, pages: list[tuple[str, str, str, str]]) -> str:
    for p, t, *_ in pages:
        if p == pid:
            return t
    return "unknown"


def _ensure_worktree(commit: str) -> Path:
    WORKTREE_ROOT.mkdir(parents=True, exist_ok=True)
    dest = WORKTREE_ROOT / commit
    if dest.exists():
        subprocess.check_call(["git", "worktree", "remove", "--force", str(dest)], cwd=ROOT)
    subprocess.check_call(["git", "worktree", "add", "--detach", str(dest), commit], cwd=ROOT)
    # data and venv live only in the main checkout
    data_link = dest / "data"
    if data_link.exists() or data_link.is_symlink():
        if data_link.is_symlink() or data_link.is_file():
            data_link.unlink()
        else:
            shutil.rmtree(data_link)
    data_link.symlink_to(MAIN / "data")
    return dest


def _remove_worktree(commit: str) -> None:
    dest = WORKTREE_ROOT / commit
    if dest.exists():
        subprocess.check_call(["git", "worktree", "remove", "--force", str(dest)], cwd=ROOT)


def _compare(a: dict, b: dict, label_a: str, label_b: str) -> dict:
    common = sorted(set(a) & set(b))
    differ_cr = [pid for pid in common if a[pid]["chromerag_sha256"] != b[pid]["chromerag_sha256"]]
    differ_tr = [pid for pid in common if a[pid]["trafilatura_sha256"] != b[pid]["trafilatura_sha256"]]
    # "outputs" in the task sense: ChromeRAG balanced (the tool under test); also report trafilatura
    by_type = defaultdict(lambda: {"n": 0, "differ_chromerag": 0, "differ_trafilatura": 0})
    word_deltas = []
    for pid in common:
        t = a[pid]["type"]
        by_type[t]["n"] += 1
        if a[pid]["chromerag_sha256"] != b[pid]["chromerag_sha256"]:
            by_type[t]["differ_chromerag"] += 1
            word_deltas.append(abs(a[pid]["chromerag_words"] - b[pid]["chromerag_words"]))
        if a[pid]["trafilatura_sha256"] != b[pid]["trafilatura_sha256"]:
            by_type[t]["differ_trafilatura"] += 1
    return {
        "commit_a": label_a,
        "commit_b": label_b,
        "n_common": len(common),
        "differ_chromerag": len(differ_cr),
        "differ_trafilatura": len(differ_tr),
        "median_abs_word_change_chromerag": (
            float(statistics.median(word_deltas)) if word_deltas else 0.0
        ),
        "per_page_type": {k: dict(v) for k, v in sorted(by_type.items())},
        "differ_chromerag_pids": differ_cr,
    }


def _winners(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text())
    return {j["pid"]: j["winner"] for j in data["judgements"]}


def _winner_change_split(
    before: str, after: str, changed_outputs: set[str], pair_label: str
) -> dict:
    wa = _winners(FINAL / before)
    wb = _winners(FINAL / after)
    common = set(wa) & set(wb)
    changed_winner = {pid for pid in common if wa[pid] != wb[pid]}
    with_code = sorted(changed_winner & changed_outputs)
    without_code = sorted(changed_winner - changed_outputs)
    return {
        "pair": pair_label,
        "result_before": before,
        "result_after": after,
        "n_common_pages": len(common),
        "n_winner_changed": len(changed_winner),
        "n_winner_changed_and_output_changed": len(with_code),
        "n_winner_changed_and_output_unchanged": len(without_code),
        "note": (
            "output_changed uses regenerated ChromeRAG balanced hash difference between the "
            "candidate commits paired to these rounds; see caveats about uncommitted code"
        ),
    }


def main() -> None:
    py = MAIN / ".venv/bin/python"
    if not py.exists():
        raise SystemExit(f"missing venv python: {py}")

    preserved = _find_preserved_judge_items()
    pids = _pids_328()
    pages = _final2_pages(MAIN / "data")
    assert len(pids) == 328, len(pids)

    commit_meta = {}
    for h in CANDIDATE_COMMITS:
        commit_meta[h] = {
            "subject": _git("log", "-1", "--format=%s", h),
            "author_date": _git("log", "-1", "--format=%aI", h),
        }

    # Also record any other Oct-2 commits in the range (evidence scan)
    oct2 = []
    for line in _git("log", "--format=%h %aI %s", "freeze-0.1.3..v0.1.4").splitlines():
        h, iso, subj = line.split(" ", 2)
        if iso.startswith("2026-10-02"):
            oct2.append({"commit": h, "author_date": iso, "subject": subj})

    by_commit = {}
    try:
        for h in CANDIDATE_COMMITS:
            wt = _ensure_worktree(h)
            print(f"extracting under {h} in {wt} ...", flush=True)
            # Run extraction in a subprocess with the worktree on PYTHONPATH so imports are clean
            payload = {
                "worktree": str(wt),
                "main_data": str(MAIN / "data"),
                "pids": pids,
            }
            helper = r"""
import hashlib, json, re, sys
from pathlib import Path
payload = json.loads(sys.argv[1])
wt = Path(payload["worktree"])
sys.path.insert(0, str(wt / "src"))
sys.path.insert(0, str(wt))
from chromerag import ChromeRAG, ContentPriority, PipelineConfig
from poc.baselines import BASELINES
_FRONT = re.compile(r"\A---\n.*?\n---\n+", re.S)
_FINAL2_KINDS = {"articles": "article", "forums": "forum", "listings": "listing", "services": "service"}
data_root = Path(payload["main_data"])
pids = set(payload["pids"])
pages = []
for kind, ptype in _FINAL2_KINDS.items():
    for meta in sorted((data_root / "extra_raw_final2" / kind).glob("*.meta.json")):
        m = json.loads(meta.read_text())
        html = (meta.parent / f"{m['id']}.html").read_text(encoding="utf-8", errors="ignore")
        pid = f"{kind}-{m['id']}"
        if pid in pids:
            pages.append((pid, ptype, m["url"], html))
rag = ChromeRAG(config=PipelineConfig.from_priority(ContentPriority.BALANCED))
out = {}
for pid, ptype, url, html in pages:
    ours = _FRONT.sub("", rag.extract(html, url=url or None).markdown)
    try:
        theirs = BASELINES["trafilatura"](html) or ""
    except Exception:
        theirs = ""
    if not ours.strip() or not theirs.strip():
        continue
    out[pid] = {
        "type": ptype,
        "chromerag_sha256": hashlib.sha256(ours.encode()).hexdigest(),
        "trafilatura_sha256": hashlib.sha256(theirs.encode()).hexdigest(),
        "chromerag_words": len(re.findall(r"\S+", ours)),
        "trafilatura_words": len(re.findall(r"\S+", theirs)),
    }
print(json.dumps(out))
"""
            env = {**os.environ, "PYTHONPATH": f"{wt / 'src'}:{wt}", "PYTHONWARNINGS": "ignore"}
            proc = subprocess.run(
                [str(py), "-c", helper, json.dumps(payload)],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            # last line is JSON
            line = proc.stdout.strip().splitlines()[-1]
            by_commit[h] = json.loads(line)
            print(f"  got {len(by_commit[h])} pages", flush=True)
    finally:
        for h in CANDIDATE_COMMITS:
            try:
                _remove_worktree(h)
            except subprocess.CalledProcessError as exc:
                print(f"worktree remove {h}: {exc}", flush=True)

    pair = _compare(by_commit["9b0afed"], by_commit["d396e64"], "9b0afed", "d396e64")
    changed = set(pair["differ_chromerag_pids"])

    # Round-to-commit mapping used for the winner split (evidenced by mtimes vs commit times)
    round_commit = {
        "v014c": {
            "mtime_window": "2026-10-02T19:04–19:05",
            "nearest_committed": "9b0afed",
            "caveat": (
                "v014c ran ~19:05, after 9b0afed (17:14) and before d396e64 (20:26); "
                "working tree may have contained uncommitted changes, so 9b0afed may not be exact"
            ),
        },
        "v014d": {
            "mtime_window": "2026-10-02T19:16–19:48",
            "nearest_committed": "9b0afed",
            "caveat": (
                "v014d ran 19:16–19:48 between 9b0afed and d396e64; "
                "9b0afed checkout may not be the exact code of those rounds"
            ),
        },
        "final": {
            "mtime_window": "2026-10-02T20:37–20:49",
            "nearest_committed": "d396e64",
            "caveat": "final judges after d396e64 (20:26); treating d396e64 as the committed baseline",
        },
    }

    winner_splits = []
    # gpt v014c -> final (full 328), using 9b0afed vs d396e64 output changes
    winner_splits.append(
        _winner_change_split(
            "gpt_judge_v014c_final2.json",
            "gpt_judge_final_final2.json",
            changed,
            "gpt:v014c->final (output delta 9b0afed->d396e64)",
        )
    )
    winner_splits.append(
        _winner_change_split(
            "gpt_judge_v014c_final2.json",
            "gpt_judge_v014d_final2.json",
            changed,
            "gpt:v014c->v014d (output delta 9b0afed->d396e64; v014d is 250-page subset)",
        )
    )
    winner_splits.append(
        _winner_change_split(
            "gpt_judge_v014d_final2.json",
            "gpt_judge_final_final2.json",
            changed,
            "gpt:v014d->final (output delta 9b0afed->d396e64)",
        )
    )
    winner_splits.append(
        _winner_change_split(
            "claude_judge_v014d_final2.json",
            "claude_judge_final_final2.json",
            changed,
            "claude:v014d->final (output delta 9b0afed->d396e64)",
        )
    )
    winner_splits.append(
        _winner_change_split(
            "gemini_judge_v014d_final2.json",
            "gemini_judge_final_final2.json",
            changed,
            "gemini:v014d->final (output delta 9b0afed->d396e64)",
        )
    )

    report = {
        "n_pages_judged": 328,
        "n_pages_on_disk_meta": len(pages),
        "candidate_commits": commit_meta,
        "oct2_commits_in_freeze_to_v014": oct2,
        "caveat_uncommitted_window": (
            "Judge rounds v014c/v014d ran at 19:05–19:48 on 2026-10-02 while the only committed "
            "extractor tip was 9b0afed (17:14); d396e64 landed at 20:26. The session log shows those rounds ran on a working "
            "tree already holding coding tasks 4 to 6, not on 9b0afed, and that tree was not kept. So 9b0afed is a "
            "lower bound on the code of those rounds, the differ counts overstate the change between rounds, and "
            "the winner split is indicative only."
        ),
        "round_commit_mapping": round_commit,
        "preserved_judge_items": preserved,
        "per_commit_n_extracted": {h: len(by_commit[h]) for h in CANDIDATE_COMMITS},
        "commit_pair_diffs": [pair],
        "winner_change_splits": winner_splits,
    }
    # drop bulky pid list from top-level pair copy used above — keep in report but OK
    OUT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_JSON}")
    print(
        f"differ chromerag {pair['differ_chromerag']}/{pair['n_common']}; "
        f"trafilatura {pair['differ_trafilatura']}; "
        f"median abs word change {pair['median_abs_word_change_chromerag']}"
    )


if __name__ == "__main__":
    main()
