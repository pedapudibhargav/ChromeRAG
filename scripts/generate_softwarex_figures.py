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
        if pct < 30:  # narrow bar: put the label beside it so it never wraps
            return f"""
      <div class="funnel-row narrow">
        <div class="funnel-bar" style="width:{pct:.1f}%;background:{color}"></div>
        <div class="funnel-label"><strong>{title}</strong><span>n = {n}</span></div>
      </div>"""
        return f"""
      <div class="funnel-row">
        <div class="funnel-bar" style="width:{pct:.1f}%;background:{color};color:{tc}">
          <strong>{title}</strong>
          <span>n = {n}</span>
        </div>
      </div>"""

    return f"""
  <section class="card" id="fig4">
    <h2>Benchmark corpus funnel</h2>
    <p class="note">Listed URLs → fetched HTML → scoreable pages used in means (cohort chosen from input HTML only)</p>
    <div class="funnel">
      {row("Listed URLs in public corpus", listed, listed, "#D9E2EC", light_text=False)}
      {row("Fetched HTML successfully", fetched, listed, "#1B9AAA")}
      {row("Scoreable (≥ 50 main-content anchors in input DOM) — used in means", scoreable, listed, "#0B6E4F")}
      {row("Thin / JS-shell pages excluded from means", thin, listed, "#9B2226")}
    </div>
    <p class="foot">All-page means (no filter) are reported alongside in the repository.</p>
  </section>"""


def _architecture_card() -> str:
    stages = [
        ("HTML in", "string or file; fetching/rendering stays with the caller", "#D9E2EC", False),
        ("1 · Input-quality gate", "flags thin HTML / JS shells → WARNING + result.warnings", "#5C6770", True),
        ("2 · Schema harvest", "JSON-LD + Microdata → YAML front-matter (before script strip)", "#3D5A80", True),
        ("3 · Clean + STCE", "strip scripts/styles; apply learned site-chrome model if given", "#1B9AAA", True),
        ("4 · Structural + density prune", "nav/footer/cookie heuristics, link/text density, DVDF", "#0B6E4F", True),
        ("5 · Tables + Markdown", "key-value table linearization, heading-safe Markdown", "#0B6E4F", True),
        ("Markdown out", "RAG-ready text + front-matter + diagnostics", "#D9E2EC", False),
    ]
    rows = "".join(
        f"""
      <div class="stage" style="background:{c};color:{'#fff' if light else '#1a1a1a'}">
        <strong>{t}</strong><span>{d}</span>
      </div>{'<div class="arrow">↓</div>' if i < len(stages) - 1 else ''}"""
        for i, (t, d, c, light) in enumerate(stages)
    )
    learn = """
      <div class="side">
        <strong>chromerag learn</strong>
        <span>≥3 pages of one site → repeated chrome-like blocks → site_chrome.json</span>
        <span class="to">feeds stage 3 →</span>
      </div>"""
    return f"""
  <section class="card" id="fig0">
    <h2>ChromeRAG pipeline</h2>
    <p class="note">Single-page extraction (left); optional learn-then-extract site model (right)</p>
    <div class="arch"><div class="stages">{rows}
    </div>{learn}</div>
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
    n_score = int(report["n_scoreable"])
    note = f"Mean over {n_score} scoreable pages (same tool-independent cohort for every method)"
    noise_max = max(v for _, v in noise) * 1.15

    listed = int(report.get("corpus_urls_listed") or 373)
    fetched = int(report.get("n_fetched") or 277)
    scoreable = int(report["n_scoreable"])
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
  .funnel-row.narrow {{ display: flex; align-items: center; gap: 16px; }}
  .funnel-label {{ display: flex; flex-direction: column; gap: 4px; font-size: 15px; }}
  .funnel-label span {{ font-size: 14px; color: var(--muted); }}
  .foot {{ margin: 12px 0 0; color: var(--muted); font-size: 12px; }}
  .arch {{ display: grid; grid-template-columns: 1fr 260px; gap: 22px; align-items: center; }}
  .stage {{ border-radius: 6px; padding: 10px 16px; display: flex; flex-direction: column; gap: 2px; font-size: 15px; }}
  .stage span {{ font-size: 13px; opacity: 0.95; }}
  .arrow {{ text-align: center; font-size: 16px; color: var(--muted); line-height: 18px; }}
  .side {{ border: 2px dashed #1B9AAA; border-radius: 8px; padding: 14px; display: flex; flex-direction: column; gap: 6px; font-size: 14px; }}
  .side span {{ font-size: 13px; color: var(--muted); }}
  .side .to {{ color: #1B9AAA; font-weight: 600; }}
</style>
</head>
<body>
{_architecture_card()}
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

    out_map = {fig_id: OUT / name for fig_id, name in OUT_NAMES.items()}
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


CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome",
    "chromium",
    "chromium-browser",
]

CARD_HEIGHTS = {"fig0": 640, "fig1": 470, "fig2": 470, "fig3": 470, "fig4": 520}
OUT_NAMES = {
    "fig0": "fig0_architecture.png",
    "fig1": "fig1_fbal.png",
    "fig2": "fig2_recall.png",
    "fig3": "fig3_noise.png",
    "fig4": "fig4_corpus_gate.png",
}


def rasterize_with_npx(html_path: Path) -> bool:
    """Fallback without Playwright: headless Chrome screenshots, one card per page."""
    import re
    import shutil

    chrome = next((c for c in CHROME_CANDIDATES if shutil.which(c) or Path(c).exists()), None)
    if not chrome:
        print("Neither playwright nor a Chrome/Chromium binary is available.", file=sys.stderr)
        return False
    html = html_path.read_text(encoding="utf-8")
    head, body = html.split("<body>", 1)
    cards = {
        fig_id: section
        for section, fig_id in re.findall(
            r'(<section class="card" id="(fig\d)">.*?</section>)', body, re.S
        )
    }
    script = body[body.index("<script>"):]
    for fig_id, name in OUT_NAMES.items():
        single = OUT / f"_{fig_id}.html"
        single.write_text(
            head.replace("padding: 24px;", "padding: 0;") + "<body style='margin:0'>" + cards[fig_id] + script,
            encoding="utf-8",
        )
        dest = OUT / name
        subprocess.run(
            [
                chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                "--force-device-scale-factor=3", f"--window-size=1180,{CARD_HEIGHTS[fig_id]}",
                f"--screenshot={dest}", single.resolve().as_uri(),
            ],
            check=True, capture_output=True, timeout=120,
        )
        single.unlink()
        print(f"Wrote {dest} ({dest.stat().st_size} bytes)")
    return True


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
    print("Done. Figures written to", OUT)


if __name__ == "__main__":
    main()
