#!/usr/bin/env python3
"""Render the SoftwareX figures (revision 1, ChromeRAG 0.1.5) from the result files.

Every number in a figure is read from a file in the repository (for the human rating
aggregates, from the output folder of the planned analysis); none is typed in here.
See FIGURE_SPECS.md for the source of each panel.

Figures are drawn at print size (6.5 in text width, sizes in points), sans-serif
text of at least 7 pt, no titles inside the artwork (captions carry them), no
vertical grid lines. Output: SVG, vector PDF and a 300 dpi PNG for Word, all with
the same base name in papers/softwarex/figures/. Each tool keeps one colour and
one marker shape in every figure, so colour is never the only cue.

Needs a local Chrome/Chromium (headless) to rasterize the SVGs. Chrome runs with a
throw-away profile and a dead proxy, so it makes no network requests.

Usage:
  python scripts/generate_softwarex_figures.py [--prereg-dir DIR]

DIR holds results.json and ai_by_forum.json of the planned human analysis
(aggregates only); default: out/human_set under the repository root, or $CHROMERAG_PREREG_DIR.
Make them with:
  PYTHONPATH=src:. python -m poc.human_set_analysis --out out/human_set
  PYTHONPATH=src:. python -m poc.human_set_ai_by_forum --out out/human_set/ai_by_forum.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "papers" / "softwarex" / "figures"
REV_ROWS = ROOT / "evaluations" / "2026-11-final" / "results" / "revision_rows"
P03 = REV_ROWS / "p03_extra_rows.json"
SPEED = REV_ROWS / "speed.json"
MANIFEST = ROOT / "evaluations" / "2026-10-v0.1.3" / "strict_split_manifest.json"
MODEL = ROOT / "src" / "chromerag" / "assets" / "lbc_stage1.npz"
RULES = ROOT / "src" / "chromerag" / "rules"
CLI = ROOT / "src" / "chromerag" / "cli.py"
PREREG_DEFAULT = ROOT / "out" / "human_set"

# Files of the v0.1.4 manuscript that the revision-1 figures replace.
OBSOLETE = ("fig2_wcxb_test", "fig2_benchmark", "fig3_frontier", "fig3_retrieval", "fig4_retrieval", "fig5_judge")

WIDTH = 468  # pt, 6.5 in
DPI = 300
FONT = "Arial, Helvetica, sans-serif"
INK = "#1f1f1d"
INK_2 = "#4a4945"
MUTED = "#8a8983"
GRID = "#e4e3df"
SURFACE = "#ffffff"
ACCENT = "#1f4e9c"  # ChromeRAG

# One colour and one marker per tool in every figure (checked for colour-vision
# deficiency separation; shapes are the second cue for the grey/brown pair).
TOOLS = {
    "chromerag_balanced": ("ChromeRAG balanced", ACCENT, "circle"),
    "trafilatura": ("Trafilatura", "#e69f00", "square"),
    "rs_trafilatura": ("rs-trafilatura", "#2ab3a0", "diamond"),
    "readability": ("Readability", "#666666", "tri_up"),
    "boilerpy3_default": ("BoilerPy3", "#a173cf", "tri_down"),
    "justext": ("jusText", "#a8501e", "plus"),
    "markitdown": ("MarkItDown", "#b8b8b8", "circle"),
}
HUMAN = ("Human majority", "#000000", "circle")
JUDGES = (  # AI judges: three greys and three shapes
    ("gpt", "GPT", "#5c5c5c", "square"),
    ("grok", "Grok", "#8c8c8c", "diamond"),
    ("gemini", "Gemini", "#b0b0b0", "tri_up"),
)

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome",
    "chromium",
    "chromium-browser",
]


# --------------------------------------------------------------------------- drawing helpers
def _text(x, y, s, *, size=8, anchor="start", weight="normal", fill=INK, style="normal", halo=False):
    """Text; halo=True paints a white outline under the glyphs so grid lines never cross a label."""
    h = f' stroke="{SURFACE}" stroke-width="2.4" stroke-linejoin="round" paint-order="stroke"' if halo else ""
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" text-anchor="{anchor}" '
        f'font-weight="{weight}" font-style="{style}" fill="{fill}"{h}>{escape(str(s))}</text>'
    )


def _line(x1, y1, x2, y2, color=INK_2, width=0.6, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{color}" stroke-width="{width}"{d}/>'


def _svg(height: float, body: list[str]) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}pt" height="{height}pt" '
        f'viewBox="0 0 {WIDTH} {height}" font-family="{FONT}">'
        f'<rect width="{WIDTH}" height="{height}" fill="{SURFACE}"/>' + "".join(body) + "</svg>"
    )


def _marker(shape: str, cx: float, cy: float, r: float, fill: str, ring: str = SURFACE, ring_w: float = 0.7) -> str:
    """Filled marker of radius r (pt) with a thin surface ring, so overlapping marks stay separate."""
    st = f'fill="{fill}" stroke="{ring}" stroke-width="{ring_w}" stroke-linejoin="round"'
    if shape == "circle":
        return f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" {st}/>'
    if shape == "square":
        s = r * 1.65
        return f'<rect x="{cx - s / 2:.2f}" y="{cy - s / 2:.2f}" width="{s:.2f}" height="{s:.2f}" {st}/>'
    if shape == "diamond":
        k = r * 1.3
        pts = [(cx, cy - k), (cx + k, cy), (cx, cy + k), (cx - k, cy)]
    elif shape == "tri_up":
        k = r * 1.3
        pts = [(cx, cy - k), (cx + k * 0.9, cy + k * 0.62), (cx - k * 0.9, cy + k * 0.62)]
    elif shape == "tri_down":
        k = r * 1.3
        pts = [(cx, cy + k), (cx + k * 0.9, cy - k * 0.62), (cx - k * 0.9, cy - k * 0.62)]
    elif shape == "plus":
        a, b = r * 1.2, r * 0.42
        pts = [
            (cx - b, cy - a), (cx + b, cy - a), (cx + b, cy - b), (cx + a, cy - b), (cx + a, cy + b), (cx + b, cy + b),
            (cx + b, cy + a), (cx - b, cy + a), (cx - b, cy + b), (cx - a, cy + b), (cx - a, cy - b), (cx - b, cy - b),
        ]
    else:
        raise ValueError(shape)
    return '<polygon points="' + " ".join(f"{x:.2f},{y:.2f}" for x, y in pts) + f'" {st}/>'


def _text_w(s: str, size: float, bold: bool = False) -> float:
    """Rough Arial advance width (pt), only used to space legend entries."""
    narrow = set("ijlrtf.,:;!|()[]' ")
    wide = set("mwMW")
    w = sum(0.28 if c in narrow else 0.83 if c in wide else 0.67 if c.isupper() else 0.55 for c in s)
    return w * size * (1.06 if bold else 1.0)


def _signed(v: float, digits: int) -> str:
    s = f"{v:+.{digits}f}"
    if float(s) == 0:
        s = f"{0:.{digits}f}"
    return s.replace("-", "−")


def _check_range(values, lo, hi, what):
    bad = [v for v in values if not lo <= v <= hi]
    if bad:
        raise SystemExit(f"{what}: values {bad} fall outside the axis {lo}..{hi}; widen the axis")


# --------------------------------------------------------------------------- Fig. 1
def _pipeline_facts() -> dict:
    import numpy as np
    import yaml

    sys.path.insert(0, str(ROOT / "src"))
    from chromerag.config import PipelineConfig

    rules = 0
    for f in sorted(RULES.glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        rules += len(data["rules"] if isinstance(data, dict) else data)
    model = np.load(MODEL, allow_pickle=False)
    n_trees, n_features = len(model["roots"]), int(model["meta"][1])
    model_bytes = json.loads(MANIFEST.read_text(encoding="utf-8"))["shipped_lbc_stage1_npz"]["bytes"]
    if model_bytes != MODEL.stat().st_size:
        raise SystemExit("Shipped model size differs from the strict-split manifest")
    m = re.search(r'"--min-pages",\s*type=int,\s*default=(\d+)', CLI.read_text(encoding="utf-8"))
    thresholds = [PipelineConfig.from_priority(p).lbc_threshold for p in ("coverage", "balanced", "precision")]
    return {
        "rules": rules,
        "trees": n_trees,
        "features": n_features,
        "kb": round(model_bytes / 1000),
        "thresholds": thresholds,
        "min_pages": int(m.group(1)),
    }


def fig_architecture(f: dict) -> str:
    th = " / ".join(f"{t:.2f}" for t in f["thresholds"])
    # (number, title lines, small-text lines, width in pt)
    stages = [
        ("1", ("Input", "gate"), ("thin / JS", "warnings"), 44),
        ("2", ("Schema", "harvest"), ("JSON-LD,", "Microdata", "→ front", "matter"), 48),
        ("3", ("Clean, rules,", "STCE"), (f"{f['rules']} YAML rules,", "generic detectors", "(each switchable);", "STCE only with", "a site model"), 66),
        ("4", ("Chrome", "prune"), ("landmarks,", "class words"), 46),
        ("5", ("Learned", "block filter"), (f"{f['features']} features,", f"{f['trees']} trees,", f"{f['kb']} KB, NumPy;", "thresholds", th), 68),
        ("6", ("Tables +", "Markdown"), ("pipe tables,", "document", "order"), 46),
    ]
    in_w, out_w, gap, left = 28, 56, 7, 4
    used = left * 2 + in_w + out_w + sum(s[3] for s in stages) + 7 * gap
    if used > WIDTH + 0.5:
        raise SystemExit(f"Figure 1 boxes too wide ({used} pt)")
    left += (WIDTH - used) / 2
    top, bh = 6, 104
    lh = 34  # height of the chromerag learn box
    h = top + bh + 20 + lh + 6
    body: list[str] = [
        '<defs><marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" '
        f'orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" fill="{MUTED}"/></marker>'
        '<marker id="arrb" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" '
        f'orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" fill="{ACCENT}"/></marker></defs>'
    ]
    mid = top + bh / 2

    def arrow(x0, x1):
        body.append(
            f'<line x1="{x0 + 1:.1f}" y1="{mid}" x2="{x1 - 1:.1f}" y2="{mid}" stroke="{MUTED}" '
            f'stroke-width="1" marker-end="url(#arr)"/>'
        )

    x = left
    body.append(f'<rect x="{x:.1f}" y="{top}" width="{in_w}" height="{bh}" rx="4" fill="#f1f0ec"/>')
    body.append(_text(x + in_w / 2, mid + 3, "HTML", size=8.5, anchor="middle", weight="bold"))
    x += in_w
    centers = []
    for num, title, small, bw in stages:
        arrow(x, x + gap)
        x += gap
        core = num == "5"
        fill = "#e8eff9" if core else "#f7f7f5"
        stroke = ACCENT if core else "#cfcec8"
        body.append(
            f'<rect x="{x:.1f}" y="{top}" width="{bw}" height="{bh}" rx="4" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{1.4 if core else 0.8}"/>'
        )
        cx = x + bw / 2
        centers.append(cx)
        body.append(_text(cx, top + 13, num, size=8, anchor="middle", weight="bold", fill=ACCENT if core else MUTED))
        for i, t in enumerate(title):
            body.append(_text(cx, top + 26 + i * 10, t, size=8, anchor="middle", weight="bold"))
        y = top + 26 + len(title) * 10 + 4
        for i, t in enumerate(small):
            body.append(_text(cx, y + i * 9, t, size=7, anchor="middle", fill=INK_2))
        x += bw
    arrow(x, x + gap)
    x += gap
    body.append(f'<rect x="{x:.1f}" y="{top}" width="{out_w}" height="{bh}" rx="4" fill="#f1f0ec"/>')
    out_lines = (("Markdown", True), ("+ front matter", False), ("+ chunks", False), ("+ diagnostics", False))
    y0 = mid - (len(out_lines) - 1) * 10 / 2 + 3
    for i, (t, bold) in enumerate(out_lines):
        body.append(_text(x + out_w / 2, y0 + i * 10, t, size=8.5 if bold else 7, anchor="middle",
                          weight="bold" if bold else "normal", fill=INK if bold else INK_2))

    # chromerag learn (optional) feeds stage 3
    lw, ly = 150, top + bh + 20
    lx = centers[2] - lw / 2
    body.append(
        f'<rect x="{lx:.1f}" y="{ly}" width="{lw}" height="{lh}" rx="4" fill="{SURFACE}" '
        f'stroke="{ACCENT}" stroke-width="1" stroke-dasharray="3 2"/>'
    )
    body.append(_text(centers[2], ly + 13, "chromerag learn (optional)", size=8, anchor="middle", weight="bold"))
    body.append(_text(centers[2], ly + 25, f"≥ {f['min_pages']} pages of one site → site model",
                      size=7, anchor="middle", fill=INK_2))
    body.append(
        f'<line x1="{centers[2]:.1f}" y1="{ly - 1}" x2="{centers[2]:.1f}" y2="{top + bh + 2}" '
        f'stroke="{ACCENT}" stroke-width="1" marker-end="url(#arrb)"/>'
    )
    return _svg(h, body)


# --------------------------------------------------------------------------- Fig. 2
TYPE_ROWS = ("all", "article", "documentation", "service", "forum", "listing", "product", "collection")
DOT_TOOLS = ("chromerag_balanced", "trafilatura", "rs_trafilatura", "readability", "boilerpy3_default", "justext")


def _wcxb_rows(p03: dict) -> list[dict]:
    rows = []
    for key in TYPE_ROWS:
        if key == "all":
            a = p03["all_511"]
            diff = a["paired"]["balanced_minus_trafilatura"]["f1"]
            rows.append({
                "label": f"All ({a['n']})",
                "f1": {t: a["summary"][t]["f1"] for t in DOT_TOOLS},
                "diff": diff["mean"], "ci": diff["ci95"], "n": a["n"],
            })
        else:
            t_ = p03["iii_per_type"][key]
            diff = t_["balanced_minus_trafilatura_f1"]
            rows.append({
                "label": f"{key.capitalize()} ({t_['n']})",
                "f1": {t: t_["mean_f1"][t] for t in DOT_TOOLS},
                "diff": diff["mean"], "ci": diff["ci95"], "n": t_["n"],
            })
    return rows


def fig_wcxb_types(p03: dict) -> str:
    rows = _wcxb_rows(p03)
    label_w = 86
    legend_h, tag_h = 14, 12
    top = legend_h + tag_h + 10
    row_h = 19
    plot_h = len(rows) * row_h
    h = top + plot_h + 30
    ax0, ax1 = label_w + 6, 318  # panel (a)
    bx0, bx1 = 350, WIDTH - 40  # panel (b); its values sit in a column on the right
    lo_a, hi_a = 0.3, 1.0
    _check_range([v for r in rows for v in r["f1"].values()], lo_a, hi_a, "Fig. 2a")
    lo_b = min(r["ci"][0] for r in rows)
    hi_b = max(r["ci"][1] for r in rows)
    lo_b, hi_b = (int(lo_b / 0.05) - (lo_b < 0)) * 0.05, (int(hi_b / 0.05) + 1) * 0.05
    sa = lambda v: ax0 + (v - lo_a) / (hi_a - lo_a) * (ax1 - ax0)  # noqa: E731
    sb = lambda v: bx0 + (v - lo_b) / (hi_b - lo_b) * (bx1 - bx0)  # noqa: E731
    body: list[str] = []

    # legend (panel a tools), one row across the top
    entries = [TOOLS[t] for t in ("chromerag_balanced", "trafilatura", "rs_trafilatura", "readability", "boilerpy3_default", "justext")]
    widths = [12 + _text_w(name, 7.5) + 12 for name, _, _ in entries]
    lx = (WIDTH - sum(widths)) / 2
    for (name, color, shape), w in zip(entries, widths):
        body.append(_marker(shape, lx + 4, 7, 3.4 if shape == "circle" else 3.0, color))
        body.append(_text(lx + 11, 9.7, name, size=7.5, fill=INK))
        lx += w

    py0, py1 = top - 4, top + plot_h + 2
    # panel tags and titles
    body.append(_text(4, top - 8, "(a)", size=8.5, weight="bold"))
    body.append(_text(ax0, top - 8, "Mean word F1 per tool", size=7.5, fill=INK_2))
    body.append(_text(bx0 - 22, top - 8, "(b)", size=8.5, weight="bold"))
    body.append(_text(bx0, top - 8, "ChromeRAG − Trafilatura", size=7.5, fill=INK_2))

    # row guides (horizontal) and the separator under "All"
    for i, r in enumerate(rows):
        y = top + i * row_h + row_h / 2
        body.append(_line(ax0, y, ax1, y, GRID, 0.6))
        body.append(_line(bx0, y, bx1, y, GRID, 0.6))
        body.append(_text(label_w, y + 2.6, r["label"], size=7.5, anchor="end", weight="bold" if i == 0 else "normal"))
    sep = top + row_h
    body.append(_line(4, sep, WIDTH - 4, sep, "#c9c8c2", 0.5, "2 2"))

    # axes
    for x0, x1, ticks, fmt, sx, title in (
        (ax0, ax1, [round(lo_a + 0.1 * k, 1) for k in range(int(round((hi_a - lo_a) / 0.1)) + 1)], lambda t: f"{t:.1f}", sa, "Word F1"),
        (bx0, bx1, [round(0.1 * k, 1) for k in range(int(lo_b * 10) - 1, int(hi_b * 10) + 2) if lo_b - 1e-9 <= 0.1 * k <= hi_b + 1e-9],
         lambda t: _signed(t, 1) if t else "0", sb, "Difference in F1 (95% CI)"),
    ):
        body.append(_line(x0, py1, x1, py1, INK_2, 0.7))
        for t in ticks:
            body.append(_line(sx(t), py1, sx(t), py1 + 2.5, INK_2, 0.7))
            body.append(_text(sx(t), py1 + 10.5, fmt(t), size=7, anchor="middle", fill=INK_2))
        body.append(_text((x0 + x1) / 2, py1 + 21, title, size=7.5, anchor="middle", fill=INK_2))
    # zero reference in (b)
    body.append(_line(sb(0), py0, sb(0), py1, INK_2, 0.8))

    for i, r in enumerate(rows):
        y = top + i * row_h + row_h / 2
        for t in DOT_TOOLS:  # ChromeRAG first and larger: smaller marks drawn over it stay visible
            name, color, shape = TOOLS[t]
            core = t == "chromerag_balanced"
            body.append(_marker(shape, sa(r["f1"][t]), y, 4.0 if core else 2.6, color, ring_w=0.6))
        v = r["f1"]["chromerag_balanced"]
        body.append(_text(sa(v), y - 5.6, f"{v:.3f}", size=7, anchor="middle", fill=INK, halo=True))
        lo, hi = r["ci"]
        body.append(_line(sb(lo), y, sb(hi), y, ACCENT, 1.3))
        for e in (lo, hi):
            body.append(_line(sb(e), y - 2.2, sb(e), y + 2.2, ACCENT, 1.0))
        body.append(_marker("circle", sb(r["diff"]), y, 2.5, ACCENT, ring_w=0.7))
        body.append(_text(WIDTH - 4, y + 2.5, _signed(r["diff"], 3), size=7, anchor="end", fill=INK))
    return _svg(h, body)


# --------------------------------------------------------------------------- Fig. 3
SPEED_TOOLS = ("chromerag_balanced", "trafilatura", "readability", "justext")


def fig_speed_f1(speed: dict, p03: dict) -> str:
    pts = []
    for t in SPEED_TOOLS:
        s = speed["tools"][t]
        pts.append((t, s["median_ms"], s["p90_ms"], p03["all_511"]["summary"][t]["f1"]))
    xmin, xmax, ymin, ymax = 0.0, 100.0, 0.65, 0.92
    _check_range([p[1] for p in pts] + [p[2] for p in pts], xmin, xmax, "Fig. 3 time")
    _check_range([p[3] for p in pts], ymin, ymax, "Fig. 3 F1")
    x0, y0, x1 = 50, 8, WIDTH - 14
    ph = 132
    h = y0 + ph + 32
    sx = lambda v: x0 + (v - xmin) / (xmax - xmin) * (x1 - x0)  # noqa: E731
    sy = lambda v: y0 + ph - (v - ymin) / (ymax - ymin) * ph  # noqa: E731
    body: list[str] = []
    yt = [0.65, 0.70, 0.75, 0.80, 0.85, 0.90]
    for t in yt:
        body.append(_line(x0, sy(t), x1, sy(t), GRID, 0.6))
        body.append(_text(x0 - 5, sy(t) + 2.5, f"{t:.2f}", size=7, anchor="end", fill=INK_2))
    body.append(_line(x0, y0 + ph, x1, y0 + ph, INK_2, 0.7))
    body.append(_line(x0, y0, x0, y0 + ph, INK_2, 0.7))
    for t in range(0, 101, 10):
        body.append(_line(sx(t), y0 + ph, sx(t), y0 + ph + 2.5, INK_2, 0.7))
        body.append(_text(sx(t), y0 + ph + 11, str(t), size=7, anchor="middle", fill=INK_2))
    body.append(_text((x0 + x1) / 2, y0 + ph + 24, "Time per page (ms): marker at the median, bar to the 90th percentile",
                      size=7.5, anchor="middle", fill=INK_2))
    yc = y0 + ph / 2
    body.append(
        f'<text x="12" y="{yc:.1f}" font-size="7.5" fill="{INK_2}" text-anchor="middle" '
        f'transform="rotate(-90 12 {yc:.1f})">Word F1, WCXB test (511 pages)</text>'
    )
    for t, med, p90, f1 in pts:
        name, color, shape = TOOLS[t]
        core = t == "chromerag_balanced"
        y = sy(f1)
        body.append(_line(sx(med), y, sx(p90), y, color, 1.6))
        body.append(_line(sx(p90), y - 2.5, sx(p90), y + 2.5, color, 1.2))
        body.append(_marker(shape, sx(med), y, 4.0 if core else 3.4, color, ring_w=0.9))
        label = f"{name} ({f1:.3f}; {med:.1f} ms)"
        body.append(_text(sx(med) + 1, y - 7, label, size=7.5, anchor="start", weight="bold" if core else "normal", halo=True))
    return _svg(h, body)


# --------------------------------------------------------------------------- Fig. 4
SUBSETS = (("overall", "All"), ("forums_only", "Forums"), ("without_forums", "Without forums"))
BASELINES = (("trafilatura", "(a)", "vs Trafilatura"), ("readability", "(b)", "vs Readability"))


def _human_ai(results: dict, ai: dict) -> dict:
    """Aggregates only: net and 95% interval per baseline, subset and judge."""
    out: dict = {}
    for base, _, _ in BASELINES:
        for sub, _ in SUBSETS:
            h_ = results["main"][f"chromerag_vs_{base}"][sub]
            rows = [("human", h_["net"], h_["net_ci95"], h_["n"])]
            for jk, _, _, _ in JUDGES:
                a = ai[f"{base}/{jk}/{sub}"]
                if a["n"] != h_["n"]:
                    raise SystemExit(f"AI judge {jk} {base}/{sub} has n={a['n']}, humans n={h_['n']}")
                rows.append((jk, a["net"], a["net_ci95"], a["n"]))
            out[(base, sub)] = rows
    return out


def fig_human_ai(results: dict, ai: dict) -> str:
    data = _human_ai(results, ai)
    label_w = 116
    gap = 22
    pw = (WIDTH - label_w - gap - 8) / 2
    tag_h = 14
    row_h, group_gap = 11.5, 15
    top = tag_h + 14
    n_rows = 1 + len(JUDGES)
    group_h = n_rows * row_h
    plot_h = len(SUBSETS) * group_h + (len(SUBSETS) - 1) * group_gap
    h = top + plot_h + 30
    xmin, xmax = -1.0, 1.0
    body: list[str] = []
    names = {"human": HUMAN[0], **{k: n for k, n, _, _ in JUDGES}}
    style = {"human": (HUMAN[1], HUMAN[2]), **{k: (c, s) for k, _, c, s in JUDGES}}

    def row_y(gi, ri):
        return top + gi * (group_h + group_gap) + ri * row_h + row_h / 2

    # y labels (shared): group heading, then judge names
    for gi, (sub, sub_name) in enumerate(SUBSETS):
        n = data[(BASELINES[0][0], sub)][0][3]
        body.append(_text(4, row_y(gi, 0) - 9, f"{sub_name} ({n})", size=7.5, weight="bold"))
        for ri, (jk, *_rest) in enumerate(data[(BASELINES[0][0], sub)]):
            body.append(_text(label_w - 6, row_y(gi, ri) + 2.5, names[jk], size=7.5, anchor="end",
                              fill=INK if jk == "human" else INK_2, weight="bold" if jk == "human" else "normal"))
    py0, py1 = top - 6, top + plot_h + 3
    for pi, (base, tag, title) in enumerate(BASELINES):
        x0 = label_w + pi * (pw + gap)
        x1 = x0 + pw
        sx = lambda v, _x0=x0, _x1=x1: _x0 + (v - xmin) / (xmax - xmin) * (_x1 - _x0)  # noqa: E731
        body.append(_text(x0, 10, tag, size=8.5, weight="bold"))
        body.append(_text(x0 + 14, 10, title, size=7.5, fill=INK_2))
        for gi in range(len(SUBSETS)):
            for ri in range(n_rows):
                y = row_y(gi, ri)
                body.append(_line(x0, y, x1, y, GRID, 0.5))
        body.append(_line(x0, py1, x1, py1, INK_2, 0.7))
        for t in (-1, -0.5, 0, 0.5, 1):
            body.append(_line(sx(t), py1, sx(t), py1 + 2.5, INK_2, 0.7))
            body.append(_text(sx(t), py1 + 10.5, _signed(t, 1) if t else "0", size=7, anchor="middle", fill=INK_2))
        body.append(_text((x0 + x1) / 2, py1 + 21, "Net preference for ChromeRAG", size=7.5, anchor="middle", fill=INK_2))
        body.append(_line(sx(0), py0, sx(0), py1, INK_2, 0.8))
        for gi, (sub, _) in enumerate(SUBSETS):
            rows = data[(base, sub)]
            _check_range([v for _, net, ci, _ in rows for v in (net, *ci)], xmin, xmax, "Fig. 4")
            # draw AI judges first, human last (on top)
            for ri in list(range(1, n_rows)) + [0]:
                jk, net, (lo, hi), _ = rows[ri]
                y = row_y(gi, ri)
                color, shape = style[jk]
                human = jk == "human"
                body.append(_line(sx(lo), y, sx(hi), y, color, 1.4 if human else 1.1))
                for e in (lo, hi):
                    body.append(_line(sx(e), y - 2, sx(e), y + 2, color, 1.0 if human else 0.8))
                body.append(_marker(shape, sx(net), y, 3.4 if human else 2.6, color, ring_w=0.8 if human else 0.6))
                if human:
                    body.append(_text(sx(net), y - 5, _signed(net, 2), size=7, anchor="middle", weight="bold", halo=True))
    return _svg(h, body)


# --------------------------------------------------------------------------- output
def _chrome() -> str:
    found = next((c for c in CHROME_CANDIDATES if shutil.which(c) or Path(c).exists()), None)
    if not found:
        raise SystemExit("A Chrome/Chromium binary is needed to rasterize the figures.")
    return found


OFFLINE_FLAGS = [
    "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-pdf-header-footer",
    "--no-first-run", "--no-default-browser-check", "--disable-background-networking",
    "--disable-component-update", "--disable-sync", "--disable-extensions", "--disable-default-apps",
    "--disable-domain-reliability", "--disable-client-side-phishing-detection", "--metrics-recording-only",
    "--use-mock-keychain", "--password-store=basic",
    "--proxy-server=127.0.0.1:9", "--proxy-bypass-list=<-loopback>",  # dead proxy: no request leaves the machine
]


def _set_png_dpi(path: Path, dpi: int) -> None:
    """Write a pHYs chunk so Word and other readers see the true print resolution."""
    raw = path.read_bytes()
    ppm = round(dpi / 0.0254)
    chunks, pos = [], 8
    while pos < len(raw):
        (length,) = struct.unpack(">I", raw[pos:pos + 4])
        ctype = raw[pos + 4:pos + 8]
        end = pos + 12 + length
        if ctype != b"pHYs":
            chunks.append(raw[pos:end])
        pos = end
    data = struct.pack(">IIB", ppm, ppm, 1)
    phys = struct.pack(">I", len(data)) + b"pHYs" + data + struct.pack(">I", zlib.crc32(b"pHYs" + data) & 0xFFFFFFFF)
    path.write_bytes(raw[:8] + chunks[0] + phys + b"".join(chunks[1:]))


def render(name: str, svg: str) -> None:
    chrome = _chrome()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.svg").write_text(svg, encoding="utf-8")
    height_pt = float(svg.split('height="', 1)[1].split("pt", 1)[0])
    px_w, px_h = round(WIDTH * 4 / 3), round(height_pt * 4 / 3)
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / f"{name}.html"
        page.write_text(
            "<!doctype html><html><head><meta charset='utf-8'><style>"
            f"@page{{size:{WIDTH}pt {height_pt}pt;margin:0}}html,body{{margin:0;padding:0;background:#fff}}"
            "svg{display:block}</style></head><body>" + svg + "</body></html>",
            encoding="utf-8",
        )
        common = [chrome, f"--user-data-dir={Path(tmp) / 'profile'}", *OFFLINE_FLAGS]
        png = OUT / f"{name}.png"
        subprocess.run(
            common + [f"--force-device-scale-factor={DPI / 96}", f"--window-size={px_w},{px_h}",
                      f"--screenshot={png}", page.as_uri()],
            check=True, capture_output=True, timeout=120,
        )
        subprocess.run(
            common + [f"--print-to-pdf={OUT / (name + '.pdf')}", page.as_uri()],
            check=True, capture_output=True, timeout=120,
        )
    _set_png_dpi(png, DPI)
    print(f"Wrote {name}.svg/.png/.pdf ({WIDTH / 72:.2f} x {height_pt / 72:.2f} in)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--prereg-dir", type=Path,
                    default=Path(os.environ.get("CHROMERAG_PREREG_DIR", PREREG_DEFAULT)),
                    help="folder with results.json and ai_by_forum.json (planned human analysis)")
    args = ap.parse_args()
    p03 = json.loads(P03.read_text(encoding="utf-8"))
    speed = json.loads(SPEED.read_text(encoding="utf-8"))
    results = json.loads((args.prereg_dir / "results.json").read_text(encoding="utf-8"))
    ai = json.loads((args.prereg_dir / "ai_by_forum.json").read_text(encoding="utf-8"))

    render("fig1_architecture", fig_architecture(_pipeline_facts()))
    render("fig2_wcxb_types", fig_wcxb_types(p03))
    render("fig3_speed_f1", fig_speed_f1(speed, p03))
    render("fig4_human_ai", fig_human_ai(results, ai))
    for stem in OBSOLETE:
        for ext in ("svg", "pdf", "png"):
            (OUT / f"{stem}.{ext}").unlink(missing_ok=True)
    print("Done:", OUT)


if __name__ == "__main__":
    sys.exit(main())
