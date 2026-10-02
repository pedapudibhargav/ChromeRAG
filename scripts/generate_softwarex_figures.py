#!/usr/bin/env python3
"""Render the SoftwareX figures from the published results in docs/data/.

Figures follow Elsevier's artwork guidance: drawn at print size (6.5 in text
width, sizes in points), sans-serif text of at least 7 pt, no titles inside the
artwork (captions carry them), vector PDF plus a 600 dpi PNG for Word.
ChromeRAG is always blue, Trafilatura orange, MarkItDown aqua and Readability
grey; every series is labelled directly, so colour is never the only cue.

Needs a local Chrome/Chromium (headless) to rasterize the SVGs.

Usage:
  python scripts/generate_softwarex_figures.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
OUT = ROOT / "papers" / "softwarex" / "figures"

WIDTH = 468  # pt, 6.5 in
DPI = 600
FONT = "Arial, Helvetica, sans-serif"
INK = "#1f1f1d"
INK_2 = "#52514e"
MUTED = "#8a8983"
GRID = "#e4e3df"
SURFACE = "#ffffff"

METHODS = {
    "chromerag_coverage": ("ChromeRAG (coverage)", "#2a78d6"),
    "chromerag": ("ChromeRAG (balanced)", "#86b6ef"),
    "trafilatura": ("Trafilatura", "#eb6834"),
    "markitdown": ("MarkItDown", "#1baf7a"),
    "readability": ("Readability", "#8a8983"),
}

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome",
    "chromium",
    "chromium-browser",
]


def _text(x, y, s, *, size=8, anchor="start", weight="normal", fill=INK, baseline="auto"):
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" '
        f'font-weight="{weight}" fill="{fill}" dominant-baseline="{baseline}">{escape(str(s))}</text>'
    )


def _svg(height: float, body: list[str]) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}pt" height="{height}pt" '
        f'viewBox="0 0 {WIDTH} {height}" font-family="{FONT}">'
        f'<rect width="{WIDTH}" height="{height}" fill="{SURFACE}"/>' + "".join(body) + "</svg>"
    )


def _hbar(x0, y, length, thickness, color):
    """Horizontal bar: square at the baseline, 2 pt rounded data end."""
    r = min(2.0, length / 2, thickness / 2)
    if length <= 0:
        return ""
    return (
        f'<path d="M{x0:.2f},{y:.2f} h{length - r:.2f} a{r},{r} 0 0 1 {r},{r} '
        f'v{thickness - 2 * r:.2f} a{r},{r} 0 0 1 -{r},{r} h-{length - r:.2f} z" fill="{color}"/>'
    )


# --------------------------------------------------------------------------- Fig. 1
def fig_architecture() -> str:
    stages = [
        ("1", "Input", "gate", "thin / JS", "warnings"),
        ("2", "Schema", "harvest", "JSON-LD", "front-matter"),
        ("3", "Clean +", "STCE", "hidden, rules,", "site model"),
        ("4", "Chrome", "prune", "landmarks,", "class words"),
        ("5", "Learned", "block filter", "trees score", "each block"),
        ("6", "Tables +", "Markdown", "key–value,", "doc. order"),
    ]
    h = 150
    body: list[str] = [
        '<defs><marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" '
        f'orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" fill="{MUTED}"/></marker></defs>'
    ]
    io_w, gap = 50, 9
    box_w = (WIDTH - 2 * io_w - 12 - 7 * gap) / 6
    top, bh = 14, 74
    body.append(f'<rect x="6" y="{top}" width="{io_w}" height="{bh}" rx="4" fill="#f3f2ef"/>')
    body.append(_text(6 + io_w / 2, top + bh / 2 - 5, "HTML", size=9, anchor="middle", weight="bold"))
    body.append(_text(6 + io_w / 2, top + bh / 2 + 8, "file or string", size=7, anchor="middle", fill=INK_2))
    x = 6 + io_w + gap
    centers = []
    for num, l1, l2, d1, d2 in stages:
        accent = num == "5"
        fill = "#eaf2fc" if accent else "#f7f7f5"
        stroke = "#2a78d6" if accent else "#d6d5d0"
        body.append(
            f'<rect x="{x:.1f}" y="{top}" width="{box_w:.1f}" height="{bh}" rx="4" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{1.2 if accent else 0.8}"/>'
        )
        cx = x + box_w / 2
        centers.append(cx)
        body.append(_text(cx, top + 15, num, size=8, anchor="middle", weight="bold", fill="#2a78d6" if accent else MUTED))
        body.append(_text(cx, top + 30, l1, size=8.5, anchor="middle", weight="bold"))
        body.append(_text(cx, top + 41, l2, size=8.5, anchor="middle", weight="bold"))
        body.append(_text(cx, top + 56, d1, size=7, anchor="middle", fill=INK_2))
        body.append(_text(cx, top + 66, d2, size=7, anchor="middle", fill=INK_2))
        body.append(
            f'<line x1="{x - gap + 1:.1f}" y1="{top + bh / 2}" x2="{x - 1:.1f}" y2="{top + bh / 2}" '
            f'stroke="{MUTED}" stroke-width="1" marker-end="url(#arr)"/>'
        )
        x += box_w + gap
    body.append(
        f'<line x1="{x - gap + 1:.1f}" y1="{top + bh / 2}" x2="{x - 1:.1f}" y2="{top + bh / 2}" '
        f'stroke="{MUTED}" stroke-width="1" marker-end="url(#arr)"/>'
    )
    body.append(f'<rect x="{x:.1f}" y="{top}" width="{io_w}" height="{bh}" rx="4" fill="#f3f2ef"/>')
    body.append(_text(x + io_w / 2, top + bh / 2 - 5, "Markdown", size=9, anchor="middle", weight="bold"))
    body.append(_text(x + io_w / 2, top + bh / 2 + 8, "+ diagnostics", size=7, anchor="middle", fill=INK_2))

    # chromerag learn feeds stage 3
    lw, ly = 150, top + bh + 26
    lx = centers[2] - lw / 2
    body.append(
        f'<rect x="{lx:.1f}" y="{ly}" width="{lw}" height="30" rx="4" fill="{SURFACE}" '
        f'stroke="#2a78d6" stroke-width="1" stroke-dasharray="3 2"/>'
    )
    body.append(_text(centers[2], ly + 12, "chromerag learn (optional)", size=8, anchor="middle", weight="bold"))
    body.append(_text(centers[2], ly + 23, "≥ 3 pages of one site → site model", size=7, anchor="middle", fill=INK_2))
    body.append(
        f'<line x1="{centers[2]:.1f}" y1="{ly - 1}" x2="{centers[2]:.1f}" y2="{top + bh + 2}" '
        f'stroke="#2a78d6" stroke-width="1" marker-end="url(#arr)"/>'
    )
    return _svg(h, body)


# --------------------------------------------------------------------------- Fig. 2
TYPE_LABELS = {"all": "All pages (511)", "article": "Article (257)", "documentation": "Documentation (42)",
               "service": "Service (59)", "forum": "Forum (51)", "product": "Product (28)",
               "collection": "Collection (34)", "listing": "Listing (40)"}
DOT_TOOLS = ("chromerag", "trafilatura", "readability", "markitdown")


def fig_wcxb_test(final: dict) -> str:
    means = final["wcxb_test"]["means"]
    rows = list(TYPE_LABELS)
    row_h, top, label_w = 17, 30, 104
    h = top + len(rows) * row_h + 26
    x0, w = label_w + 8, WIDTH - label_w - 24
    lo, hi = 0.2, 1.0
    sx = lambda v: x0 + (v - lo) / (hi - lo) * w  # noqa: E731
    body: list[str] = []
    for t in (0.2, 0.4, 0.6, 0.8, 1.0):
        body.append(f'<line x1="{sx(t):.1f}" y1="{top - 6}" x2="{sx(t):.1f}" y2="{top + len(rows) * row_h}" stroke="{GRID}" stroke-width="0.6"/>')
        body.append(_text(sx(t), top + len(rows) * row_h + 10, f"{t:.1f}", size=7, anchor="middle", fill=INK_2))
    body.append(_text(x0 + w / 2, top + len(rows) * row_h + 21, "Word-level F1 against human-reviewed main content (WCXB held-out test)", size=7.5, anchor="middle", fill=INK_2))
    lx = x0
    for key in DOT_TOOLS:
        label, color = METHODS[key]
        body.append(f'<circle cx="{lx + 3:.1f}" cy="10" r="3.4" fill="{color}"/>')
        body.append(_text(lx + 10, 12.5, label, size=7.5))
        lx += 20 + 4.4 * len(label)
    for i, row in enumerate(rows):
        y = top + i * row_h + row_h / 2
        if row == "all":
            body.append(f'<rect x="4" y="{y - row_h / 2 + 1:.1f}" width="{WIDTH - 8}" height="{row_h - 2}" fill="#f6f5f2"/>')
        body.append(_text(label_w, y + 2.5, TYPE_LABELS[row], size=7.5, anchor="end", weight="bold" if row == "all" else "normal"))
        for key in DOT_TOOLS:
            v = means[row][key]["f1"]
            body.append(f'<circle cx="{sx(v):.1f}" cy="{y:.1f}" r="3.4" fill="{METHODS[key][1]}" stroke="{SURFACE}" stroke-width="0.9"/>')
        v = means[row]["chromerag"]["f1"]
        body.append(_text(sx(v), y - 6, f"{v:.2f}", size=6.5, anchor="middle", fill="#2a78d6"))
    return _svg(h, body)


# --------------------------------------------------------------------------- Fig. 3
def fig_frontier(final: dict) -> str:
    h = 200
    x0, y0, w, ph = 46, 14, WIDTH - 130, 150
    xmin, xmax, ymin, ymax = 0.68, 1.0, 0.76, 0.90
    sx = lambda v: x0 + (v - xmin) / (xmax - xmin) * w  # noqa: E731
    sy = lambda v: y0 + ph - (v - ymin) / (ymax - ymin) * ph  # noqa: E731
    body: list[str] = []
    for t in (0.7, 0.8, 0.9, 1.0):
        body.append(f'<line x1="{sx(t):.1f}" y1="{y0}" x2="{sx(t):.1f}" y2="{y0 + ph}" stroke="{GRID}" stroke-width="0.6"/>')
        body.append(_text(sx(t), y0 + ph + 10, f"{t:.1f}", size=7, anchor="middle", fill=INK_2))
    for t in (0.76, 0.80, 0.84, 0.88):
        body.append(f'<line x1="{x0}" y1="{sy(t):.1f}" x2="{x0 + w}" y2="{sy(t):.1f}" stroke="{GRID}" stroke-width="0.6"/>')
        body.append(_text(x0 - 4, sy(t) + 2.5, f"{t:.2f}", size=7, anchor="end", fill=INK_2))
    body.append(_text(x0 + w / 2, y0 + ph + 22, "Recall", size=7.5, anchor="middle", fill=INK_2))
    body.append(f'<text x="12" y="{y0 + ph / 2:.1f}" font-size="7.5" fill="{INK_2}" text-anchor="middle" transform="rotate(-90 12 {y0 + ph / 2:.1f})">Precision</text>')
    pts = []
    for t, (p, r, f1) in final["frontier_dev"].items():
        if xmin <= r <= xmax and ymin <= p <= ymax:
            pts.append((float(t), r, p))
    pts.sort()
    body.append('<polyline points="' + " ".join(f"{sx(r):.1f},{sy(p):.1f}" for _, r, p in pts) + f'" fill="none" stroke="#2a78d6" stroke-width="1.6"/>')
    for t, r, p in pts:
        body.append(f'<circle cx="{sx(r):.1f}" cy="{sy(p):.1f}" r="2.6" fill="#2a78d6" stroke="{SURFACE}" stroke-width="0.8"/>')
        body.append(_text(sx(r) + 4, sy(p) - 3, f"{t:.2f}", size=6, fill=INK_2))
    dev = final["wcxb_dev_cv"]["means"]["all"]
    for key in ("trafilatura", "readability"):
        label, color = METHODS[key]
        p, r = dev[key]["p"], dev[key]["r"]
        body.append(f'<circle cx="{sx(r):.1f}" cy="{sy(p):.1f}" r="4" fill="{color}" stroke="{SURFACE}" stroke-width="1"/>')
        body.append(_text(sx(r) + 7, sy(p) + 2.5, label, size=7.5))
    body.append(_text(x0 + w + 8, y0 + 12, "ChromeRAG:", size=7.5, weight="bold", fill="#2a78d6"))
    body.append(_text(x0 + w + 8, y0 + 23, "threshold 0.15 to 0.90", size=7, fill=INK_2))
    body.append(_text(x0 + w + 8, y0 + 34, "(coverage 0.30,", size=7, fill=INK_2))
    body.append(_text(x0 + w + 8, y0 + 44, "balanced 0.50,", size=7, fill=INK_2))
    body.append(_text(x0 + w + 8, y0 + 54, "precision 0.70)", size=7, fill=INK_2))
    return _svg(h, body)


# --------------------------------------------------------------------------- Fig. 4
def fig_retrieval(report: dict) -> str:
    tools = [t for t in METHODS if t in report["tools"]]
    rows = len(tools)
    row_h, thick = 20, 10
    top = 26
    h = top + rows * row_h + 30
    body: list[str] = []
    label_w = 98
    panels = [
        ("(a)", "Known-item hit@5 (higher is better)", "hit@5", 1.0, lambda v: f"{v:.3f}", (0, 0.25, 0.5, 0.75, 1.0), lambda t: f"{t:g}"),
        ("(b)", "Chrome in retrieved context (lower is better)", "context_chrome@5", 0.03, lambda v: f"{v * 100:.1f}%", (0, 0.01, 0.02, 0.03), lambda t: f"{t * 100:.0f}%"),
    ]
    pw = (WIDTH - label_w - 20) / 2
    for pi, (tag, title, metric, vmax, fmt, ticks, tfmt) in enumerate(panels):
        x0 = label_w + pi * (pw + 20)
        w = pw - 30
        body.append(
            f'<text x="{x0 - (label_w - 4) if pi == 0 else x0:.1f}" y="10" font-size="7.5" fill="{INK_2}">'
            f'<tspan font-size="9" font-weight="bold" fill="{INK}">{tag}</tspan>'
            f'<tspan dx="{label_w - 4 - 14 if pi == 0 else 6}">{escape(title)}</tspan></text>'
        )
        for t in ticks:
            x = x0 + t / vmax * w
            body.append(f'<line x1="{x:.1f}" y1="{top - 4}" x2="{x:.1f}" y2="{top + rows * row_h}" stroke="{GRID}" stroke-width="0.6"/>')
            body.append(_text(x, top + rows * row_h + 10, tfmt(t), size=7, anchor="middle", fill=INK_2))
        for i, tool in enumerate(tools):
            label, color = METHODS[tool]
            y = top + i * row_h + (row_h - thick) / 2
            v = report["tools"][tool][metric]
            length = v / vmax * w
            body.append(_hbar(x0, y, length, thick, color))
            body.append(_text(x0 + length + 3, y + thick / 2 + 2.5, fmt(v), size=7))
            if pi == 0:
                body.append(_text(label_w - 8, y + thick / 2 + 2.5, label, size=7.5, anchor="end"))
        body.append(f'<line x1="{x0}" y1="{top - 4}" x2="{x0}" y2="{top + rows * row_h}" stroke="{INK_2}" stroke-width="0.8"/>')
    return _svg(h, body)


# --------------------------------------------------------------------------- Fig. 5
def fig_judge(final: dict) -> str:
    rows = [("Landing pages (100)", "vs Trafilatura", final["judge"]["all:trafilatura"], "#eb6834"),
            ("Landing pages (100)", "vs MarkItDown", final["judge"]["all:markitdown"], "#1baf7a"),
            ("WCXB test (105)", "vs Trafilatura", final["judge_wcxb_test"]["all:trafilatura"], "#eb6834"),
            ("WCXB test (105)", "vs MarkItDown", final["judge_wcxb_test"]["all:markitdown"], "#1baf7a")]
    h, top, label_w = 112, 22, 128
    x0, w = label_w + 6, WIDTH - label_w - 20
    body: list[str] = [_text(x0, 10, "Blind pairwise LLM judge: share of pages preferred (grey = tie)", size=7.5, fill=INK_2)]
    for i, (group, label, r, other) in enumerate(rows):
        y = top + i * 20
        body.append(_text(label_w, y + 9, f"{group}, {label}", size=7, anchor="end"))
        x = x0
        for key, color in (("chromerag_wins", "#2a78d6"), ("ties", "#c9c8c2"), ("baseline_wins", other)):
            seg = r[key] * w
            body.append(f'<rect x="{x:.1f}" y="{y}" width="{seg:.1f}" height="13" fill="{color}"/>')
            if r[key] >= 0.08:
                body.append(_text(x + seg / 2, y + 9.5, f"{r[key] * 100:.0f}%", size=7, anchor="middle", fill="#ffffff" if key != "ties" else INK))
            x += seg
    body.append(f'<rect x="{x0}" y="{top + 84}" width="8" height="8" fill="#2a78d6"/>' + _text(x0 + 12, top + 91, "ChromeRAG preferred", size=7))
    return _svg(h, body)


# --------------------------------------------------------------------------- output
def _chrome() -> str:
    found = next((c for c in CHROME_CANDIDATES if shutil.which(c) or Path(c).exists()), None)
    if not found:
        raise SystemExit("A Chrome/Chromium binary is needed to rasterize the figures.")
    return found


def render(name: str, svg: str) -> None:
    chrome = _chrome()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.svg").write_text(svg, encoding="utf-8")
    height_pt = float(svg.split('height="', 1)[1].split("pt", 1)[0])
    px_w, px_h = round(WIDTH * 4 / 3), round(height_pt * 4 / 3)
    page = OUT / f"_{name}.html"
    page.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><style>"
        f"@page{{size:{WIDTH}pt {height_pt}pt;margin:0}}html,body{{margin:0;padding:0;background:#fff}}"
        "svg{display:block}</style></head><body>" + svg + "</body></html>",
        encoding="utf-8",
    )
    common = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-pdf-header-footer"]
    scale = DPI / 96
    subprocess.run(
        common
        + [f"--force-device-scale-factor={scale}", f"--window-size={px_w},{px_h}", f"--screenshot={OUT / (name + '.png')}", page.as_uri()],
        check=True,
        capture_output=True,
        timeout=120,
    )
    subprocess.run(
        common + [f"--print-to-pdf={OUT / (name + '.pdf')}", page.as_uri()],
        check=True,
        capture_output=True,
        timeout=120,
    )
    page.unlink()
    print(f"Wrote {name}.svg/.png/.pdf")


def main() -> None:
    final = json.loads((DATA / "final_results.json").read_text(encoding="utf-8"))
    fresh = {"tools": {t: v for t, v in final["retrieval_fresh"]["bm25"].items()}}
    for stale in OUT.glob("fig*_*.png"):
        stale.unlink()
    render("fig1_architecture", fig_architecture())
    render("fig2_wcxb_test", fig_wcxb_test(final))
    render("fig3_frontier", fig_frontier(final))
    render("fig4_retrieval", fig_retrieval(fresh))
    render("fig5_judge", fig_judge(final))
    print("Done:", OUT)


if __name__ == "__main__":
    sys.exit(main())
