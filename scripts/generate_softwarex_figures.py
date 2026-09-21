#!/usr/bin/env python3
"""Generate SoftareX figures from the corpus comparison report (no matplotlib).

Writes SVG bar charts under papers/softwarex/figures/ — data-driven, no gen-AI art.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data" / "outputs" / "corpus_comparison_report.json"
OUT = ROOT / "papers" / "softwarex" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# SoftareX-friendly palette (avoid purple-on-white AI cliché)
COLORS = {
    "chromerag_coverage": "#0B6E4F",
    "chromerag": "#1B9AAA",
    "chromerag_precision": "#3D5A80",
    "trafilatura": "#E09F3E",
    "markitdown": "#9B2226",
    "readability": "#6C757D",
    "markdownify": "#AE2012",
    "html2text": "#BB3E03",
    "beautifulsoup_text": "#CA6702",
}


def _bar_chart(
    title: str,
    series: list[tuple[str, float]],
    ylabel: str,
    out: Path,
    higher_better: bool = True,
    ymax: float | None = None,
) -> None:
    width, height = 720, 420
    left, right, top, bottom = 160, 40, 50, 70
    plot_w = width - left - right
    plot_h = height - top - bottom
    vals = [v for _, v in series]
    ymax = ymax if ymax is not None else max(vals + [0.01]) * 1.15
    n = len(series)
    gap = 12
    bar_w = (plot_w - gap * (n + 1)) / max(n, 1)

    bars = []
    labels = []
    for i, (name, val) in enumerate(series):
        x = left + gap + i * (bar_w + gap)
        h = (val / ymax) * plot_h if ymax else 0
        y = top + plot_h - h
        color = COLORS.get(name, "#333333")
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
            f'fill="{color}" rx="2"/>'
        )
        bars.append(
            f'<text x="{x + bar_w/2:.1f}" y="{y - 6:.1f}" text-anchor="middle" '
            f'font-size="11" font-family="Helvetica,Arial,sans-serif">{val:.3f}</text>'
        )
        labels.append(
            f'<text x="{x + bar_w/2:.1f}" y="{height - 28}" text-anchor="middle" '
            f'font-size="10" font-family="Helvetica,Arial,sans-serif" '
            f'transform="rotate(-28 {x + bar_w/2:.1f},{height - 28})">{name}</text>'
        )

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#FFFFFF"/>
  <text x="{width/2}" y="28" text-anchor="middle" font-size="15" font-weight="600"
        font-family="Helvetica,Arial,sans-serif">{title}</text>
  <text x="18" y="{top + plot_h/2}" text-anchor="middle" font-size="11"
        font-family="Helvetica,Arial,sans-serif"
        transform="rotate(-90 18,{top + plot_h/2})">{ylabel}</text>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}" stroke="#222" stroke-width="1"/>
  <line x1="{left}" y1="{top+plot_h}" x2="{left+plot_w}" y2="{top+plot_h}" stroke="#222" stroke-width="1"/>
  {''.join(bars)}
  {''.join(labels)}
  <text x="{left}" y="{height - 8}" font-size="9" fill="#555"
        font-family="Helvetica,Arial,sans-serif">Source: corpus_comparison_report.json · higher={'better' if higher_better else 'worse'}</text>
</svg>
"""
    out.write_text(svg, encoding="utf-8")
    print(f"Wrote {out}")


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    summary = report["summary"]
    order = [
        "chromerag_coverage",
        "chromerag",
        "trafilatura",
        "markitdown",
        "chromerag_precision",
        "readability",
    ]
    fbal = [(m, float(summary[m]["avg_f_balanced"])) for m in order if m in summary]
    recall = [(m, float(summary[m]["avg_content_recall"])) for m in order if m in summary]
    noise = [(m, float(summary[m]["avg_noise_retention"])) for m in order if m in summary]

    _bar_chart(
        "Fig. 1 — Fbal on 238 scoreable pages",
        fbal,
        "Fbal ↑",
        OUT / "fig1_fbal.svg",
        higher_better=True,
        ymax=1.0,
    )
    _bar_chart(
        "Fig. 2 — Content recall",
        recall,
        "Recall ↑",
        OUT / "fig2_recall.svg",
        higher_better=True,
        ymax=1.0,
    )
    _bar_chart(
        "Fig. 3 — Noise retention (lower is better)",
        noise,
        "Noise retention ↓",
        OUT / "fig3_noise.svg",
        higher_better=False,
        ymax=0.4,
    )

    # Corpus accounting figure (simple stacked counts)
    listed = int(report.get("corpus_urls_listed") or report.get("corpus_url_count") or 373)
    fetched = int(report.get("n_fetched") or report.get("n_pages") or 277)
    scoreable = int(report.get("n_scoreable") or 238)
    thin = int(report.get("n_thin") or max(fetched - scoreable, 0))
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="720" height="280" viewBox="0 0 720 280">
  <rect width="100%" height="100%" fill="#FFFFFF"/>
  <text x="360" y="28" text-anchor="middle" font-size="15" font-weight="600"
        font-family="Helvetica,Arial,sans-serif">Fig. 4 — Corpus accounting (honesty gate)</text>
  <rect x="80" y="70" width="560" height="36" fill="#D9E2EC" rx="4"/>
  <text x="90" y="94" font-size="13" font-family="Helvetica,Arial,sans-serif">Listed URLs: {listed}</text>
  <rect x="80" y="120" width="{560 * fetched / listed:.1f}" height="36" fill="#1B9AAA" rx="4"/>
  <text x="90" y="144" font-size="13" fill="#fff" font-family="Helvetica,Arial,sans-serif">Fetched HTML: {fetched}</text>
  <rect x="80" y="170" width="{560 * scoreable / listed:.1f}" height="36" fill="#0B6E4F" rx="4"/>
  <text x="90" y="194" font-size="13" fill="#fff" font-family="Helvetica,Arial,sans-serif">Scoreable (means): {scoreable}</text>
  <rect x="{80 + 560 * scoreable / listed:.1f}" y="170" width="{560 * thin / listed:.1f}" height="36" fill="#9B2226" rx="4"/>
  <text x="360" y="240" text-anchor="middle" font-size="11" fill="#444"
        font-family="Helvetica,Arial,sans-serif">Thin={thin} excluded from averages · caller must render JS shells first</text>
</svg>
"""
    path = OUT / "fig4_corpus_gate.svg"
    path.write_text(svg, encoding="utf-8")
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
