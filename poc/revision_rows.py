"""Revision 1 result rows on the WCXB test split (511 pages), frozen 0.1.5; each result is produced once.

Steps (outputs are saved once, then each result file is scored from them):

  extract      all local tools on the 511 pages with the frozen tree; saves one text per tool and page
  extract-old  ChromeRAG pipeline code of tag freeze-0.1.3 with the 0.1.5 model file; run with
               PYTHONPATH=<exported freeze-0.1.3 src whose assets/lbc_stage1.npz is the 0.1.5 file>:<repo>
  p07          front matter: ChromeRAG output as emitted and stripped; Trafilatura with and without metadata
  p03          372-page set, domains absent from the original dev folder, page types, with-snippet rate,
               freeze-0.1.3 code with the 0.1.5 model
  justext      jusText 3.0.2 (P13)
  boilerpy3    BoilerPy3 outputs made in CI (P13), scored here
  speed        single-process warm timing on this machine
  gt-manifest  sha256 of the local test ground truth and HTML, to compare with an upstream copy

Scores: ``poc.wcxb.word_f1`` and ``snippet_rate`` (same tokenizer and rules as the benchmark's evaluate.py).
Intervals: paired, sites resampled with replacement (registrable domain), 5,000 draws, numpy seed 0, as in
``poc/final_wcxb.py``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path
from urllib.parse import urlparse

import numpy as np

from poc.psl import registrable_domain
from poc.wcxb import load_split, snippet_rate, strip_front_matter, word_f1

ROOT = Path(__file__).resolve().parents[1]
FINAL_JSON = ROOT / "evaluations" / "2026-11-final" / "results" / "wcxb_test" / "wcxb_test.json"
LEAKED = ROOT / "poc" / "wcxb_leaked_ids.json"
MODES = ("balanced", "precision", "coverage")
MAIN_TOOLS = (
    "chromerag_balanced_raw",
    "chromerag_precision_raw",
    "chromerag_coverage_raw",
    "trafilatura",
    "trafilatura_meta",
    "readability",
    "markitdown",
    "justext",
)
_FM = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_KEY = re.compile(r"^([A-Za-z_][\w-]*):", re.MULTILINE)


def site_of(url: str) -> str:
    """Same as ``poc.learn_tokens.cv_site_of`` without importing the package (extract-old runs on old code)."""
    dom = registrable_domain(url)
    return dom if dom else urlparse(url).netloc.lower().removeprefix("www.")


def shown_path(path: Path) -> str:
    """Path inside this repository, or inside the exported freeze-0.1.3 tree; never a machine-specific prefix."""
    path = Path(path).resolve()
    if ROOT in path.parents:
        return str(path.relative_to(ROOT))
    parts = path.parts
    return "<freeze-0.1.3 export>/" + "/".join(parts[parts.index("src") :]) if "src" in parts else path.name


def git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def src_is_frozen() -> bool:
    return subprocess.call(["git", "diff", "--quiet", "freeze-0.1.5", "--", "src", "pyproject.toml"], cwd=ROOT) == 0


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dir_digest(path: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(path.glob("*.txt")):
        h.update(f.name.encode())
        h.update(hashlib.sha256(f.read_bytes()).digest())
    return h.hexdigest()


def write_once(path: Path, data: dict) -> None:
    if path.exists():
        raise SystemExit(f"{path} exists: each result is produced once")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def front_keys(text: str) -> tuple[list[str], int]:
    """Keys and word count of a leading YAML block (empty when there is none)."""
    m = _FM.match(text)
    if not m:
        return [], 0
    return _KEY.findall(m.group(1)), len(re.findall(r"\w+", m.group(1)))


# ---------------------------------------------------------------- extraction


def _justext(html: str) -> str:
    import justext

    paras = justext.justext(html, justext.get_stoplist("English"))
    return "\n\n".join(p.text for p in paras if not p.is_boilerplate)


def _trafilatura(html: str, url: str, meta: bool) -> str:
    import trafilatura

    out = trafilatura.extract(
        html,
        url=url,
        include_tables=True,
        include_comments=False,
        include_links=False,
        output_format="markdown",
        with_metadata=meta,
    )
    return out or ""


def run_main_tool(tool: str, html: str, url: str) -> str:
    if tool.startswith("chromerag_"):
        from chromerag import ChromeRAG
        from chromerag.config import PipelineConfig

        mode = tool.split("_")[1]
        return ChromeRAG(config=PipelineConfig.from_priority(mode)).extract(html, url=url).markdown
    if tool == "trafilatura":
        return _trafilatura(html, url, False)
    if tool == "trafilatura_meta":
        return _trafilatura(html, url, True)
    if tool == "readability":
        from poc.baselines import baseline_readability

        return baseline_readability(html)
    if tool == "markitdown":
        from poc.baselines import baseline_markitdown

        return baseline_markitdown(html)
    if tool == "justext":
        return _justext(html)
    raise ValueError(tool)


def _extract_page(args: tuple) -> dict:
    pid, html, url, tools, out_root = args
    row: dict = {"id": pid}
    for tool in tools:
        try:
            text = run_main_tool(tool, html, url)
        except Exception as exc:  # recorded, scored as empty output
            row.setdefault("errors", {})[tool] = f"{type(exc).__name__}: {str(exc)[:120]}"
            text = ""
        (Path(out_root) / tool / f"{pid}.txt").write_text(text, encoding="utf-8")
    return row


def cmd_extract(args: argparse.Namespace, *, old: bool) -> None:
    import chromerag

    src = Path(chromerag.__file__).resolve()
    if old:
        expect = Path(args.expect_src).resolve()
        if expect not in src.parents:
            raise SystemExit(f"chromerag imported from {src}, expected under {expect}")
        tools = tuple(f"chromerag_{m}_raw" for m in MODES)
    else:
        if (ROOT / "src") not in src.parents:
            raise SystemExit(f"chromerag imported from {src}, not this tree")
        if not src_is_frozen():
            raise SystemExit("src differs from freeze-0.1.5")
        tools = MAIN_TOOLS
    import chromerag.lbc as lbc

    model = Path(lbc.MODEL_PATH)
    out = Path(args.outputs_dir)
    if out.exists():
        raise SystemExit(f"{out} exists: outputs are produced once")
    for t in tools:
        (out / t).mkdir(parents=True)
    pages = load_split("test", root=args.wcxb_root)
    started = now()
    t0 = time.time()
    with Pool(args.workers) as pool:
        rows = pool.map(_extract_page, [(p.id, p.html, p.url, tools, str(out)) for p in pages], chunksize=4)
    versions = {"chromerag": chromerag.__version__, "python": platform.python_version()}
    if not old:
        import importlib.metadata as md

        for dist in ("trafilatura", "readability-lxml", "markitdown", "justext", "lxml"):
            versions[dist] = md.version(dist)
    meta = {
        "started": started,
        "finished": now(),
        "seconds": round(time.time() - t0, 1),
        "pages": len(rows),
        "tools": list(tools),
        "chromerag_file": shown_path(src),
        "model_file": shown_path(model),
        "model_sha256": sha256_file(model),
        "repo_head": git_head(),
        "src_equals_freeze_0_1_5": None if old else True,
        "versions": versions,
        "errors": {r["id"]: r["errors"] for r in rows if r.get("errors")},
        "output_digests": {t: dir_digest(out / t) for t in tools},
        "workers": args.workers,
    }
    (out / "_run.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps({k: meta[k] for k in ("started", "seconds", "pages", "model_sha256", "errors")}, indent=1))


# ---------------------------------------------------------------- scoring helpers


def load_gt(root: Path) -> list[dict]:
    pages = load_split("test", root=root)
    return [
        {
            "id": p.id,
            "url": p.url,
            "type": p.page_type,
            "site": site_of(p.url),
            "ref": p.main_content,
            "with": p.with_snippets,
            "without": p.without_snippets,
        }
        for p in pages
    ]


def score_text(text: str, page: dict) -> dict:
    p, r, f1 = word_f1(text, page["ref"])
    return {
        "p": p,
        "r": r,
        "f1": f1,
        "without": snippet_rate(text, page["without"]),
        "with": snippet_rate(text, page["with"]),
        "empty": not text.strip(),
    }


def read_text(path: Path) -> str | None:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else None


def site_boot(values: list[float], sites: list[str]) -> dict:
    """Mean over pages and percentile interval from resampling sites (as in poc/final_wcxb.py)."""
    by_site: dict[str, list[float]] = {}
    for v, s in zip(values, sites):
        by_site.setdefault(s, []).append(v)
    weights = np.array([len(v) for v in by_site.values()])
    sums = np.array([sum(v) for v in by_site.values()])
    rng = np.random.default_rng(0)
    n = len(weights)
    samples = [sums[ix].sum() / weights[ix].sum() for ix in (rng.integers(0, n, n) for _ in range(5000))]
    return {
        "mean": float(sums.sum() / weights.sum()),
        "ci95": [float(x) for x in np.percentile(samples, [2.5, 97.5])],
        "n_pages": int(weights.sum()),
        "n_sites": n,
    }


def summarize(rows: list[dict], tool: str) -> dict:
    vals = [r[tool] for r in rows]
    out = {k: float(np.mean([v[k] for v in vals])) for k in ("p", "r", "f1", "without", "with")}
    out["under_0_1"] = sum(v["f1"] < 0.1 for v in vals)
    out["empty_outputs"] = sum(v["empty"] for v in vals)
    out["n"] = len(vals)
    return out


def paired(rows: list[dict], a: str, b: str, keys=("f1", "without", "with")) -> dict:
    sites = [r["site"] for r in rows]
    return {k: site_boot([r[a][k] - r[b][k] for r in rows], sites) for k in keys}


def run_meta(outputs_dir: Path) -> dict:
    return json.loads((outputs_dir / "_run.json").read_text(encoding="utf-8"))


def scored_rows(gt: list[dict], sources: dict[str, Path], transform: dict | None = None) -> list[dict]:
    """One row per page with a score for every source directory (missing file: scored as empty, flagged)."""
    transform = transform or {}
    rows = []
    for page in gt:
        row = {"id": page["id"], "type": page["type"], "site": page["site"]}
        for name, directory in sources.items():
            text = read_text(directory / f"{page['id']}.txt")
            if text is None:
                row.setdefault("missing", []).append(name)
                text = ""
            text = transform.get(name, lambda t: t)(text)
            row[name] = score_text(text, page)
        rows.append(row)
    return rows


def compact(rows: list[dict], tools: list[str]) -> list[dict]:
    keep = ("p", "r", "f1", "without", "with")
    return [
        {"id": r["id"], "type": r["type"], "site": r["site"]}
        | {t: {k: round(r[t][k], 6) for k in keep} for t in tools}
        | ({"missing": r["missing"]} if r.get("missing") else {})
        for r in rows
    ]


def parity_with_final(rows: list[dict], mapping: dict[str, str]) -> dict:
    """Pages whose F1 or without rate differs from the saved final run (wcxb_test.json)."""
    saved = {r["id"]: r for r in json.loads(FINAL_JSON.read_text(encoding="utf-8"))["rows"]}
    out = {}
    for mine, theirs in mapping.items():
        diff = [
            max(
                abs(r[mine]["f1"] - saved[r["id"]][theirs]["f1"]),
                abs(r[mine]["without"] - saved[r["id"]][theirs]["without"]),
            )
            for r in rows
        ]
        out[mine] = {"pages_differing": sum(d > 1e-9 for d in diff), "max_abs_diff": float(max(diff))}
    site_mismatch = sum(r["site"] != saved[r["id"]]["site"] for r in rows)
    out["site_grouping_mismatches"] = site_mismatch
    return out


def base_report(kind: str, outputs: Path | None) -> dict:
    return {
        "result": kind,
        "scored": now(),
        "repo_head": git_head(),
        "src_equals_freeze_0_1_5": src_is_frozen(),
        "set": "WCXB test split, local copy data/wcxb/test",
        "extraction_run": run_meta(outputs) if outputs else None,
        "scorer": "poc.wcxb.word_f1 and snippet_rate (tokenizer \\w+ lower-cased; same as data/wcxb/evaluate.py)",
        "interval_method": "paired difference per page; sites (registrable domain, poc.psl) resampled with "
        "replacement; 5,000 draws; numpy default_rng(0); 2.5 and 97.5 percentiles",
    }


# ---------------------------------------------------------------- P07


def cmd_p07(args: argparse.Namespace) -> None:
    out_dir = Path(args.outputs_dir)
    gt = load_gt(args.wcxb_root)
    sources = {}
    transform = {}
    for m in MODES:
        sources[f"chromerag_{m}_raw"] = out_dir / f"chromerag_{m}_raw"
        sources[f"chromerag_{m}"] = out_dir / f"chromerag_{m}_raw"
        transform[f"chromerag_{m}"] = strip_front_matter
    sources["trafilatura"] = out_dir / "trafilatura"
    sources["trafilatura_meta_raw"] = out_dir / "trafilatura_meta"
    sources["trafilatura_meta_stripped"] = out_dir / "trafilatura_meta"
    transform["trafilatura_meta_stripped"] = strip_front_matter
    rows = scored_rows(gt, sources, transform)

    # what each tool puts in front of the body, counted over the 511 outputs (keys only; values not read)
    fm: dict[str, dict] = {}
    for name, sub in (
        ("chromerag_balanced", "chromerag_balanced_raw"),
        ("chromerag_precision", "chromerag_precision_raw"),
        ("chromerag_coverage", "chromerag_coverage_raw"),
        ("trafilatura_meta", "trafilatura_meta"),
        ("trafilatura", "trafilatura"),
    ):
        keys: dict[str, int] = {}
        words = []
        with_block = 0
        for page in gt:
            k, w = front_keys(read_text(out_dir / sub / f"{page['id']}.txt") or "")
            with_block += bool(k)
            words.append(w)
            for key in k:
                keys[key] = keys.get(key, 0) + 1
        fm[name] = {
            "pages_with_front_matter": with_block,
            "key_counts": dict(sorted(keys.items(), key=lambda kv: -kv[1])),
            "mean_front_matter_words": float(np.mean(words)),
        }
    same_body = sum(
        strip_front_matter(read_text(out_dir / "trafilatura_meta" / f"{p['id']}.txt") or "").strip()
        == (read_text(out_dir / "trafilatura" / f"{p['id']}.txt") or "").strip()
        for p in gt
    )
    tools = list(sources)
    report = base_report("P07 front-matter symmetric reporting", out_dir) | {
        "n": len(rows),
        "summary": {t: summarize(rows, t) for t in tools},
        "paired": {
            "balanced_raw_minus_balanced_stripped": paired(rows, "chromerag_balanced_raw", "chromerag_balanced"),
            "precision_raw_minus_precision_stripped": paired(rows, "chromerag_precision_raw", "chromerag_precision"),
            "coverage_raw_minus_coverage_stripped": paired(rows, "chromerag_coverage_raw", "chromerag_coverage"),
            "trafilatura_meta_raw_minus_trafilatura": paired(rows, "trafilatura_meta_raw", "trafilatura"),
            "trafilatura_meta_stripped_minus_trafilatura": paired(rows, "trafilatura_meta_stripped", "trafilatura"),
            "balanced_stripped_minus_trafilatura (primary, both without metadata)": paired(
                rows, "chromerag_balanced", "trafilatura"
            ),
            "balanced_raw_minus_trafilatura_meta_raw (both with metadata)": paired(
                rows, "chromerag_balanced_raw", "trafilatura_meta_raw"
            ),
            "balanced_raw_minus_trafilatura (as shipped by default)": paired(
                rows, "chromerag_balanced_raw", "trafilatura"
            ),
        },
        "front_matter": fm,
        "trafilatura_meta_body_equal_to_without_metadata_pages": same_body,
        "parity_with_final_run": parity_with_final(
            rows,
            {
                "chromerag_balanced": "chromerag",
                "chromerag_precision": "chromerag_precision",
                "chromerag_coverage": "chromerag_coverage",
                "trafilatura": "trafilatura",
            },
        ),
        "note": (
            "Default API and CLI output are the same: `chromerag extract page.html --url URL` writes "
            "ExtractResult.markdown, and the CLI config equals PipelineConfig.from_priority(mode) (checked). "
            "ChromeRAG front matter (enable_schema=True, default) is a YAML block between --- lines built by "
            "schema_fusion.fuse_front_matter: url (the url argument), title (<title>, else og:title; replaced by "
            "a JSON-LD/microdata headline or name), description (meta description, replaced by Schema.org "
            "description), type (Schema.org @type of the main node), lastUpdated (dateModified, datePublished or "
            "lastUpdated), author (Schema.org author name) and breadcrumb (JSON-LD BreadcrumbList names joined "
            "by ' > '). Trafilatura 2.2.0 with with_metadata=True and output_format='markdown' prepends its own "
            "YAML block; keys seen on these pages (counts in front_matter.trafilatura_meta): url, hostname, "
            "sitename, title, date, description, author, tags, categories, license, each only when found. "
            "Without metadata Trafilatura emits no block. ChromeRAG emits its block even when the body is "
            "empty, so raw output is never empty. 'raw' scores the text as emitted; 'stripped' "
            "removes one leading YAML block with the regex of poc.wcxb.strip_front_matter (the method of the "
            "final run). The WCXB reference holds body text only, so metadata words count against precision. "
            "Trafilatura settings otherwise as poc/baselines.py (tables on, comments and links off, url given)."
        ),
        "rows": compact(rows, tools),
    }
    write_once(Path(args.out), report)
    print(json.dumps({k: report[k] for k in ("summary", "paired", "front_matter", "parity_with_final_run")}, indent=1))


# ---------------------------------------------------------------- P03


def dev_domains(root: Path) -> tuple[set[str], int, int, set[str]]:
    """Registrable domains of every file in the original dev/ folder, with and without the 139 leaked ids."""
    leaked = set(json.loads(LEAKED.read_text(encoding="utf-8")))
    doms: set[str] = set()
    doms_no_leak: set[str] = set()
    files = no_url = 0
    for f in sorted((Path(root) / "dev" / "ground-truth").glob("*.json")):
        files += 1
        url = json.loads(f.read_text(encoding="utf-8")).get("url") or ""
        if not url:
            no_url += 1
            continue
        d = site_of(url)
        doms.add(d)
        if f.stem not in leaked:
            doms_no_leak.add(d)
    return doms, files, no_url, doms_no_leak


def all_sources(args: argparse.Namespace) -> tuple[dict, dict]:
    out_dir = Path(args.outputs_dir)
    sources = {
        "chromerag_balanced": out_dir / "chromerag_balanced_raw",
        "chromerag_precision": out_dir / "chromerag_precision_raw",
        "chromerag_coverage": out_dir / "chromerag_coverage_raw",
        "trafilatura": out_dir / "trafilatura",
        "readability": out_dir / "readability",
        "markitdown": out_dir / "markitdown",
        "justext": out_dir / "justext",
        "rs_trafilatura": Path(args.rs_dir),
        "boilerpy3_default": Path(args.boilerpy3_dir) / "default",
        "boilerpy3_article": Path(args.boilerpy3_dir) / "article",
    }
    transform = {k: strip_front_matter for k in ("chromerag_balanced", "chromerag_precision", "chromerag_coverage")}
    return sources, transform


def cmd_p03(args: argparse.Namespace) -> None:
    out_dir = Path(args.outputs_dir)
    old_dir = Path(args.old_outputs_dir)
    gt = load_gt(args.wcxb_root)
    sources, transform = all_sources(args)
    for m in MODES:
        sources[f"old013_{m}"] = old_dir / f"chromerag_{m}_raw"
        transform[f"old013_{m}"] = strip_front_matter
    rows = scored_rows(gt, sources, transform)
    tools = list(sources)
    leaked = set(json.loads(LEAKED.read_text(encoding="utf-8")))
    doms, dev_files, dev_no_url, doms_no_leak = dev_domains(args.wcxb_root)
    by_id = {p["id"]: p for p in gt}

    def block(sub: list[dict], extra_pairs=()) -> dict:
        pairs = {"balanced_minus_trafilatura": paired(sub, "chromerag_balanced", "trafilatura")}
        for a, b in extra_pairs:
            pairs[f"{a}_minus_{b}"] = paired(sub, a, b)
        return {
            "n": len(sub),
            "n_sites": len({r["site"] for r in sub}),
            "types": {t: sum(r["type"] == t for r in sub) for t in sorted({r["type"] for r in sub})},
            "summary": {t: summarize(sub, t) for t in tools},
            "paired": pairs,
        }

    clean = [r for r in rows if r["id"] not in leaked]
    absent = [r for r in rows if by_id[r["id"]]["url"] and r["site"] not in doms]
    absent_alt = [r for r in rows if by_id[r["id"]]["url"] and r["site"] not in doms_no_leak]
    per_type = {}
    for t in sorted({r["type"] for r in rows}):
        sub = [r for r in rows if r["type"] == t]
        sites = [r["site"] for r in sub]
        per_type[t] = {
            "n": len(sub),
            "n_sites": len(set(sites)),
            "mean_f1": {tool: float(np.mean([r[tool]["f1"] for r in sub])) for tool in tools},
            "balanced_f1": site_boot([r["chromerag_balanced"]["f1"] for r in sub], sites),
            "trafilatura_f1": site_boot([r["trafilatura"]["f1"] for r in sub], sites),
            "balanced_minus_trafilatura_f1": site_boot(
                [r["chromerag_balanced"]["f1"] - r["trafilatura"]["f1"] for r in sub], sites
            ),
        }
    old_meta = run_meta(old_dir)
    report = base_report("P03 extra rows on the WCXB test split", out_dir) | {
        "old_code_extraction_run": old_meta,
        "rs_trafilatura_source": "saved outputs of CI run 41339838506 (rs-trafilatura 0.1.1, main_content only); "
        "re-scored here, no new extraction",
        "boilerpy3_source": "CI run 44817203676, boilerpy3 1.0.7; see boilerpy3 result file",
        "all_511": block(
            rows,
            (
                ("chromerag_balanced", "old013_balanced"),
                ("old013_balanced", "trafilatura"),
                ("rs_trafilatura", "chromerag_balanced"),
            ),
        ),
        "i_clean_372": block(clean)
        | {
            "definition": "511 test pages minus the 139 ids also present in the public dev/ folder "
            "(poc/wcxb_leaked_ids.json); the primary set of the v0.1.4 manuscript"
        },
        "ii_domain_absent_from_original_dev": block(absent)
        | {
            "definition": "test pages with a URL whose registrable domain (poc.psl, as for the strict split) is not "
            "the domain of any file in the original dev/ folder (all files, including the 139 duplicates of test "
            "pages)",
            "dev_files": dev_files,
            "dev_files_without_url_not_checked": dev_no_url,
            "dev_domains": len(doms),
            "test_pages_without_url_excluded": sum(1 for p in gt if not p["url"]),
            "alternative_count_dev_without_139_duplicates": len(absent_alt),
        },
        "iii_per_type": per_type,
        "iv_with_snippet_rate_all_511": {t: summarize(rows, t)["with"] for t in tools},
        "v_freeze_0_1_3_code_with_0_1_5_model": {
            "runnable": True,
            "how": "git archive freeze-0.1.3 src, then assets/lbc_stage1.npz replaced by the 0.1.5 file (sha256 "
            "2e2fecb9...); no code edited. The 0.1.3 loader reads the same npz keys; feature count 535 in both, "
            "FEATURE_NAMES identical; the 0.1.3 package reports __version__ 0.1.2 (unchanged at that tag).",
            "summary": {m: summarize(rows, f"old013_{m}") for m in MODES},
        },
        "parity_with_final_run": parity_with_final(
            rows,
            {
                "chromerag_balanced": "chromerag",
                "chromerag_precision": "chromerag_precision",
                "chromerag_coverage": "chromerag_coverage",
                "trafilatura": "trafilatura",
                "readability": "readability",
                "markitdown": "markitdown",
            },
        ),
        "note": "ChromeRAG scored with front matter stripped (the final run's method). Missing output files are "
        "scored as empty and listed per row. An empty snippet list scores 1.0, as in the benchmark.",
        "rows": compact(rows, tools),
    }
    write_once(Path(args.out), report)
    show = {k: report[k] for k in ("iv_with_snippet_rate_all_511", "parity_with_final_run")}
    for k in ("all_511", "i_clean_372", "ii_domain_absent_from_original_dev"):
        show[k] = {
            "n": report[k]["n"],
            "f1": {t: round(v["f1"], 4) for t, v in report[k]["summary"].items()},
            "paired": report[k]["paired"],
        }
    show["ii_extra"] = {
        k: v for k, v in report["ii_domain_absent_from_original_dev"].items() if not isinstance(v, dict)
    }
    show["iii"] = {
        t: {k: v[k] for k in ("n", "n_sites", "balanced_f1", "trafilatura_f1", "balanced_minus_trafilatura_f1")}
        for t, v in per_type.items()
    }
    print(json.dumps(show, indent=1))


# ---------------------------------------------------------------- P13


def _single_tool(args: argparse.Namespace, kind: str, tool_sources: dict[str, Path], extra: dict) -> None:
    out_dir = Path(args.outputs_dir)
    gt = load_gt(args.wcxb_root)
    sources = {"chromerag_balanced": out_dir / "chromerag_balanced_raw", "trafilatura": out_dir / "trafilatura"}
    sources |= tool_sources
    rows = scored_rows(gt, sources, {"chromerag_balanced": strip_front_matter})
    tools = list(sources)
    pairs = {}
    for t in tool_sources:
        pairs[f"balanced_minus_{t}"] = paired(rows, "chromerag_balanced", t)
        pairs[f"trafilatura_minus_{t}"] = paired(rows, "trafilatura", t)
    per_type = {
        ty: {
            "n": sum(r["type"] == ty for r in rows),
            "mean_f1": {t: float(np.mean([r[t]["f1"] for r in rows if r["type"] == ty])) for t in tools},
        }
        for ty in sorted({r["type"] for r in rows})
    }
    report = (
        base_report(kind, out_dir)
        | extra
        | {
            "n": len(rows),
            "summary": {t: summarize(rows, t) for t in tools},
            "paired": pairs,
            "per_type": per_type,
            "missing_outputs": sum(bool(r.get("missing")) for r in rows),
            "rows": compact(rows, tools),
        }
    )
    write_once(Path(args.out), report)
    print(json.dumps({k: report[k] for k in ("summary", "paired", "missing_outputs")}, indent=1))


def cmd_justext(args: argparse.Namespace) -> None:
    out_dir = Path(args.outputs_dir)
    _single_tool(
        args,
        "P13 jusText baseline",
        {"justext": out_dir / "justext"},
        {
            "note": "jusText 3.0.2, justext.justext(html, get_stoplist('English')) with default parameters; output "
            "is the text of paragraphs not classed as boilerplate, joined by blank lines. Same HTML string as the "
            "other tools. Heuristic (stop-word density and link density), not learned.",
        },
    )


def cmd_boilerpy3(args: argparse.Namespace) -> None:
    bp = Path(args.boilerpy3_dir)
    meta = json.loads((bp / "_meta.json").read_text(encoding="utf-8"))
    ci_ms = {
        k: {"median": statistics.median(v.values()), "p90": float(np.percentile(list(v.values()), 90))}
        for k, v in meta.get("ms", {}).items()
        if isinstance(v, dict) and v
    }
    _single_tool(
        args,
        "P13 BoilerPy3 baseline (outputs from CI, scored here)",
        {"boilerpy3_default": bp / "default", "boilerpy3_article": bp / "article"},
        {
            "provenance": {
                "ci_run": 44817203676,
                "repository": "pedapudibhargav/ChromeRAG, temporary branch ci/boilerpy3-wcxb",
                "runner": "ubuntu-24.04, Python 3.12",
                "boilerpy3": meta.get("boilerpy3"),
                "wcxb_upstream": "github.com/Murrough-Foley/web-content-extraction-benchmark at "
                "c039d5ee9f5a3a984a0e167e63aacd04e76e78a9",
                "artifact_sha256": "b8250240e1ba6b22ae65d4f0c21f0fb7ae1c52828e38d925d954f3402f7d9fbb",
                "ci_errors": meta.get("errors"),
                "output_digests": {k: dir_digest(bp / k) for k in ("default", "article")},
                "ci_ms_per_page_not_comparable_with_local_speed": ci_ms,
            },
            "note": "DefaultExtractor is the Kohlschuetter et al. (2010) shallow-text-feature classifier; "
            "ArticleExtractor is its news-article variant. Extracted in CI from the upstream HTML; scored here "
            "against the local ground truth with the same scorer as the other tools. Whether the upstream ground "
            "truth at that commit equals the local copy could not be checked offline; see ground_truth_check.",
            "ground_truth_check": "not verified: no upstream copy on this machine and no network. "
            "gt_manifest.json lists sha256 of every local test ground-truth file and HTML file for a CI comparison.",
        },
    )


# ---------------------------------------------------------------- speed


def cmd_speed(args: argparse.Namespace) -> None:
    import importlib.metadata as md

    import chromerag
    from chromerag import ChromeRAG
    from chromerag.config import PipelineConfig
    from poc.baselines import baseline_readability, baseline_trafilatura

    if (ROOT / "src") not in Path(chromerag.__file__).resolve().parents or not src_is_frozen():
        raise SystemExit("not the frozen tree")
    pages = load_split("test", root=args.wcxb_root)
    cr = ChromeRAG(config=PipelineConfig.from_priority("balanced"))
    tools = {
        "chromerag_balanced": lambda p: cr.extract(p.html, url=p.url).markdown,
        "trafilatura": lambda p: baseline_trafilatura(p.html, p.url),
        "readability": lambda p: baseline_readability(p.html),
        "justext": lambda p: _justext(p.html),
    }
    cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
    load_start = [round(x, 2) for x in os.getloadavg()]
    started = now()
    res = {}
    for name, fn in tools.items():
        for p in pages[: args.warmup]:
            try:
                fn(p)
            except Exception:
                pass
        ms = []
        errors = 0
        for p in pages:
            t0 = time.perf_counter()
            try:
                fn(p)
            except Exception:
                errors += 1
            ms.append((time.perf_counter() - t0) * 1000)
        res[name] = {
            "median_ms": statistics.median(ms),
            "p90_ms": float(np.percentile(ms, 90)),
            "p99_ms": float(np.percentile(ms, 99)),
            "mean_ms": statistics.fmean(ms),
            "max_ms": max(ms),
            "errors": errors,
            "ms_per_page": [round(x, 3) for x in ms],
        }
        print(name, round(res[name]["median_ms"], 1), round(res[name]["p90_ms"], 1), flush=True)
    report = {
        "result": "Speed, WCXB test split, 511 pages",
        "started": started,
        "finished": now(),
        "repo_head": git_head(),
        "src_equals_freeze_0_1_5": True,
        "load_average_at_start": load_start,
        "machine": {
            "cpu": cpu,
            "logical_cpus": os.cpu_count(),
            "os": platform.platform(),
            "python": platform.python_version(),
        },
        "versions": {
            "chromerag": chromerag.__version__,
            "trafilatura": md.version("trafilatura"),
            "readability-lxml": md.version("readability-lxml"),
            "justext": md.version("justext"),
            "lxml": md.version("lxml"),
        },
        "method": f"one process, tools one after another; each tool first runs untimed on the first {args.warmup} "
        "pages (warm-up), then one timed pass over all 511 pages in id order; time.perf_counter around the "
        "extraction call only (HTML already decoded in memory; ChromeRAG instance built once; url given to "
        "ChromeRAG and Trafilatura). ChromeRAG output includes front matter (default). No other job from "
        "this harness ran; other processes on the machine did (see load_average_at_start).",
        "tools": res,
    }
    write_once(Path(args.out), report)


# ---------------------------------------------------------------- ground truth manifest


def cmd_gt_manifest(args: argparse.Namespace) -> None:
    root = Path(args.wcxb_root) / "test"
    files = {}
    for f in sorted((root / "ground-truth").glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        mc = (data.get("ground_truth") or {}).get("main_content") or ""
        html = root / "html" / f"{f.stem}.html.gz"
        files[f.stem] = {
            "ground_truth_json_sha256": sha256_file(f),
            "main_content_sha256": hashlib.sha256(mc.encode("utf-8")).hexdigest(),
            "html_gz_sha256": sha256_file(html) if html.exists() else None,
            "html_sha256": hashlib.sha256(gzip.open(html).read()).hexdigest() if html.exists() else None,
        }
    agg = hashlib.sha256("".join(f"{k}{v['main_content_sha256']}" for k, v in files.items()).encode()).hexdigest()
    write_once(
        Path(args.out),
        {
            "result": "sha256 manifest of the local WCXB test split (data/wcxb/test)",
            "made": now(),
            "files": len(files),
            "aggregate_main_content_sha256": agg,
            "aggregate_rule": "sha256 of the concatenation of id + main_content_sha256 in id order",
            "per_file": files,
        },
    )
    print(len(files), agg)


# ---------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("extract", "extract-old", "p07", "p03", "justext", "boilerpy3", "speed", "gt-manifest"):
        p = sub.add_parser(name)
        p.add_argument("--wcxb-root", type=Path, default=ROOT / "data" / "wcxb")
        if name in ("extract", "extract-old"):
            p.add_argument("--outputs-dir", type=Path, required=True)
            p.add_argument("--workers", type=int, default=12)
            if name == "extract-old":
                p.add_argument("--expect-src", type=Path, required=True)
            continue
        p.add_argument("--out", type=Path, required=True)
        if name in ("p07", "p03", "justext", "boilerpy3"):
            p.add_argument("--outputs-dir", type=Path, required=True)
        if name in ("p03", "boilerpy3"):
            p.add_argument("--boilerpy3-dir", type=Path, required=True)
        if name == "p03":
            p.add_argument("--old-outputs-dir", type=Path, required=True)
            p.add_argument("--rs-dir", type=Path, required=True)
        if name == "speed":
            p.add_argument("--warmup", type=int, default=25)
    args = ap.parse_args(argv)
    {
        "extract": lambda a: cmd_extract(a, old=False),
        "extract-old": lambda a: cmd_extract(a, old=True),
        "p07": cmd_p07,
        "p03": cmd_p03,
        "justext": cmd_justext,
        "boilerpy3": cmd_boilerpy3,
        "speed": cmd_speed,
        "gt-manifest": cmd_gt_manifest,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
