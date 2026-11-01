"""Build the held-out-use ledger CSV for the SoftwareX evaluation campaign.

Reads file mtimes from the main checkout (clones do not keep mtimes), plus
WORKLOG.md, git history, openai_spend.json, and the judge scripts. Values that
cannot be evidenced are written as "unknown" or "inferred" with a notes trail.

  PYTHONPATH=src:. python -m poc.held_out_ledger
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FINAL_REL = Path("evaluations/2026-10-v0.1.3/FINAL")
OUT_CSV = ROOT / "evaluations/2026-10-v0.1.3/HELD_OUT_LEDGER.csv"
WORKLOG = ROOT / "evaluations/2026-10-v0.1.3/WORKLOG.md"
MAIN_DEFAULT = Path("/Users/bpeddapudi/Documents/projects/HTML-vector-density-filter")

COLUMNS = [
    "run_time",
    "time_source",
    "set",
    "n_pages",
    "tool_version_or_commit",
    "commit_basis",
    "prompt_hash",
    "judge_model",
    "temperature",
    "access_route",
    "cost_usd",
    "result_file",
    "net_overall",
    "notes",
]

# sha256 of poc.run_llm_judge.SYSTEM (shared by GPT batch and Claude sub-agent builds)
SYSTEM_TEXT = """You evaluate HTML-to-text extraction for retrieval-augmented generation (RAG).
You get the visible text of a web page (it includes the page's real content and its site
chrome) and two extractions of that page, A and B. For RAG, a good extraction keeps the
page's substantive content (what the page is about: descriptions, product details, prices,
features, instructions, tables) and drops site chrome (navigation menus, headers and footers,
cookie/consent banners, newsletter or sign-up prompts, repeated calls to action, social links,
legal boilerplate). Losing real content is worse than keeping a little chrome.
Long extractions may be shortened with "[...]" in the middle; judge what you can see.
Answer with JSON only:
{"better": "A" | "B" | "tie",
 "content_A": 1-5, "content_B": 1-5,   (5 = all substantive content kept)
 "chrome_A": 1-5, "chrome_B": 1-5,     (5 = no chrome left)
 "reason": "one short sentence"}"""
PROMPT_HASH = hashlib.sha256(SYSTEM_TEXT.encode()).hexdigest()

# Paper / aggregate scripts name these judges; temperature is never set in poc/openai_client.py.
GPT_MODEL = "gpt-5.6-luna"
CLAUDE_MODEL = "Claude Sonnet 5.5"  # SOFTWAREX_EXPANDED.md judge paragraph
GEMINI_MODEL = "Gemini 3.7 Flash"  # SOFTWAREX_EXPANDED.md judge paragraph


def _main_final() -> Path:
    main = Path(__import__("os").environ.get("CHROMERAG_MAIN_CHECKOUT", str(MAIN_DEFAULT)))
    p = main / FINAL_REL
    if not p.is_dir():
        raise SystemExit(f"main-checkout FINAL missing: {p}")
    return p


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _commits_oct2() -> list[tuple[str, datetime, str]]:
    """Commits on 2026-10-02 in freeze-0.1.3..v0.1.4 (local author date)."""
    rows = []
    out = _git("log", "--format=%h%x09%aI%x09%s", "freeze-0.1.3..v0.1.4")
    for line in out.splitlines():
        h, iso, subj = line.split("\t", 2)
        dt = datetime.fromisoformat(iso)
        if dt.date().isoformat() == "2026-10-02":
            rows.append((h, dt, subj))
    rows.sort(key=lambda r: r[1])
    return rows


def _infer_commit(mtime: datetime, commits: list[tuple[str, datetime, str]]) -> tuple[str, str, str]:
    """Latest commit with author date <= mtime. commit_basis=inferred when from timing."""
    prior = [c for c in commits if c[1] <= mtime]
    if not prior:
        # fall back to freeze tip
        return "2d436bb", "inferred", "no Oct-2 commit at or before mtime; freeze-0.1.3 tip used"
    h, dt, subj = prior[-1]
    return h, "inferred", f"latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime ({dt.isoformat()}; {subj[:60]})"


def _mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone()


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _net_from_summary(data: dict) -> str:
    all_ = (data.get("summary") or {}).get("ALL")
    if isinstance(all_, dict) and "net" in all_:
        return f"{all_['net']:.6f}"
    return "unknown"


def _n_from_summary(data: dict) -> str:
    all_ = (data.get("summary") or {}).get("ALL")
    if isinstance(all_, dict) and "n" in all_:
        return str(all_["n"])
    if "judgements" in data:
        return str(len(data["judgements"]))
    return "unknown"


def _llm_judge_net(data: dict, baseline: str = "trafilatura") -> str:
    """Net = chromerag_wins - baseline_wins from primary (non-swapped) pairs if present."""
    summary = data.get("summary") or {}
    # Prefer all:trafilatura style keys from run_llm_judge.summarize
    for key in (f"all:{baseline}", f"landing:{baseline}", f"benchmark:{baseline}"):
        row = summary.get(key)
        if row and "chromerag_wins" in row and "baseline_wins" in row:
            return f"{row['chromerag_wins'] - row['baseline_wins']:.6f}"
    # Fallback: compute from judgements vs trafilatura, non-swapped
    rows = [
        r
        for r in data.get("judgements", [])
        if r.get("baseline") == baseline and not r.get("swapped")
    ]
    if not rows:
        rows = [r for r in data.get("judgements", []) if not r.get("swapped")]
    if not rows:
        return "unknown"
    n = len(rows)
    wins = sum(r.get("winner") == "chromerag" for r in rows)
    losses = sum(r.get("winner") == "baseline" for r in rows)
    return f"{(wins - losses) / n:.6f}"


def _classify(name: str) -> str | None:
    """Return held-out set label, or None if the file is not a held-out result."""
    if name in {"README.md", "openai_spend.json"}:
        return None
    # More specific needles first.
    mapping = [
        ("mix_markitdown", "mix_wcxb_clean+docs_final+products_final"),
        ("mix_readability", "mix_wcxb_clean+docs_final+products_final"),
        ("final2", "final2"),
        ("docs_final", "docs_final"),
        ("products_final", "products_final"),
        ("wcxb_test", "wcxb_test"),
        ("wcxb_clean", "wcxb_clean"),
        ("heldout", "landing_heldout"),
        ("landing_unseen", "landing_heldout+fresh_unseen_domain"),
        ("llm_judge_final", "landing_heldout+fresh"),
        ("heading_context", "docs_final"),
        ("fresh_retrieval", "landing_fresh"),
        ("fresh", "landing_fresh"),
    ]
    for needle, label in mapping:
        if needle in name:
            return label
    return None


def _file_rows(main_final: Path, commits: list[tuple[str, datetime, str]]) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(main_final.iterdir()):
        if path.name.startswith("."):
            continue
        set_label = _classify(path.name)
        if set_label is None:
            continue
        mtime = _mtime(path)
        run_time = mtime.isoformat(timespec="seconds")
        time_source = "mtime_main_checkout"
        tool, basis, basis_note = _infer_commit(mtime, commits)
        notes = [basis_note]
        prompt_hash = "n/a"
        judge_model = "n/a"
        temperature = "n/a"
        access_route = "n/a"
        cost = "unknown"
        net = "n/a"
        n_pages = "unknown"

        # Explicit freeze for the recorded WCXB test dump (WORKLOG + near-identical mtime)
        if path.name == "wcxb_test.json":
            tool, basis = "2d436bb", "worklog"
            notes = ["WORKLOG: WCXB test run once 2026-10-02 commit 2d436bb tagged freeze-0.1.3; mtime matches freeze minute"]
            data = _load(path)
            n_pages = str(len(data) if isinstance(data, list) else data.get("n", "unknown"))
            # balanced overall from first page aggregate? list of per-page — use WORKLOG 0.902 as note only
            net = "n/a"
            notes.append("primary metric is word F1 balanced 0.902 (WORKLOG), not a judge net")

        elif path.name == "wcxb_test_deduplicated.json":
            data = _load(path)
            n_pages = str(data.get("n", "unknown"))
            tool, basis = "2d436bb", "inferred"
            notes = ["audit of freeze test split; tool commit same as wcxb_test.json (inferred); file records aggregate only"]
            net = "n/a"

        elif path.name in {"wcxb_test_v014_final.json", "wcxb_clean_f1_v014_final.json"}:
            data = _load(path)
            if path.name.endswith("v014_final.json") and isinstance(data, list):
                n_pages = str(len(data))
            elif isinstance(data, dict) and "ALL" in data:
                # aggregate table; page count from sibling per-page file
                n_pages = "372"  # clean split used in v014 F1 table filename wcxb_clean
                notes.append("n_pages=372 from clean-test convention in filename/WORKLOG; aggregate file has no n field")
            tool, basis, basis_note = _infer_commit(mtime, commits)
            notes = [basis_note, "F1 re-score under 0.1.4 pipeline; not a judge net"]

        elif path.name.startswith(("claude_judge_", "gpt_judge_", "gemini_judge_")):
            data = _load(path)
            n_pages = _n_from_summary(data)
            net = _net_from_summary(data)
            prompt_hash = PROMPT_HASH
            temperature = "unknown"
            notes.append("temperature not present in OpenAI client payload; Claude/Gemini temperature not recorded in repo")
            if path.name.startswith("gpt_"):
                judge_model = GPT_MODEL
                access_route = "openai_api"
                notes.append("model from poc/gpt_judge_batches.py / poc/run_llm_judge.py MODEL")
            elif path.name.startswith("claude_"):
                judge_model = CLAUDE_MODEL
                access_route = "anthropic_subagent"
                notes.append("model name from manuscript judge paragraph; access via blinded sub-agent batches (poc/claude_judge_build.py)")
            else:
                judge_model = GEMINI_MODEL
                access_route = "unknown"
                notes.append("model name from manuscript; no Gemini runner script in poc/, access route not recorded")
            if "readability" in path.name:
                notes.append("rival=readability; net is vs Readability not Trafilatura")
            if "mix_" in path.name:
                notes.append("seeded mix over wcxb_clean+docs_final+products_final (poc/claude_judge_build pages('mix'))")
            # cost unknown per file for these aggregates
            cost = "unknown"
            tool, basis, basis_note = _infer_commit(mtime, commits)
            notes.insert(0, basis_note)
            if mtime.hour == 19 and 5 <= mtime.minute <= 48:
                notes.append(
                    "mtime in 19:05-19:48 window: code may have been uncommitted between 9b0afed (17:14) and d396e64 (20:26); "
                    "9b0afed checkout may not be the exact code of this round"
                )

        elif path.name.startswith("llm_judge_"):
            data = _load(path)
            if path.name == "llm_judge_wcxb_test_deduplicated.json":
                n_pages = str(105 - int(data.get("duplicates_excluded", 0)))
                notes.append("derived from llm_judge_wcxb_test.json excluding 33 duplicate pages; no per-judgement payload")
                net = "unknown"
                cost = "unknown"
                judge_model = GPT_MODEL
                prompt_hash = PROMPT_HASH
                temperature = "unknown"
                access_route = "openai_api"
                tool, basis = "0652236", "inferred"
                notes.append("commit inferred from git log of parent llm_judge_wcxb_test.json (0652236)")
            else:
                n_pages = str(data.get("n_pages") or data.get("n_judgements") or "unknown")
                if path.name == "llm_judge_wcxb_test.json":
                    n_pages = str(data.get("n_pages", 105))
                elif path.name == "llm_judge_final.json":
                    # 100 pages sampled; 247 judgements
                    n_pages = "100"
                    notes.append("WORKLOG: 100 pages (50 held-out + 50 fresh); n_judgements in file")
                judge_model = data.get("model", GPT_MODEL)
                prompt_hash = PROMPT_HASH
                temperature = "unknown"
                access_route = "openai_api"
                cost = str(data.get("cost_usd", "unknown"))
                net = _llm_judge_net(data)
                notes.append("temperature not passed in poc/openai_client.chat_json payload")
                tool, basis, basis_note = _infer_commit(mtime, commits)
                # Prefer WORKLOG/git for these morning runs
                if path.name == "llm_judge_final.json":
                    tool, basis = "b1432c3", "worklog"
                    notes.append("WORKLOG: landing/fresh judge after freeze; recorded in commit b1432c3")
                elif path.name == "llm_judge_wcxb_test.json":
                    tool, basis = "0652236", "git_log"
                    notes.append("git log -- FINAL/llm_judge_wcxb_test.json -> 0652236")

        elif "landing_comparison" in path.name:
            if path.suffix == ".md":
                # summary companion; still a held-out artifact
                n_pages = "unknown"
                notes.append("markdown summary companion of the JSON report")
                # try sibling
                sib = path.with_name(path.name.replace("_summary.md", "_report.json"))
                if sib.exists():
                    d = _load(sib)
                    n_pages = str(d.get("n_scoreable") or d.get("n_pages") or "unknown")
            else:
                data = _load(path)
                n_pages = str(data.get("n_scoreable") or data.get("n_pages") or "unknown")
                notes.append("anchor F_bal in summary; net_overall n/a")
            # WORKLOG: run once after freeze; mtime 20:45 may be later rewrite under 0.1.4
            tool, basis = "b1432c3", "worklog"
            notes.append(
                "WORKLOG: landing held-out/fresh scored once after freeze (commit b1432c3). "
                f"mtime {run_time} is later than that commit; may be a rewrite — commit_basis kept as worklog for the evaluation event"
            )
            if "fresh" in path.name:
                set_label = "landing_fresh"
            else:
                set_label = "landing_heldout"

        elif path.name == "landing_unseen_domain.json":
            data = _load(path)
            n_h = data.get("heldout", {}).get("all", {}).get("n")
            n_f = data.get("fresh", {}).get("all", {}).get("n")
            n_hu = data.get("heldout", {}).get("domain_not_in_wcxb_dev", {}).get("n")
            n_fu = data.get("fresh", {}).get("domain_not_in_wcxb_dev", {}).get("n")
            n_pages = f"heldout_all={n_h};fresh_all={n_f};heldout_unseen={n_hu};fresh_unseen={n_fu}"
            tool, basis = "2d436bb", "inferred"
            notes.append("audit filter of landing results; tool same as freeze evaluations (inferred)")

        elif path.name == "fresh_retrieval_eval_report.json":
            data = _load(path)
            n_pages = str(data.get("n_pages", "unknown"))
            tool, basis = "b1432c3", "worklog"
            notes.append("WORKLOG retrieval on fresh companies; cost includes embeddings in openai_spend.json aggregate")
            cost = "unknown"

        elif path.name == "heading_context_retrieval.json":
            data = _load(path)
            n_pages = str(data.get("n_questions", "unknown"))
            tool, basis, basis_note = _infer_commit(mtime, commits)
            notes = [
                basis_note,
                "held-out documentation corpus; n_pages column stores n_questions from file",
                "questions written by blinded Claude judge; retrieval prompt hash not the judge SYSTEM hash",
            ]
            judge_model = CLAUDE_MODEL
            access_route = "anthropic_subagent"
            prompt_hash = "unknown"
            temperature = "unknown"

        else:
            continue

        rows.append(
            {
                "run_time": run_time,
                "time_source": time_source,
                "set": set_label,
                "n_pages": n_pages,
                "tool_version_or_commit": tool,
                "commit_basis": basis,
                "prompt_hash": prompt_hash,
                "judge_model": judge_model,
                "temperature": temperature,
                "access_route": access_route,
                "cost_usd": cost,
                "result_file": path.name,
                "net_overall": net,
                "notes": "; ".join(notes),
            }
        )
    return rows


def _deleted_rows(commits: list[tuple[str, datetime, str]]) -> list[dict]:
    """Rows for exploratory batches listed as deleted in FINAL/README.md, with git evidence."""
    # Pure deletes in 4259080
    pure = [
        ("claude_judge_v014_docs.json", "docs", "353", "-0.036827"),
        ("claude_judge_v014_products.json", "products", "307", "0.355049"),
        ("claude_judge_v014b_docs.json", "docs", "354", "0.240113"),
    ]
    # Renamed away (old name gone); README lists them under superseded/deleted patterns
    renamed = [
        ("claude_judge_v014_wcxb_clean.json", "wcxb_clean", "369", "-0.051491", "renamed to claude_judge_final_wcxb_clean.json in 4259080"),
        ("claude_judge_v014b_wcxb_clean.json", "wcxb_clean", "369", "0.130081", "renamed to claude_judge_v014d_wcxb_clean.json in 4259080"),
        ("claude_judge_v014b_docs_final.json", "docs_final", "180", "0.094444", "renamed/replaced by gpt_judge_final_docs_final.json in 4259080"),
        ("claude_judge_v014b_products_final.json", "products_final", "97", "0.474227", "renamed/replaced by gpt_judge_v014c_products_final.json in 4259080"),
        ("claude_judge_wcxb_clean.json", "wcxb_clean", "369", "-0.130081", "renamed/replaced by gpt_judge_v014c_wcxb_clean.json in 4259080; early net matches manuscript -0.13"),
    ]
    rows = []
    # First-seen commit for the pure deletes
    for name, set_label, n_pages, net in pure:
        log = _git("log", "--format=%h %aI %s", "--", f"{FINAL_REL}/{name}")
        first = log.strip().splitlines()[-1] if log.strip() else ""
        commit = "9b0afed"
        run_time = "unknown"
        time_source = "unknown"
        if first:
            parts = first.split(" ", 2)
            commit = parts[0]
            run_time = parts[1]
            time_source = "git_author_date_first_add"
        rows.append(
            {
                "run_time": run_time,
                "time_source": time_source,
                "set": set_label,
                "n_pages": n_pages,
                "tool_version_or_commit": commit,
                "commit_basis": "inferred",
                "prompt_hash": PROMPT_HASH,
                "judge_model": CLAUDE_MODEL,
                "temperature": "unknown",
                "access_route": "anthropic_subagent",
                "cost_usd": "unknown",
                "result_file": "deleted",
                "net_overall": net,
                "notes": f"deleted path was {name}; recovered summary.ALL from git show 4259080^; README superseded list; mtime unknown after delete",
            }
        )
    for name, set_label, n_pages, net, note in renamed:
        rows.append(
            {
                "run_time": "unknown",
                "time_source": "unknown",
                "set": set_label,
                "n_pages": n_pages,
                "tool_version_or_commit": "9b0afed",
                "commit_basis": "inferred",
                "prompt_hash": PROMPT_HASH,
                "judge_model": CLAUDE_MODEL,
                "temperature": "unknown",
                "access_route": "anthropic_subagent",
                "cost_usd": "unknown",
                "result_file": "deleted",
                "net_overall": net,
                "notes": f"old name {name}; {note}; summary.ALL from git show 4259080^; listed under README superseded patterns",
            }
        )
    # README also lists claude_judge_v014c_*.json — no blob in git history
    rows.append(
        {
            "run_time": "unknown",
            "time_source": "unknown",
            "set": "unknown",
            "n_pages": "unknown",
            "tool_version_or_commit": "unknown",
            "commit_basis": "unknown",
            "prompt_hash": PROMPT_HASH,
            "judge_model": CLAUDE_MODEL,
            "temperature": "unknown",
            "access_route": "anthropic_subagent",
            "cost_usd": "unknown",
            "result_file": "deleted",
            "net_overall": "unknown",
            "notes": "FINAL/README.md lists claude_judge_v014c_*.json as deleted; no such path in git history (unknown whether ever written)",
        }
    )
    return rows


def _worklog_only_rows() -> list[dict]:
    """Held-out runs described in WORKLOG that have no FINAL result file."""
    # Landing/fresh/WCXB/judge/retrieval all have files. Documentation corpus BM25 is explicitly
    # "not held out". No additional held-out WORKLOG-only run identified with evidence.
    return []


def main() -> None:
    main_final = _main_final()
    commits = _commits_oct2()
    # Also include freeze tip and morning commits for inference before Oct-2 17:14
    extra = []
    for h in ("2d436bb", "5ff8155", "b1432c3", "0652236", "f1523fe", "9b0afed", "d396e64"):
        iso = _git("log", "-1", "--format=%aI", h)
        subj = _git("log", "-1", "--format=%s", h)
        extra.append((h, datetime.fromisoformat(iso), subj))
    by_h = {h: (h, dt, s) for h, dt, s in commits}
    for h, dt, s in extra:
        by_h[h] = (h, dt, s)
    commits = sorted(by_h.values(), key=lambda r: r[1])

    rows = _file_rows(main_final, commits) + _deleted_rows(commits) + _worklog_only_rows()
    rows.sort(key=lambda r: (r["run_time"], r["result_file"], r["set"]))
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT_CSV} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
