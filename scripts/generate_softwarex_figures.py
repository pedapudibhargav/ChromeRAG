#!/usr/bin/env python3
"""Generate SoftareX figures as HTML (real fonts) + rasterize via Playwright if available.

Fallback: writes SVG with Helvetica text (vector; Word can use PNG from screenshots).
Primary output for Word embed: high-DPI PNG from Chromium screenshot.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data" / "outputs" / "corpus_comparison_report.json"
OUT = ROOT / "papers" / "softwarex" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

LABELS = {
    "chromerag_coverage": "ChromeRAG (coverage)",
    "chromerag": "ChromeRAG (balanced)",
    "chromerag_precision": "ChromeRAG (precision)",
    "trafilatura": "Trafilatura",
    "markitdown": "MarkItDown",
    "readability": "Readability",
}

COLORS = {
    "chromerag_coverage": "#0B6E4F",
    "chromerag": "#1B9AAA",
    "chromerag_precision": "#3D5A80",
    "trafilatura": "#C47B0A",
    "markitdown": "#9B2226",
    "readability": "#5C6770",
}


def _hbar_card(
    fig_id: str,
    title: str,
    series: list[tuple[str, float]],
    xlabel: str,
    *,
    xmax: float,
    note: str,
) -> str:
    rows = []
    for key, val in series:
        pct = 100.0 * val / xmax if xmax else 0
        label = LABELS.get(key, key)
        color = COLORS.get(key, "#333")
        rows.append(
            f"""
      <div class="row">
        <div class="ylab">{label}</div>
        <div class="track">
          <div class="bar" style="width:{pct:.2f}%;background:{color}"></div>
          <span class="val">{val:.3f}</span>
        </div>
      </div>"""
        )
    ticks = "".join(
        f'<span style="left:{100*f:.0f}%">{xmax*f:.2f}</span>' for f in (0, 0.25, 0.5, 0.75, 1.0)
    )
    return f"""
  <section class="card" id="{fig_id}">
    <h2>{title}</h2>
    <p class="note">{note}</p>
    <div class="chart">
      {''.join(rows)}
      <div class="axis">
        <div class="ticks">{ticks}</div>
        <div class="xlabel">{xlabel}</div>
      </div>
    </div>
  </section>"""


def _funnel_card(listed: int, fetched: int, scoreable: int, thin: int) -> str:
    def row(title: str, n: int, denom: int, color: str, light_text: bool = True) -> str:
        pct = 100.0 * n / denom if denom else 0
        tc = "#fff" if light_text else "#1a1a1a"
        return f"""
      <div class="funnel-row">
        <div class="funnel-bar" style="width:{pct:.1f}%;background:{color};color:{tc}">
          <strong>{title}</strong>
          <span>n = {n}</span>
        </div>
      </div>"""

    return f"""
  <section class="card" id="fig4">
    <h2>Corpus honesty gate</h2>
    <p class="note">Listed URLs → fetched HTML → scoreable pages used in means (thin shells excluded)</p>
    <div class="funnel">
      {row("Listed URLs in public corpus", listed, listed, "#D9E2EC", light_text=False)}
      {row("Fetched HTML successfully", fetched, listed, "#1B9AAA")}
      {row("Scoreable (recall ≥ 0.05) — used in means", scoreable, listed, "#0B6E4F")}
      {row("Thin / JS-shell pages excluded", thin, listed, "#9B2226")}
    </div>
    <p class="foot">Leaderboard means use scoreable pages only; both counts are reported in the paper.</p>
  </section>"""


def write_html(report: dict) -> Path:
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
    n_score = int(report.get("n_scoreable") or 238)
    note = f"Mean over {n_score} scoreable pages (content recall ≥ 0.05)"
    noise_max = max(v for _, v in noise) * 1.15

    listed = int(report.get("corpus_urls_listed") or 373)
    fetched = int(report.get("n_fetched") or 277)
    scoreable = int(report.get("n_scoreable") or 238)
    thin = int(report.get("n_thin") or max(fetched - scoreable, 0))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>ChromeRAG SoftareX figures</title>
<style>
  :root {{
    --ink: #1a1a1a;
    --muted: #5c6770;
    --line: #e6e8eb;
    --font: "Helvetica Neue", Helvetica, Arial, sans-serif;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px; background: #fff; color: var(--ink);
    font-family: var(--font);
  }}
  .card {{
    width: 1180px; margin: 0 0 48px; padding: 28px 40px 28px 32px;
    background: #fff; border: 1px solid #eee;
  }}
  h2 {{
    margin: 0 0 6px; font-size: 22px; font-weight: 650; letter-spacing: -0.01em;
  }}
  .note {{ margin: 0 0 18px; color: var(--muted); font-size: 13px; }}
  .row {{
    display: grid; grid-template-columns: 230px 1fr; gap: 14px;
    align-items: center; margin: 0 0 12px;
  }}
  .ylab {{
    text-align: right; font-size: 14px; font-weight: 500; line-height: 1.25;
  }}
  .track {{
    position: relative; height: 34px; background: #f4f6f8; border-radius: 4px;
    border: 1px solid var(--line); overflow: visible;
  }}
  .bar {{
    height: 100%; border-radius: 3px 0 0 3px; min-width: 2px;
  }}
  .val {{
    position: absolute; top: 50%; transform: translateY(-50%);
    font-size: 13px; font-weight: 650; color: var(--ink); white-space: nowrap;
  }}
  .axis {{ margin: 8px 0 0 244px; }}
  .ticks {{
    position: relative; height: 18px; border-top: 1px solid #222; margin-top: 4px;
  }}
  .ticks span {{
    position: absolute; top: 6px; transform: translateX(-50%);
    font-size: 12px; color: var(--muted);
  }}
  .xlabel {{
    text-align: center; margin-top: 8px; font-size: 13px; font-weight: 500;
  }}
  .funnel {{ margin-top: 8px; }}
  .funnel-row {{ margin: 0 0 14px; }}
  .funnel-bar {{
    min-height: 64px; border-radius: 6px; padding: 14px 18px;
    display: flex; flex-direction: column; gap: 4px;
    font-size: 15px;
  }}
  .funnel-bar span {{ font-size: 14px; opacity: 0.95; }}
  .foot {{ margin: 12px 0 0; color: var(--muted); font-size: 12px; }}
</style>
</head>
<body>
{_hbar_card("fig1", "Balanced F-score (Fbal)", fbal, "Fbal (higher is better)", xmax=1.0, note=note)}
{_hbar_card("fig2", "Content recall", recall, "Content recall (higher is better)", xmax=1.0, note=note)}
{_hbar_card("fig3", "Noise retention (chrome / boilerplate kept)", noise, "Noise retention (lower is better)", xmax=noise_max, note=note)}
{_funnel_card(listed, fetched, scoreable, thin)}
<script>
  // Always place numeric labels just past the end of the colored bar
  document.querySelectorAll('.row').forEach(row => {{
    const bar = row.querySelector('.bar');
    const val = row.querySelector('.val');
    if (!bar || !val) return;
    const pct = parseFloat(bar.style.width);
    val.style.left = 'calc(' + pct + '% + 8px)';
    val.style.right = 'auto';
    val.style.color = '#1a1a1a';
  }});
</script>
</body>
</html>
"""
    path = OUT / "_charts.html"
    path.write_text(html, encoding="utf-8")
    print(f"Wrote {path}")
    return path


