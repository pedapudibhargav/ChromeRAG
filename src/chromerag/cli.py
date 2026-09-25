"""ChromeRAG CLI — HTML → RAG Markdown (fetch is not a core concern).

Subcommands:
  extract  — single HTML file → markdown
  learn    — mine site-chrome model from a directory of HTML fixtures
  batch    — learn-then-extract (or extract with a saved chrome model)

URL fetching is intentionally omitted from the default path. Use `poc.fetch_pages`
or your own crawler, then point ChromeRAG at the saved HTML.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from chromerag import __version__
from chromerag.batch import BatchPage, learn_chrome, learn_then_extract
from chromerag.config import ContentPriority, PipelineConfig, Strictness
from chromerag.extractor import ChromeRAG
from chromerag.site_chrome import load_chrome_models, save_chrome_models


def _build_config(args: argparse.Namespace) -> PipelineConfig:
    overrides = dict(
        enable_dvdf=not getattr(args, "no_dvdf", False),
        enable_schema=not getattr(args, "no_schema", False),
        enable_tables=not getattr(args, "no_tables", False),
        enable_stce=not getattr(args, "no_stce", False),
        inject_heading_paths=getattr(args, "heading_paths", False),
    )
    if getattr(args, "priority", None):
        return PipelineConfig.from_priority(args.priority, **overrides)
    if getattr(args, "strictness", None):
        return PipelineConfig.from_strictness(args.strictness, **overrides)
    return PipelineConfig.from_priority(ContentPriority.BALANCED, **overrides)


def _add_shared_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--priority",
        choices=[c.value for c in ContentPriority],
        default=None,
        help="precision | coverage | balanced (default)",
    )
    p.add_argument(
        "--strictness",
        choices=[s.value for s in Strictness],
        default=None,
        help="Legacy alias for priority",
    )
    p.add_argument("--no-dvdf", action="store_true")
    p.add_argument("--no-schema", action="store_true")
    p.add_argument("--no-tables", action="store_true")
    p.add_argument("--no-stce", action="store_true")
    p.add_argument("--heading-paths", action="store_true")


def _load_fixture_dir(raw_dir: Path) -> list[BatchPage]:
    pages: list[BatchPage] = []
    for meta_path in sorted(raw_dir.glob("*.meta.json")):
        if meta_path.name.startswith("_"):
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        html_path = raw_dir / f"{meta['id']}.html"
        if not html_path.exists():
            continue
        pages.append(
            BatchPage(
                html=html_path.read_text(encoding="utf-8", errors="ignore"),
                url=meta.get("url"),
                page_id=meta["id"],
            )
        )
    if not pages:
        # Fallback: bare *.html without meta
        for html_path in sorted(raw_dir.glob("*.html")):
            pages.append(
                BatchPage(
                    html=html_path.read_text(encoding="utf-8", errors="ignore"),
                    url=None,
                    page_id=html_path.stem,
                )
            )
    return pages


def _missing_chrome_model(path: str | None) -> bool:
    if path and not Path(path).is_file():
        sys.stderr.write(
            f"Chrome model not found: {path}\n"
            "Create one first with: chromerag learn <html_dir> -o <model.json>\n"
        )
        return True
    return False


def cmd_extract(args: argparse.Namespace) -> int:
    path = Path(args.html)
    if not path.exists():
        sys.stderr.write(
            f"File not found: {path}\n"
            "ChromeRAG extracts HTML files only. Fetch pages with your crawler "
            "or: python -m poc.fetch_pages\n"
        )
        return 2
    if _missing_chrome_model(args.chrome_model):
        return 2
    html = path.read_text(encoding="utf-8", errors="ignore")
    cfg = _build_config(args)
    model = None
    if args.chrome_model and not args.no_stce:
        models = load_chrome_models(args.chrome_model)
        from chromerag.site_chrome import select_model_for_url

        model = select_model_for_url(models, args.url)
    extractor = ChromeRAG(config=cfg, site_chrome=model)
    result = extractor.extract(html, url=args.url)

    for warning in result.warnings:
        sys.stderr.write(f"WARNING: {warning}\n")

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result.markdown, encoding="utf-8")
    else:
        sys.stdout.write(result.markdown)

    if args.json_meta:
        meta = {
            "url": result.url,
            "tokens_estimate": result.tokens_estimate,
            "n_blocks_in": result.n_blocks_in,
            "n_blocks_kept": result.n_blocks_kept,
            "n_tables": result.n_tables,
            "front_matter": result.front_matter,
            "warnings": result.warnings,
            "input_quality": result.input_quality,
            "diagnostics": result.diagnostics,
        }
        sys.stderr.write(json.dumps(meta, indent=2) + "\n")
    # Non-zero only on hard failures; thin JS shells warn but still exit 0 so
    # pipelines can log and decide. Use --fail-on-thin to hard-fail.
    if getattr(args, "fail_on_thin", False) and result.input_quality.get("is_thin"):
        return 3
    return 0


def cmd_learn(args: argparse.Namespace) -> int:
    if not Path(args.html_dir).is_dir():
        sys.stderr.write(f"Not a directory: {args.html_dir}\n")
        return 2
    pages = _load_fixture_dir(Path(args.html_dir))
    if len(pages) < 2:
        sys.stderr.write("Need at least 2 HTML pages to learn chrome patterns.\n")
        return 2
    cfg = _build_config(args)
    models = learn_chrome(
        pages,
        config=cfg,
        min_pages=args.min_pages,
        path_prefix_depth=args.path_prefix_depth,
    )
    out = Path(args.output)
    save_chrome_models(models, out)
    active = {k: len(m.signatures) for k, m in models.items() if m.signatures}
    sys.stderr.write(
        json.dumps(
            {
                "pages": len(pages),
                "groups": {k: m.n_pages for k, m in models.items()},
                "chrome_signatures": active,
                "wrote": str(out),
            },
            indent=2,
        )
        + "\n"
    )
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    """Learn-then-extract (default) or extract with a pre-learned chrome model."""
    if not Path(args.html_dir).is_dir():
        sys.stderr.write(f"Not a directory: {args.html_dir}\n")
        return 2
    if _missing_chrome_model(args.chrome_model):
        return 2
    pages = _load_fixture_dir(Path(args.html_dir))
    if not pages:
        sys.stderr.write(f"No HTML fixtures in {args.html_dir}\n")
        return 2
    cfg = _build_config(args)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    chrome_models = None
    learn = True
    if args.chrome_model:
        chrome_models = load_chrome_models(args.chrome_model)
        learn = False
    if args.no_learn:
        learn = False

    results, models = learn_then_extract(
        pages,
        config=cfg,
        chrome_models=chrome_models,
        learn=learn,
        path_prefix_depth=args.path_prefix_depth,
    )

    if args.save_chrome:
        save_chrome_models(models, args.save_chrome)

    summary = []
    for br in results:
        pid = br.page_id or "page"
        page_out = out_dir / pid
        page_out.mkdir(parents=True, exist_ok=True)
        (page_out / "chromerag.md").write_text(br.result.markdown, encoding="utf-8")
        iq = br.result.input_quality or {}
        row = {
            "id": pid,
            "url": br.url,
            "tokens": br.result.tokens_estimate,
            "stce_applied": br.stce_applied,
            "chrome_group": br.chrome_group,
            "stce_removed": br.result.diagnostics.get("stce_removed", 0),
            "priority": br.result.diagnostics.get("content_priority"),
            "json_ld": br.result.diagnostics.get("schema_sources", {}).get("json_ld_count", 0),
            "input_thin": bool(iq.get("is_thin")),
            "likely_js_shell": bool(iq.get("likely_js_shell")),
            "warnings": list(br.result.warnings or []),
        }
        summary.append(row)
        flag = " THIN" if row["input_thin"] else ""
        if row["likely_js_shell"]:
            flag = " JS_SHELL"
        print(
            f"{pid:28s} tok={row['tokens']:6d} stce={row['stce_applied']} "
            f"rm={row['stce_removed']} jsonld={row['json_ld']}{flag}"
        )
        for warning in br.result.warnings or []:
            sys.stderr.write(f"WARNING [{pid}]: {warning}\n")

    (out_dir / "batch_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="chromerag",
        description=(
            "ChromeRAG: ingest-time elimination of site template noise "
            "for enterprise web RAG. Pass HTML files — do not use as a crawler."
        ),
    )
    parser.add_argument("--version", action="version", version=f"chromerag {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ex = sub.add_parser("extract", help="Extract one HTML file to Markdown")
    p_ex.add_argument("html", help="Path to .html file")
    p_ex.add_argument("-o", "--output", help="Write markdown to path")
    p_ex.add_argument("--url", help="Canonical URL (for page-type + STCE group)")
    p_ex.add_argument("--chrome-model", help="Path to learned chrome JSON from `chromerag learn`")
    p_ex.add_argument("--json-meta", action="store_true")
    p_ex.add_argument(
        "--fail-on-thin",
        action="store_true",
        help="Exit 3 when input HTML looks thin / like a JS shell (still prints WARNINGs by default)",
    )
    _add_shared_flags(p_ex)
    p_ex.set_defaults(func=cmd_extract)

    p_learn = sub.add_parser(
        "learn",
        help="Mine site-chrome patterns from a directory of HTML (run BEFORE batch extract)",
    )
    p_learn.add_argument("html_dir", help="Directory with *.html (+ optional *.meta.json)")
    p_learn.add_argument("-o", "--output", required=True, help="Write chrome model JSON here")
    p_learn.add_argument("--min-pages", type=int, default=3)
    p_learn.add_argument("--path-prefix-depth", type=int, default=1)
    _add_shared_flags(p_learn)
    p_learn.set_defaults(func=cmd_learn)

    p_batch = sub.add_parser(
        "batch",
        help="Learn-then-extract a directory (or extract with --chrome-model / --no-learn)",
    )
    p_batch.add_argument("html_dir", help="Directory with HTML fixtures")
    p_batch.add_argument("-o", "--output-dir", required=True, help="Output directory")
    p_batch.add_argument(
        "--chrome-model",
        help="Use a previously learned chrome model (skips mining)",
    )
    p_batch.add_argument(
        "--save-chrome",
        help="Also write the mined chrome model to this path",
    )
    p_batch.add_argument(
        "--no-learn",
        action="store_true",
        help="Skip STCE mining; heuristics + DVDF only",
    )
    p_batch.add_argument("--path-prefix-depth", type=int, default=1)
    _add_shared_flags(p_batch)
    p_batch.set_defaults(func=cmd_batch)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
