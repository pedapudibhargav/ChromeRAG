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
        ("1", "Input-quality", "gate", "thin / JS-shell", "warnings"),
        ("2", "Schema", "harvest", "JSON-LD, Microdata", "→ front-matter"),
        ("3", "Clean +", "STCE", "strip scripts; apply", "site model"),
        ("4", "Structural +", "density prune", "landmarks, link", "density, DVDF"),
        ("5", "Tables +", "Markdown", "key–value rows,", "safe headings"),
    ]
    h = 150
    body: list[str] = [
        '<defs><marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" '
        f'orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" fill="{MUTED}"/></marker></defs>'
    ]
    io_w, gap = 50, 9
    box_w = (WIDTH - 2 * io_w - 12 - 6 * gap) / 5
    top, bh = 14, 74
    body.append(f'<rect x="6" y="{top}" width="{io_w}" height="{bh}" rx="4" fill="#f3f2ef"/>')
    body.append(_text(6 + io_w / 2, top + bh / 2 - 5, "HTML", size=9, anchor="middle", weight="bold"))
    body.append(_text(6 + io_w / 2, top + bh / 2 + 8, "file or string", size=7, anchor="middle", fill=INK_2))
    x = 6 + io_w + gap
    centers = []
    for num, l1, l2, d1, d2 in stages:
        accent = num == "3"
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
def fig_benchmark(report: dict) -> str:
    h = 212
    body: list[str] = []
    pw = (WIDTH - 30) / 2
    # (a) recall vs noise retention, means over scoreable pages
    summary = report["summary"]
    x0, y0, w, ph = 44, 20, pw - 44, 150
    xmax, ymin, ymax = 0.3, 0.4, 0.75
    sx = lambda v: x0 + v / xmax * w  # noqa: E731
    sy = lambda v: y0 + ph - (v - ymin) / (ymax - ymin) * ph  # noqa: E731
    body.append(_text(4, 10, "(a)", size=9, weight="bold"))
    for t in (0.0, 0.1, 0.2, 0.3):
        body.append(f'<line x1="{sx(t):.1f}" y1="{y0}" x2="{sx(t):.1f}" y2="{y0 + ph}" stroke="{GRID}" stroke-width="0.6"/>')
        body.append(_text(sx(t), y0 + ph + 10, f"{t:.1f}", size=7, anchor="middle", fill=INK_2))
    for t in (0.4, 0.5, 0.6, 0.7):
        body.append(f'<line x1="{x0}" y1="{sy(t):.1f}" x2="{x0 + w}" y2="{sy(t):.1f}" stroke="{GRID}" stroke-width="0.6"/>')
        body.append(_text(x0 - 4, sy(t) + 2.5, f"{t:.1f}", size=7, anchor="end", fill=INK_2))
    body.append(_text(x0 + w / 2, y0 + ph + 22, "Noise retention (lower is better)", size=7.5, anchor="middle", fill=INK_2))
    body.append(
        f'<text x="12" y="{y0 + ph / 2:.1f}" font-size="7.5" fill="{INK_2}" text-anchor="middle" '
        f'transform="rotate(-90 12 {y0 + ph / 2:.1f})">Content recall (higher is better)</text>'
    )
    body.append(_text(x0 + 4, y0 + 9, "↖ better", size=7, fill=MUTED))
    leader_x = sx(0.045)  # labels for the cluster near zero noise sit to the right
    for key, (label, color) in METHODS.items():
        s = summary[key]
        cx, cy = sx(s["avg_noise_retention"]), sy(s["avg_content_recall"])
        if key == "markitdown":
            body.append(_text(cx, cy - 8, label, size=7, anchor="middle"))
        else:
            body.append(f'<line x1="{cx + 4:.1f}" y1="{cy:.1f}" x2="{leader_x - 2:.1f}" y2="{cy:.1f}" stroke="{MUTED}" stroke-width="0.5"/>')
            body.append(_text(leader_x, cy + 2.5, label, size=7))
        body.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.6" fill="{color}" stroke="{SURFACE}" stroke-width="1.2"/>')

    # (b) per-page recall ECDF: where content gets lost
    pages = [p for p in report["pages"].values() if p.get("scoreable")]
    bx0, by0, bw = WIDTH / 2 + 42, 20, pw - 38
    body.append(_text(WIDTH / 2 + 8, 10, "(b)", size=9, weight="bold"))
    bsx = lambda v: bx0 + v * bw  # noqa: E731
    bsy = lambda v: by0 + ph - v * ph  # noqa: E731
    body.append(f'<rect x="{bsx(0):.1f}" y="{by0}" width="{bsx(0.2) - bsx(0):.1f}" height="{ph}" fill="#f6f5f2"/>')
    body.append(_text(bsx(0.1), by0 + 9, "recall < 0.2", size=6.5, anchor="middle", fill=MUTED))
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        body.append(f'<line x1="{bsx(t):.1f}" y1="{by0}" x2="{bsx(t):.1f}" y2="{by0 + ph}" stroke="{GRID}" stroke-width="0.6"/>')
        body.append(_text(bsx(t), by0 + ph + 10, f"{t:g}", size=7, anchor="middle", fill=INK_2))
        body.append(f'<line x1="{bx0}" y1="{bsy(t):.1f}" x2="{bx0 + bw}" y2="{bsy(t):.1f}" stroke="{GRID}" stroke-width="0.6"/>')
        body.append(_text(bx0 - 4, bsy(t) + 2.5, f"{int(t * 100)}%", size=7, anchor="end", fill=INK_2))
    body.append(_text(bx0 + bw / 2, by0 + ph + 22, "Per-page content recall", size=7.5, anchor="middle", fill=INK_2))
    body.append(
        f'<text x="{WIDTH / 2 + 12:.1f}" y="{by0 + ph / 2:.1f}" font-size="7.5" fill="{INK_2}" text-anchor="middle" '
        f'transform="rotate(-90 {WIDTH / 2 + 12:.1f} {by0 + ph / 2:.1f})">Share of pages (cumulative)</text>'
    )
    legend_y = bsy(0.86)
    for i, key in enumerate(("trafilatura", "chromerag_coverage", "markitdown")):
        label, color = METHODS[key]
        vals = sorted(p["methods"][key]["content_recall"] for p in pages)
        n = len(vals)
        pts = [f"{bsx(0):.2f},{bsy(0):.2f}"]
        for j, v in enumerate(vals):
            pts.append(f"{bsx(v):.2f},{bsy(j / n):.2f}")
            pts.append(f"{bsx(v):.2f},{bsy((j + 1) / n):.2f}")
        pts.append(f"{bsx(1):.2f},{bsy(1):.2f}")
        body.append(
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1.5" '
            'stroke-linejoin="round" stroke-linecap="round"/>'
        )
        ly = legend_y + i * 11
        body.append(f'<line x1="{bsx(0.24):.1f}" y1="{ly - 2.5}" x2="{bsx(0.30):.1f}" y2="{ly - 2.5}" stroke="{color}" stroke-width="1.8" stroke-linecap="round"/>')
        body.append(_text(bsx(0.32), ly, label.split(" (")[0], size=7))
    return _svg(h, body)


# --------------------------------------------------------------------------- Fig. 3
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
            v = report["tools"][tool]["scores"]["all"][metric]
            length = v / vmax * w
            body.append(_hbar(x0, y, length, thick, color))
            body.append(_text(x0 + length + 3, y + thick / 2 + 2.5, fmt(v), size=7))
            if pi == 0:
                body.append(_text(label_w - 8, y + thick / 2 + 2.5, label, size=7.5, anchor="end"))
        body.append(f'<line x1="{x0}" y1="{top - 4}" x2="{x0}" y2="{top + rows * row_h}" stroke="{INK_2}" stroke-width="0.8"/>')
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
    corpus = json.loads((DATA / "corpus_comparison_report.json").read_text(encoding="utf-8"))
    retrieval = json.loads((DATA / "retrieval_eval_report.json").read_text(encoding="utf-8"))
    for stale in OUT.glob("fig*_*.png"):
        stale.unlink()
    render("fig1_architecture", fig_architecture())
    render("fig2_benchmark", fig_benchmark(corpus))
    render("fig3_retrieval", fig_retrieval(retrieval))
    print("Done:", OUT)


if __name__ == "__main__":
    sys.exit(main())
