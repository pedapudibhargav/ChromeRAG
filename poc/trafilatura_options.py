"""Reviewer-requested robustness rows: Trafilatura favor_recall / favor_precision on the WCXB test split (511 pages).

One pass over the 511 pages with Trafilatura 2.2.0 and the arguments of ``poc.revision_rows._trafilatura(meta=False)``
(Markdown, tables, no comments, no links, no metadata), plus ``favor_recall=True`` or ``favor_precision=True``.
The unmodified configuration is extracted in the same pass only as a reproduction check: its F1 must be 0.8596 and
match the saved P07 rows page by page, otherwise nothing is written. ChromeRAG balanced is read from the saved P07 rows
(front matter stripped, frozen 0.1.5); it is not run again.

Scores and intervals: same scorer and same paired site bootstrap as ``poc.revision_rows`` (registrable-domain sites,
5,000 draws, numpy default_rng(0)). Also tabulates the saved Trafilatura version files of the baseline reconciliation
(summaries only; those runs are not repeated).

  python -m poc.trafilatura_options run --outputs-dir <scratch dir> --out <json> [--wcxb-root <dir>]
  python -m poc.trafilatura_options ledger --result <json>
"""

from __future__ import annotations

import argparse
import importlib.metadata as md
import json
import platform
import sys
import time
import uuid
from multiprocessing import Pool
from pathlib import Path

from poc.revision_rows import (
    ROOT,
    base_report,
    compact,
    dir_digest,
    git_head,
    load_gt,
    now,
    paired,
    score_text,
    src_is_frozen,
    summarize,
    write_once,
)

P07_JSON = ROOT / "evaluations" / "2026-11-final" / "results" / "revision_rows" / "p07_front_matter.json"
LEDGER = ROOT / "evaluations" / "2026-11-final" / "results" / "held_out_runs.jsonl"
RECON = Path("evaluations") / "2026-11-baseline-reconciliation"
VERSIONS = ("1.12.2", "2.0.0", "2.1.0", "2.3.1")
BASE_KWARGS = {
    "include_tables": True,
    "include_comments": False,
    "include_links": False,
    "output_format": "markdown",
    "with_metadata": False,
}
CONFIGS = {
    "trafilatura_default_repro": {},
    "trafilatura_favor_recall": {"favor_recall": True},
    "trafilatura_favor_precision": {"favor_precision": True},
}
EXPECTED_DEFAULT_F1 = 0.8596
PURPOSE = "reviewer-requested robustness row: Trafilatura favor_recall / favor_precision"


def _extract(args: tuple) -> tuple[str, dict[str, str], dict[str, str]]:
    import trafilatura

    pid, html, url, out_root = args
    errors: dict[str, str] = {}
    texts = {}
    for name, extra in CONFIGS.items():
        try:
            text = trafilatura.extract(html, url=url, **BASE_KWARGS, **extra) or ""
        except Exception as exc:  # recorded, scored as empty output
            errors[name] = f"{type(exc).__name__}: {str(exc)[:120]}"
            text = ""
        texts[name] = text
        (Path(out_root) / name / f"{pid}.txt").write_text(text, encoding="utf-8")
    return pid, texts, errors


def version_table(root: Path) -> dict:
    """Summary numbers copied from the saved version files (no new extraction)."""
    rows = {}
    for split in ("test", "dev"):
        for v in VERSIONS:
            rel = RECON / f"wcxb_{split}_trafilatura-{v}.json"
            d = json.loads((root / rel).read_text(encoding="utf-8"))
            sets = d["sets"]
            key = next(k for k in sets if k.endswith("_all_with_reference"))
            s = sets[key]
            rows[f"{split}_{v}"] = {
                "file": str(rel),
                "split": split,
                "trafilatura": d["versions"]["trafilatura"],
                "n_pages": s["n"],
                "n_empty_reference": d.get("n_empty_reference"),
                "run_date": "2026-11-01 (file written 10:13 local; note in p0-02-baseline-reconciliation.md)",
                "code_tag": "upstream GitHub tag source on PYTHONPATH (PyPI blocked in that sandbox); "
                "dependency versions as in the file's versions field",
                "f1_repo_config": s["trafilatura_repo"]["f1_raw"],
                "f1_default_config": s["trafilatura_default"]["f1_raw"],
                "f1_favor_recall_default_args": s["trafilatura_favor_recall"]["f1_raw"],
                "f1_favor_precision_default_args": s["trafilatura_favor_precision"]["f1_raw"],
                "without_snippet_rate": None,
                "with_snippet_rate": None,
            }
    return rows


