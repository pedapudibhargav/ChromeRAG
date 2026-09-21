"""Compare UI API — side-by-side HTML extraction validation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from poc.baselines import BASELINES, estimate_tokens, noise_keyword_hits
from chromerag import ChromeRAG
from chromerag.config import ContentPriority, PipelineConfig, Strictness

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "outputs"
STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="ChromeRAG — Compare Lab", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

METHODS = [
    "chromerag",
    "chromerag_heading_paths",
    "trafilatura",
    "readability",
    "markitdown",
    "markdownify",
    "html2text",
    "beautifulsoup_text",
]


class ExtractRequest(BaseModel):
    page_id: str | None = None
    url: str | None = None
    html: str | None = None
    methods: list[str] = Field(default_factory=lambda: list(METHODS))
    inject_heading_paths: bool = False
    priority: str = ContentPriority.BALANCED.value
    strictness: str | None = None  # legacy; prefer priority
    enable_stce: bool = False  # needs mined model; off by default for single-page live extract


def _page_meta(page_id: str) -> dict[str, Any]:
    meta_path = RAW / f"{page_id}.meta.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    return {"id": page_id, "url": None, "category": "unknown"}


def _heading_stats(text: str) -> dict[str, Any]:
    heads = re.findall(r"^(#{1,6})\s+(.+)$", text, re.M)
    by_level: dict[str, int] = {}
    for marks, _ in heads:
        key = f"h{len(marks)}"
        by_level[key] = by_level.get(key, 0) + 1
    return {
        "heading_count": len(heads),
        "by_level": by_level,
        "sample": [f"{'#' * len(m)} {t}" for m, t in heads[:8]],
    }


def _stats(text: str) -> dict[str, Any]:
    noise = noise_keyword_hits(text)
    return {
        "chars": len(text),
        "tokens": estimate_tokens(text),
        "noise_total": sum(noise.values()),
        "noise_hits": noise,
        "headings": _heading_stats(text),
        "has_front_matter": text.lstrip().startswith("---"),
        "table_markers": len(re.findall(r"\[Table:", text)),
        "section_markers": len(re.findall(r"\[Section:", text)),
    }


def _load_cached(page_id: str, method: str) -> str | None:
    path = OUT / page_id / f"{method}.md"
    if path.exists():
        return path.read_text(encoding="utf-8", errors="ignore")
    return None


def _smart_cfg(
    *,
    priority: str | None = None,
    strictness: str | None = None,
    inject_heading_paths: bool = False,
    enable_stce: bool = False,
) -> PipelineConfig:
    if priority:
        return PipelineConfig.from_priority(
            priority,
            inject_heading_paths=inject_heading_paths,
            enable_stce=enable_stce,
        )
    if strictness:
        return PipelineConfig.from_strictness(
            strictness,
            inject_heading_paths=inject_heading_paths,
            enable_stce=enable_stce,
        )
    return PipelineConfig.from_priority(
        ContentPriority.BALANCED,
        inject_heading_paths=inject_heading_paths,
        enable_stce=enable_stce,
    )


def _run_method(
    method: str,
    html: str,
    url: str | None,
    *,
    priority: str = ContentPriority.BALANCED.value,
) -> str:
    if method == "chromerag":
        return ChromeRAG(config=_smart_cfg(priority=priority)).extract(
            html, url=url
        ).markdown
    if method == "chromerag_heading_paths":
        return ChromeRAG(
            config=_smart_cfg(priority=priority, inject_heading_paths=True)
        ).extract(html, url=url).markdown
    fn = BASELINES.get(method)
    if not fn:
        raise HTTPException(400, f"Unknown method: {method}")
    return fn(html)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/pages")
def list_pages() -> dict[str, Any]:
    pages = []
    for meta_path in sorted(RAW.glob("*.meta.json")):
        if meta_path.name.startswith("_"):
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        page_id = meta["id"]
        out_dir = OUT / page_id
        available = []
        if out_dir.exists():
            available = sorted(p.stem for p in out_dir.glob("*.md"))
        pages.append(
            {
                "id": page_id,
                "url": meta.get("url"),
                "category": meta.get("category"),
                "signals": meta.get("signals", {}),
                "cached_methods": available,
            }
        )
    report = {}
    report_path = OUT / "benchmark_report.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8")).get("summary", {})
    return {"pages": pages, "methods": METHODS, "benchmark_summary": report}


@app.get("/api/compare/{page_id}")
def compare_page(
    page_id: str,
    left: str = Query("chromerag"),
    right: str = Query("markitdown"),
    live: bool = Query(False),
    priority: str = Query(ContentPriority.BALANCED.value),
) -> dict[str, Any]:
    html_path = RAW / f"{page_id}.html"
    if not html_path.exists():
        raise HTTPException(404, f"No fixture for {page_id}")
    html = html_path.read_text(encoding="utf-8", errors="ignore")
    meta = _page_meta(page_id)
    url = meta.get("url")

    def resolve(method: str) -> tuple[str, str]:
        if not live and method.startswith("chromerag"):
            if priority != ContentPriority.BALANCED.value:
                text = _run_method(method, html, url, priority=priority)
                return text, f"live:{priority}"
        if not live:
            cached = _load_cached(page_id, method)
            if cached is not None and method != "chromerag_heading_paths":
                return cached, "cache"
            if method == "chromerag_heading_paths":
                text = _run_method(method, html, url, priority=priority)
                (OUT / page_id).mkdir(parents=True, exist_ok=True)
                (OUT / page_id / f"{method}.md").write_text(text, encoding="utf-8")
                return text, "generated"
            if cached is not None:
                return cached, "cache"
        text = _run_method(method, html, url, priority=priority)
        (OUT / page_id).mkdir(parents=True, exist_ok=True)
        (OUT / page_id / f"{method}.md").write_text(text, encoding="utf-8")
        return text, "live" if live else "generated"

    left_text, left_src = resolve(left)
    right_text, right_src = resolve(right)

    return {
        "page": meta,
        "priority": priority,
        "left": {"method": left, "source": left_src, "text": left_text, "stats": _stats(left_text)},
        "right": {"method": right, "source": right_src, "text": right_text, "stats": _stats(right_text)},
    }


@app.get("/api/matrix/{page_id}")
def matrix(page_id: str) -> dict[str, Any]:
    """Compact stats for all methods on one page (for overview cards)."""
    html_path = RAW / f"{page_id}.html"
    if not html_path.exists():
        raise HTTPException(404, f"No fixture for {page_id}")
    meta = _page_meta(page_id)
    rows = []
    for method in METHODS:
        text = _load_cached(page_id, method)
        if text is None and method == "chromerag_heading_paths":
            html = html_path.read_text(encoding="utf-8", errors="ignore")
            text = _run_method(method, html, meta.get("url"))
            (OUT / page_id).mkdir(parents=True, exist_ok=True)
            (OUT / page_id / f"{method}.md").write_text(text, encoding="utf-8")
        if text is None:
            continue
        rows.append({"method": method, **_stats(text)})
    return {"page": meta, "rows": rows}


@app.post("/api/extract")
def extract(req: ExtractRequest) -> dict[str, Any]:
    html = req.html
    url = req.url
    page_id = req.page_id
    if page_id:
        path = RAW / f"{page_id}.html"
        if not path.exists():
            raise HTTPException(404, f"Unknown page_id {page_id}")
        html = path.read_text(encoding="utf-8", errors="ignore")
        meta = _page_meta(page_id)
        url = url or meta.get("url")
    if not html:
        raise HTTPException(400, "Provide page_id, html, or fetch via url in page fixtures")

    results = {}
    priority = req.priority or (
        ContentPriority.BALANCED.value
        if not req.strictness
        else None
    )
    for method in req.methods:
        try:
            if method == "chromerag" and req.inject_heading_paths:
                method_key = "chromerag_heading_paths"
                text = ChromeRAG(
                    config=_smart_cfg(
                        priority=priority,
                        strictness=req.strictness,
                        inject_heading_paths=True,
                        enable_stce=req.enable_stce,
                    )
                ).extract(html, url=url).markdown
            else:
                method_key = method
                if priority:
                    text = _run_method(method, html, url, priority=priority)
                else:
                    # legacy strictness path via cfg
                    text = ChromeRAG(
                        config=_smart_cfg(strictness=req.strictness)
                    ).extract(html, url=url).markdown if method.startswith("chromerag") else _run_method(
                        method, html, url
                    )
            results[method_key] = {"ok": True, "text": text, "stats": _stats(text)}
            if page_id:
                (OUT / page_id).mkdir(parents=True, exist_ok=True)
                (OUT / page_id / f"{method_key}.md").write_text(text, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            results[method] = {"ok": False, "error": str(exc)}
    return {
        "page_id": page_id,
        "url": url,
        "priority": priority or req.strictness,
        "results": results,
    }
