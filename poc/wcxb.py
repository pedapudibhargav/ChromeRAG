"""WCXB loader and scoring helpers (word F1, snippet rates)."""

from __future__ import annotations

import gzip
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "data" / "wcxb"

_FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n+", re.DOTALL)


@dataclass(frozen=True)
class Page:
    id: str
    url: str
    html: str
    page_type: str
    main_content: str
    with_snippets: list[str]
    without_snippets: list[str]


def strip_front_matter(text: str) -> str:
    return _FRONT_MATTER_RE.sub("", text)


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    return re.findall(r"\w+", text.lower())


def word_f1(pred: str, ref: str) -> tuple[float, float, float]:
    """Word-level precision, recall, F1 (multiset overlap)."""
    pred_tokens = tokenize(pred)
    ref_tokens = tokenize(ref)

    if not ref_tokens:
        return (1.0, 1.0, 1.0) if not pred_tokens else (0.0, 0.0, 0.0)
    if not pred_tokens:
        return (0.0, 0.0, 0.0)

    pred_counts = Counter(pred_tokens)
    ref_counts = Counter(ref_tokens)
    overlap = sum((pred_counts & ref_counts).values())

    precision = overlap / len(pred_tokens)
    recall = overlap / len(ref_tokens)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return (precision, recall, f1)


def snippet_rate(text: str, snippets: list[str]) -> float:
    """Share of snippets found as case-insensitive substrings."""
    if not snippets:
        return 1.0
    text_lower = text.lower()
    found = sum(1 for s in snippets if s.lower() in text_lower)
    return found / len(snippets)


def _page_type(data: dict) -> str:
    internal = data.get("_internal", {}) or {}
    pt_obj = internal.get("page_type", {})
    if isinstance(pt_obj, dict):
        pt = pt_obj.get("primary", "article")
    elif isinstance(pt_obj, str):
        pt = pt_obj
    else:
        pt = "article"
    return "collection" if pt == "category" else pt


# 139 files sit in both the dev/ and test/ folders of the public WCXB release (metadata.json assigns them to test;
# identical HTML, same ids). poc/wcxb_leaked_ids.json lists them. The frozen 0.1.3 model was trained on dev/ including
# these files, so test results are reported with them removed (drop_leaked=True).
LEAKED_IDS = frozenset(json.loads((ROOT / "poc" / "wcxb_leaked_ids.json").read_text())) if (ROOT / "poc" / "wcxb_leaked_ids.json").exists() else frozenset()


def load_split(split: str, root: Path | str = DEFAULT_ROOT, *, drop_leaked: bool = False) -> list[Page]:
    """Load WCXB pages for *split* (dev, test, …). Skips files without a main_content key (2 in dev)."""
    root = Path(root)
    gt_dir = root / split / "ground-truth"
    html_dir = root / split / "html"
    if not gt_dir.is_dir():
        raise FileNotFoundError(f"Missing ground truth dir: {gt_dir}")

    pages: list[Page] = []
    for gt_path in sorted(gt_dir.glob("*.json")):
        data = json.loads(gt_path.read_text(encoding="utf-8"))
        gt = data.get("ground_truth", {})
        if not isinstance(gt, dict):
            continue
        # Same 1,495 dev pages as the frozen 0.1.2 baseline: skip only files that have no
        # main_content key. Empty references are kept and scored (empty output scores 1.0).
        if "main_content" not in gt:
            continue
        main_content = gt.get("main_content", "") or ""

        page_id = gt_path.stem
        if drop_leaked and page_id in LEAKED_IDS:
            continue
        html_path = html_dir / f"{page_id}.html.gz"
        if not html_path.exists():
            continue
        with gzip.open(html_path, "rt", encoding="utf-8", errors="ignore") as fh:
            html = fh.read()

        pages.append(
            Page(
                id=page_id,
                url=data.get("url", ""),
                html=html,
                page_type=_page_type(data),
                main_content=main_content,
                with_snippets=list(gt.get("with", []) or []),
                without_snippets=list(gt.get("without", []) or []),
            )
        )
    return pages