def cmd_run(args: argparse.Namespace) -> None:
    import trafilatura

    if md.version("trafilatura") != "2.2.0":
        raise SystemExit(f"trafilatura {md.version('trafilatura')} installed, 2.2.0 required")
    out = Path(args.outputs_dir)
    if out.exists():
        raise SystemExit(f"{out} exists: outputs are produced once")
    gt = load_gt(args.wcxb_root)
    if len(gt) != 511:
        raise SystemExit(f"{len(gt)} pages, expected 511")
    for name in CONFIGS:
        (out / name).mkdir(parents=True)
    from poc.wcxb import load_split

    pages = load_split("test", root=args.wcxb_root)
    started = now()
    t0 = time.time()
    with Pool(args.workers) as pool:
        res = pool.map(_extract, [(p.id, p.html, p.url, str(out)) for p in pages], chunksize=4)
    seconds = round(time.time() - t0, 1)
    errors = {pid: e for pid, _, e in res if e}
    err_counts = {n: sum(n in e for e in errors.values()) for n in CONFIGS}

    saved = {r["id"]: r for r in json.loads(P07_JSON.read_text(encoding="utf-8"))["rows"]}
    rows = []
    for page in gt:
        row = {"id": page["id"], "type": page["type"], "site": page["site"]}
        for name in CONFIGS:
            text = (out / name / f"{page['id']}.txt").read_text(encoding="utf-8")
            row[name] = score_text(text, page)
        s = saved[page["id"]]
        keep = ("p", "r", "f1", "without", "with")
        row["chromerag_balanced"] = {k: s["chromerag_balanced"][k] for k in keep} | {"empty": False}
        row["saved_default"] = {k: s["trafilatura"][k] for k in keep} | {"empty": False}
        rows.append(row)

    summary = {t: summarize(rows, t) for t in (*CONFIGS, "chromerag_balanced")}
    # saved rows carry no empty flag: take the empty-output count from the saved P07 summary
    summary["chromerag_balanced"]["empty_outputs"] = json.loads(P07_JSON.read_text(encoding="utf-8"))["summary"][
        "chromerag_balanced"
    ]["empty_outputs"]
    gate_f1 = round(summary["trafilatura_default_repro"]["f1"], 4)
    gate_pages = sum(abs(r["trafilatura_default_repro"]["f1"] - r["saved_default"]["f1"]) > 1e-5 for r in rows)
    gate = {
        "default_f1": gate_f1,
        "expected": EXPECTED_DEFAULT_F1,
        "pages_differing_from_saved_p07": gate_pages,
        "balanced_f1": round(summary["chromerag_balanced"]["f1"], 4),
    }
    if gate_f1 != EXPECTED_DEFAULT_F1 or gate_pages or gate["balanced_f1"] != 0.8839:
        print(json.dumps({"GATE_FAILED": gate, "seconds": seconds, "errors": err_counts}, indent=1))
        raise SystemExit("reproduction check failed: nothing written")

    new = ("trafilatura_favor_recall", "trafilatura_favor_precision")
    pairs = {}
    for t in new:
        pairs[f"balanced_minus_{t}"] = paired(rows, "chromerag_balanced", t)
        pairs[f"{t}_minus_default_trafilatura_2_2_0"] = paired(rows, t, "trafilatura_default_repro")
    report = base_report("Trafilatura favor_recall / favor_precision (reviewer-requested)", None) | {
        "config": {
            "base_arguments": {k: v for k, v in BASE_KWARGS.items()} | {"url": "<page url>"},
            "variants": {n: CONFIGS[n] for n in new},
            "same_arguments_as": "poc.revision_rows._trafilatura(html, url, meta=False)",
            "balanced": "ChromeRAG 0.1.5 balanced, front matter stripped, read from the saved P07 rows (not rerun)",
            "default_trafilatura_2_2_0": "reproduction check in the same pass; equals saved P07 rows page by page",
        },
        "versions": {
            "trafilatura": trafilatura.__version__
            if hasattr(trafilatura, "__version__")
            else md.version("trafilatura"),
            "lxml": md.version("lxml"),
            "python": platform.python_version(),
        },
        "extraction": {
            "started": started,
            "seconds_all_three_configs_one_pass": seconds,
            "workers": args.workers,
            "note": "wall time of one parallel pass over three configurations; not a speed measurement",
            "output_digests": {n: dir_digest(out / n) for n in CONFIGS},
        },
        "reproduction_check": gate,
        "n_pages": len(rows),
        "n_sites": len({r["site"] for r in rows}),
        "error_count": err_counts,
        "errors": errors,
        "src_equals_freeze_0_1_5": src_is_frozen(),
        "code_commit": git_head(),
        "summary": {t: summary[t] for t in (*new, "trafilatura_default_repro", "chromerag_balanced")},
        "paired": pairs,
        "version_table": version_table(args.recon_root),
        "version_table_note": "F1 is the word-F1 mean over the 511-page test split (1,495 dev pages for dev rows) "
        "from the saved summaries, same tokenizer as poc.wcxb.word_f1; the version files hold no snippet rates. "
        "Config columns: repo = Markdown, tables, no comments, no links; default = library default; favor_* in the "
        "version files use default arguments (plain text), not the repo arguments used for the new rows. "
        "Not used: wcxb_test_trafilatura-2.2.0_chromerag-0.1.4.json (void run).",
        "rows": compact(rows, [*new, "trafilatura_default_repro", "chromerag_balanced"]),
    }
    write_once(Path(args.out), report)
    print(json.dumps({k: report[k] for k in ("reproduction_check", "error_count", "summary", "paired")}, indent=1))