def rasterize_with_playwright(html_path: Path) -> bool:
    """Screenshot each .card to PNG via Playwright Python API or npx."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        # Try npx playwright screenshot of full page then crop — weaker fallback
        return rasterize_with_npx(html_path)

    out_map = {
        "fig1": OUT / "fig1_fbal.png",
        "fig2": OUT / "fig2_recall.png",
        "fig3": OUT / "fig3_noise.png",
        "fig4": OUT / "fig4_corpus_gate.png",
    }
    uri = html_path.resolve().as_uri()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 900}, device_scale_factor=3)
        page.goto(uri, wait_until="networkidle")
        for fig_id, dest in out_map.items():
            loc = page.locator(f"#{fig_id}")
            loc.screenshot(path=str(dest), type="png")
            print(f"Wrote {dest} ({dest.stat().st_size} bytes)")
        browser.close()
    return True


def rasterize_with_npx(html_path: Path) -> bool:
    """Last resort: serve file and use cursor playwright MCP externally — return False."""
    print("playwright Python package not installed; trying `python -m playwright` install…", file=sys.stderr)
    return False


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    html_path = write_html(report)
    ok = rasterize_with_playwright(html_path)
    if not ok:
        print(
            "Open figures/_charts.html in a browser (or Playwright MCP) and screenshot "
            "#fig1..#fig4 to fig1_fbal.png … fig4_corpus_gate.png at deviceScaleFactor=3, "
            "then run: python scripts/fill_softwarex_docx.py && python scripts/embed_softwarex_figures.py",
            file=sys.stderr,
        )
        raise SystemExit(
            "playwright not installed in this venv. HTML source is ready at figures/_charts.html"
        )
    print("Done. Captions for Word:")
    print("  Figure 1. Balanced F-score (Fbal) on 238 scoreable pages (higher is better).")
    print("  Figure 2. Content recall on the same scoreable set (higher is better).")
    print("  Figure 3. Noise retention — chrome/boilerplate kept (lower is better).")
    print(
        "  Figure 4. Corpus honesty gate: listed URLs → fetched HTML → scoreable pages "
        "(thin/JS shells excluded)."
    )


if __name__ == "__main__":
    main()
