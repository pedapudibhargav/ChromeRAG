"""Run all pinned extractors on a page set with caching and freeze guard."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
import uuid
from concurrent.futures import ProcessPoolExecutor
from importlib import metadata
from pathlib import Path

from chromerag import ChromeRAG, ContentPriority, PipelineConfig
from poc.baselines import BASELINES
from poc.wcxb import strip_front_matter, word_f1

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "evaluations" / "2026-11-final"
CACHE_DIR = EVAL_DIR / "cache"
RESULTS_DIR = EVAL_DIR / "results"
STRICT_MANIFEST = ROOT / "evaluations" / "2026-10-v0.1.3" / "strict_split_manifest.json"
MODEL_PATH = ROOT / "src" / "chromerag" / "assets" / "lbc_stage1.npz"
HELD_OUT_LEDGER = EVAL_DIR / "results" / "held_out_runs.jsonl"

REQUIRED_TAG = "freeze-0.1.5"
RS_TRAFILATURA_CI_VERSION = "0.1.1"

HELD_OUT_SETS = frozenset({"wcxb_test", "crag_split1", "new_pages"})
HELD_OUT_DIR_NAMES = frozenset({"final", "wcxb_test", "crag_split1", "new_pages"})

TOOL_CHROMERAG = {
    "chromerag_coverage": ContentPriority.COVERAGE,
    "chromerag": ContentPriority.BALANCED,
    "chromerag_precision": ContentPriority.PRECISION,
}
DEFAULT_TOOLS = (
    "chromerag_coverage",
    "chromerag",
    "chromerag_precision",
    "trafilatura",
    "markitdown",
    "readability",
    "rs_trafilatura",
)

_RUNTIME_PACKAGES = {
    "trafilatura": "trafilatura",
    "readability": "readability-lxml",
    "readability_lxml": "readability-lxml",
    "markitdown": "markitdown",
    "rs_trafilatura": "rs-trafilatura",
}


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def expected_model_sha256() -> str:
    data = json.loads(STRICT_MANIFEST.read_text(encoding="utf-8"))
    return str(data["shipped_lbc_stage1_npz"]["sha256"])


def actual_model_sha256() -> str:
    return hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()


def freeze_check_errors() -> list[str]:
    errors: list[str] = []
    tag_ref = _git("rev-parse", f"refs/tags/{REQUIRED_TAG}")
    if tag_ref.returncode != 0:
        errors.append(f"missing git tag {REQUIRED_TAG}")
        return errors
    diff = _git("diff", "--quiet", REQUIRED_TAG, "--", "src", "pyproject.toml")
    if diff.returncode != 0:
        errors.append(f"src/ or pyproject.toml differ from tag {REQUIRED_TAG}")
    status = _git("status", "--porcelain", "--", "src", "pyproject.toml")
    if status.stdout.strip():
        errors.append("src/ or pyproject.toml have uncommitted changes")
    if not MODEL_PATH.is_file():
        errors.append(f"missing model file {MODEL_PATH.relative_to(ROOT)}")
    elif actual_model_sha256() != expected_model_sha256():
        errors.append("lbc_stage1.npz SHA-256 does not match strict_split_manifest.json")
    return errors


def assert_chromerag_freeze() -> None:
    errors = freeze_check_errors()
    if errors:
        raise SystemExit("ChromeRAG freeze check failed: " + "; ".join(errors))


def recorded_dependency_versions() -> dict[str, str]:
    out: dict[str, str] = {"rs_trafilatura_ci_pin": RS_TRAFILATURA_CI_VERSION}
    for key, dist in _RUNTIME_PACKAGES.items():
        try:
            out[key] = metadata.version(dist)
        except metadata.PackageNotFoundError:
            out[key] = "not_installed"
    return out


def tool_version(tool: str) -> str:
    if tool.startswith("chromerag"):
        return REQUIRED_TAG
    dist = _RUNTIME_PACKAGES.get(tool)
    if not dist:
        return "unknown"
    try:
        return metadata.version(dist)
    except metadata.PackageNotFoundError:
        return "not_installed"


def html_sha256(html: str) -> str:
    return hashlib.sha256(html.encode("utf-8", errors="replace")).hexdigest()


def cache_key(*, html: str, tool: str, version: str | None = None) -> str:
    """Cache identity: html sha256 + tool + tool version."""
    payload = f"{html_sha256(html)}|{tool}|{version or tool_version(tool)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def is_held_out_pages_dir(pages_dir: Path) -> bool:
    """Held-out if path is under data/final or a known held-out dir name."""
    resolved = pages_dir.resolve()
    final_dir = (ROOT / "data" / "final").resolve()
    try:
        resolved.relative_to(final_dir)
        return True
    except ValueError:
        pass
    if resolved == final_dir:
        return True
    name = resolved.name.lower()
    if name in HELD_OUT_DIR_NAMES:
        return True
    parts = {p.lower() for p in resolved.parts}
    if "final" in parts and "data" in parts:
        return True
    return False


def is_held_out_set(set_name: str, pages_dir: Path | None = None) -> bool:
    if set_name in HELD_OUT_SETS:
        return True
    if pages_dir is not None and is_held_out_pages_dir(pages_dir):
        return True
    return False


def load_held_out_ledger(path: Path = HELD_OUT_LEDGER) -> dict[str, str]:
    """Map set_name -> run_id for completed held-out scoring runs."""
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        key = str(row.get("set") or "")
        rid = str(row.get("run_id") or "")
        if key and rid:
            out[key] = rid
    return out


def append_held_out_ledger(set_name: str, run_id: str, path: Path = HELD_OUT_LEDGER) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"set": set_name, "run_id": run_id}, sort_keys=True) + "\n")


def assert_set_allowed(
    set_name: str,
    *,
    allow_held_out: bool,
    pages_dir: Path | None = None,
    resume_same_run: str | None = None,
    ledger_path: Path = HELD_OUT_LEDGER,
) -> str | None:
    """Gate held-out scoring. Returns run_id when a held-out run proceeds."""
    held = is_held_out_set(set_name, pages_dir)
    if not held:
        return None

    ledger = load_held_out_ledger(ledger_path)
    existing = ledger.get(set_name)

    if resume_same_run:
        if existing is None:
            raise SystemExit(
                f"No prior held-out run for {set_name!r}; cannot --resume-same-run {resume_same_run!r}."
            )
        if resume_same_run != existing:
            raise SystemExit(
                f"Refusing held-out set {set_name!r}: --resume-same-run does not match run id {existing!r}."
            )
        return resume_same_run

    if existing is not None:
        raise SystemExit(
            f"Refusing second scoring run on held-out set {set_name!r}. "
            f"Pass --resume-same-run {existing} to continue the same run."
        )

    if not allow_held_out:
        raise SystemExit(
            f"Refusing held-out set {set_name!r}. Pass --allow-held-out-scoring only for the one locked manager run."
        )

    run_id = uuid.uuid4().hex
    append_held_out_ledger(set_name, run_id, ledger_path)
    return run_id


def _baseline_rs_trafilatura(html: str, url: str | None = None) -> str:
    try:
        import rs_trafilatura
    except ImportError as exc:
        raise RuntimeError("rs_trafilatura not installed") from exc
    fn = getattr(rs_trafilatura, "extract", None) or getattr(rs_trafilatura, "html2text", None)
    if fn is None:
        raise RuntimeError("rs_trafilatura has no extract/html2text")
    out = fn(html, url=url) if url is not None else fn(html)
    return out or ""


def _extract(tool: str, html: str, url: str) -> str:
    if tool in TOOL_CHROMERAG:
        return ChromeRAG(
            config=PipelineConfig.from_priority(TOOL_CHROMERAG[tool], enable_dvdf=True)
        ).extract(html, url=url or None).markdown
    if tool == "rs_trafilatura":
        return _baseline_rs_trafilatura(html, url or None)
    fn = BASELINES[tool]
    if tool == "trafilatura":
        return fn(html, url=url or None)
    return fn(html)


def cache_path(cache_root: Path, tool: str, key: str) -> Path:
    return cache_root / tool / f"{key[:32]}.json"


def load_pages_from_dir(raw_dir: Path) -> list[dict]:
    pages: list[dict] = []
    for html_path in sorted(raw_dir.glob("*.html")):
        pid = html_path.stem
        meta_path = raw_dir / f"{pid}.meta.json"
        meta = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        pages.append(
            {
                "id": pid,
                "url": meta.get("url") or meta.get("requested_url") or "",
                "page_type": meta.get("page_type") or meta.get("kind") or "unknown",
                "html": html_path.read_text(encoding="utf-8", errors="replace"),
                "main_content": meta.get("main_content"),
                "with_snippets": meta.get("with_snippets") or [],
                "without_snippets": meta.get("without_snippets") or [],
            }
        )
    return pages


def _run_tool_on_page(args: tuple) -> dict:
    page, tool, cache_root_str, version = args
    cache_root = Path(cache_root_str)
    key = cache_key(html=page["html"], tool=tool, version=version)
    cp = cache_path(cache_root, tool, key)
    if cp.exists():
        cached = json.loads(cp.read_text(encoding="utf-8"))
        # Error rows are not reused silently — retry extraction.
        if not cached.get("error"):
            return cached

    t0 = time.perf_counter()
    error = None
    try:
        text = _extract(tool, page["html"], page.get("url") or "")
        if tool.startswith("chromerag"):
            text = strip_front_matter(text)
    except Exception as exc:  # noqa: BLE001
        text, error = "", f"{type(exc).__name__}: {exc}"[:200]
    ms = (time.perf_counter() - t0) * 1000.0
    row: dict = {
        "id": page["id"],
        "tool": tool,
        "tool_version": version,
        "html_sha256": html_sha256(page["html"]),
        "ms": ms,
        "chars": len(text),
        "sha256": hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest(),
        "text": text,
    }
    if error:
        row["error"] = error
    ref = page.get("main_content")
    if ref:
        p, r, f1 = word_f1(text, ref)
        row["p"] = p
        row["r"] = r
        row["f1"] = f1
    # Persist successes; leave prior error files so retries can overwrite after success.
    if not error:
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(json.dumps(row) + "\n", encoding="utf-8")
    elif cp.exists():
        # Replace stale error cache so a later success path is not blocked by identity alone.
        cp.unlink(missing_ok=True)
    return row


def run_set(
    pages: list[dict],
    *,
    tools: list[str],
    cache_root: Path,
    workers: int | None = None,
) -> list[dict]:
    workers = workers or (os.cpu_count() or 1)
    versions = {t: tool_version(t) for t in tools}
    jobs = [(p, t, str(cache_root), versions[t]) for p in pages for t in tools]
    if workers <= 1:
        return [_run_tool_on_page(job) for job in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_run_tool_on_page, jobs))


def summarize(rows: list[dict]) -> dict:
    by_tool: dict[str, list[dict]] = {}
    for row in rows:
        by_tool.setdefault(row["tool"], []).append(row)
    summary = {}
    for tool, group in by_tool.items():
        f1s = [g["f1"] for g in group if "f1" in g]
        summary[tool] = {
            "n": len(group),
            "mean_ms": sum(g["ms"] for g in group) / len(group),
            "errors": sum(1 for g in group if g.get("error")),
        }
        if f1s:
            summary[tool]["mean_f1"] = sum(f1s) / len(f1s)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run extractors on a page set (frozen tag required)")
    parser.add_argument("--set", required=True, help="Set name (synthetic, new_pages, …)")
    parser.add_argument("--pages-dir", type=Path, required=True, help="Directory of *.html (+ optional *.meta.json)")
    parser.add_argument("--tools", default=",".join(DEFAULT_TOOLS))
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "run.json")
    parser.add_argument("--cache", type=Path, default=CACHE_DIR)
    parser.add_argument("--skip-freeze-check", action="store_true", help="Tests only")
    parser.add_argument("--allow-held-out-scoring", action="store_true")
    parser.add_argument(
        "--resume-same-run",
        default=None,
        help="Resume a prior held-out scoring run (must match ledger run id)",
    )
    parser.add_argument("--workers", type=int, default=None, help="Process pool size (default: all cores)")
    args = parser.parse_args()

    if not args.skip_freeze_check:
        assert_chromerag_freeze()
    run_id = assert_set_allowed(
        args.set,
        allow_held_out=args.allow_held_out_scoring,
        pages_dir=args.pages_dir,
        resume_same_run=args.resume_same_run,
    )

    tools = [t.strip() for t in args.tools.split(",") if t.strip()]
    for t in tools:
        if t not in TOOL_CHROMERAG and t not in BASELINES and t != "rs_trafilatura":
            parser.error(f"Unknown tool {t!r}")

    pages = load_pages_from_dir(args.pages_dir)
    if not pages:
        raise SystemExit(f"No pages under {args.pages_dir}")

    cache_root = args.cache / args.set
    rows = run_set(pages, tools=tools, cache_root=cache_root, workers=args.workers)
    payload = {
        "set": args.set,
        "run_id": run_id,
        "chromerag_tag": REQUIRED_TAG,
        "lbc_stage1_sha256": actual_model_sha256(),
        "dependency_versions": recorded_dependency_versions(),
        "tools": tools,
        "n_pages": len(pages),
        "summary": summarize(rows),
        "per_page": {},
    }
    for row in rows:
        payload["per_page"].setdefault(row["id"], {})[row["tool"]] = {
            k: v for k, v in row.items() if k not in {"text", "id", "tool"}
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.out} ({len(rows)} tool-page rows)")


if __name__ == "__main__":
    main()