def cmd_ledger(args: argparse.Namespace) -> None:
    res = json.loads(Path(args.result).read_text(encoding="utf-8"))
    rows = []
    for t, label in (
        ("trafilatura_favor_recall", "favor_recall=True"),
        ("trafilatura_favor_precision", "favor_precision=True"),
    ):
        rows.append(
            {
                "run_id": uuid.uuid4().hex,
                "set": "wcxb_test",
                "n": res["n_pages"],
                "date_time": now(),
                "purpose": f"{PURPOSE} ({label}); scored once",
                "commit": f"{res['code_commit'][:7]}; src identical to tag freeze-0.1.5 (checked by the script); "
                "Trafilatura 2.2.0, repo arguments (Markdown, tables, no comments, no links, no metadata)",
                "tools": {"trafilatura": res["versions"]["trafilatura"], "python": res["versions"]["python"]},
                "read_afterwards": "aggregate tables only (means, paired interval bounds); no page text read",
                "result_file": "evaluations/2026-11-final/results/revision_rows/trafilatura_options.json",
            }
        )
    with LEDGER.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps([r["run_id"] for r in rows]))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--wcxb-root", type=Path, default=ROOT / "data" / "wcxb")
    r.add_argument(
        "--recon-root",
        type=Path,
        required=True,
        help="directory that holds evaluations/2026-11-baseline-reconciliation",
    )
    r.add_argument("--outputs-dir", type=Path, required=True)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--workers", type=int, default=8)
    g = sub.add_parser("ledger")
    g.add_argument("--result", type=Path, required=True)
    args = ap.parse_args(argv)
    {"run": cmd_run, "ledger": cmd_ledger}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
