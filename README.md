# ChromeRAG

[![PyPI](https://img.shields.io/pypi/v/chromerag.svg)](https://pypi.org/project/chromerag/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![GitHub Pages](https://img.shields.io/badge/docs-GitHub%20Pages-222.svg)](https://pedapudibhargav.github.io/ChromeRAG/)

**HTML → RAG-ready Markdown** that strips site-template chrome (nav, footer, CTAs, cookie banners) while keeping documentation, pricing tables, and article body text.

> Built for **enterprise RAG ingest**, **LLM chunking**, **vector indexing**, and **boilerplate / noise removal** from scraped HTML — not for pixel-perfect web archiving.

| Owns | Does **not** own |
|---|---|
| HTML string / file → clean Markdown | Crawling, Playwright, rate limits |
| Optional site-chrome **learn → extract** (STCE) | Rendering JavaScript shells (it warns; render first) |
| Schema.org → YAML front-matter | Vector DB / embeddings |
| Table → key-value row linearization | Hosted SaaS API |
| Precision / coverage priority knobs | PDF / Office formats |

**Paper:** *ChromeRAG: Ingest-Time Elimination of Site Template Noise for Enterprise Web RAG* (submitted to SoftwareX)  
**Release:** [`v0.1.1`](https://github.com/pedapudibhargav/ChromeRAG/tree/v0.1.1)  
**Author:** [Bhargava Chary Peddapudi](https://orcid.org/0009-0002-8523-8415)

---

## Install

Requires **Python 3.11+**. CPU only; no model downloads.

```bash
pip install chromerag
chromerag --version
```

From source (adds tests and the benchmark baselines):

```bash
git clone https://github.com/pedapudibhargav/ChromeRAG.git
cd ChromeRAG
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev,baselines]"
pytest -q
```

---

## Quick start

The repository ships a tiny synthetic site in [`examples/site/`](examples/) (four pages that share a
header, cookie banner, sales CTA, footer, and a repeated in-content promo strip). Run these from the
repository root:

```bash
# 1) One page → Markdown (JSON-LD becomes YAML front-matter, tables become key-value rows)
chromerag extract examples/site/pricing.html -o out/pricing.md --priority balanced --json-meta

# 2) Learn the site's repeated chrome from ≥3 pages, then batch-extract with it
chromerag learn examples/site -o out/site_chrome.json --min-pages 3
chromerag batch examples/site -o out/batch --chrome-model out/site_chrome.json
```

`learn` reports one site group (`docs.example.com/docs`) with its chrome signatures; `batch`
writes `out/batch/<page>/chromerag.md` plus `out/batch/batch_summary.json`. The repeated
"Widget Summit" strip survives single-page extraction but is removed once the site model is applied.

Priorities: `precision` (strip more) · `balanced` (default) · `coverage` (keep more).

### Thin / JavaScript-shell input

ChromeRAG does not execute JavaScript. Unrendered SPA shells produce a warning on stderr (and in
`result.warnings`); render them with Playwright/Puppeteer first.

```bash
echo '<html><body><div id="root"></div><script src="app.js"></script></body></html>' > spa.html
chromerag extract spa.html -o out/spa.md                  # prints WARNING, exits 0
chromerag extract spa.html -o out/spa.md --fail-on-thin   # prints WARNING, exits 3
```

### Python

```python
from chromerag import ChromeRAG, PipelineConfig, ContentPriority

html = open("examples/site/pricing.html", encoding="utf-8").read()
result = ChromeRAG(
    config=PipelineConfig.from_priority(ContentPriority.BALANCED)
).extract(html, url="https://docs.example.com/docs/pricing")

print(result.markdown)       # RAG-ready Markdown (+ YAML front-matter when Schema.org present)
print(result.front_matter)   # dict
print(result.tokens_estimate)
print(result.warnings)       # e.g. JS shell → render with Playwright first
```

Learn-then-extract from Python: `chromerag.learn_then_extract(pages)` or
`load_chrome_models(path)` + `ChromeRAG(site_chrome=model)`.

---

## Why ChromeRAG (vs MarkItDown / Trafilatura)?

| Tool | Best at | Gap for corporate web RAG |
|------|---------|---------------------------|
| **MarkItDown** | Office/PDF/HTML → Markdown for LLMs | Keeps most page chrome; not designed to strip nav/footer |
| **Trafilatura** | News/article main content | Occasionally drops most of a multi-section docs page |
| **Readability** | Single-article extraction | Often drops tables / reference sections |
| **ChromeRAG** | Ingest-time chrome removal + schema + tables + input warnings | HTML only; fetching/rendering stays in your crawler |

---

## Benchmarks (public corpus)

**Metrics** (deterministic, computed from each input DOM, independent of any extractor):

| Metric | Meaning | Better |
|--------|---------|--------|
| **Recall** (`content_recall`) | Share of `<main>`/`<article>` 5-gram anchors kept | Higher |
| **Noise ret** (`noise_retention`) | Share of nav/header/footer/aside/cookie anchors kept | Lower |
| **Fbal** (`f_balanced`) | Harmonic mean of recall and (1 − noise) | Higher |

**Corpus:** 373 URLs in `poc/corpus_urls.json` → **277** fetched (plain HTTP, no JS rendering) →
**250 scoreable**. A page is scoreable when its **input HTML** has ≥ 50 main-content anchors; the
rule never looks at any tool's output, so every method is averaged over the same pages. The 27
excluded pages are 7 JS shells, 1 other thin page, and 19 pages with too little landmarked text.
No site model (STCE) is used in the benchmark.

| Method | Recall ↑ | Noise ↓ | Fbal ↑ (250 scoreable) | Fbal ↑ (all 277) |
|--------|--------:|--------:|-------:|-------:|
| chromerag_coverage | 0.691 | 0.007 | **0.791** | **0.752** |
| chromerag (balanced) | 0.667 | 0.006 | 0.774 | 0.736 |
| trafilatura | 0.640 | 0.012 | 0.740 | 0.698 |
| markitdown | 0.692 | 0.253 | 0.694 | 0.661 |
| readability | 0.450 | 0.013 | 0.531 | 0.499 |

Paired bootstrap (95% CI): coverage − Trafilatura Fbal **+0.051 [+0.025, +0.081]** (driven by
recall; noise difference not significant); coverage − MarkItDown noise **−0.246 [−0.269, −0.222]**
at equal recall. Full tables, per-category breakdown and per-page scores:
[Results](https://pedapudibhargav.github.io/ChromeRAG/results.html) ·
[`docs/data/corpus_comparison_summary.md`](docs/data/corpus_comparison_summary.md).

---

## Reproduce the evaluation

```bash
pip install -e ".[dev,baselines]"

# 0) Offline: recompute the published cohort and every leaderboard mean
#    from the per-page scores in docs/data/ (no network needed)
python scripts/revalidate_corpus.py

# 1) Fetch the public corpus into data/raw/ and score every tool (network required)
python -m poc.run_corpus_comparison
#    …later re-scores of the already-fetched HTML can skip the network:
python -m poc.run_corpus_comparison --no-fetch

# 2) Recheck the fresh run and classify thin pages (JS shell vs other)
python scripts/revalidate_corpus.py

# 3) Copy results into docs/ for GitHub Pages, run tests, rebuild docs/tests.html
./scripts/build_docs.sh
```

Live pages change over time, so a fresh fetch will not reproduce the published numbers exactly;
the published per-page scores are in `docs/data/corpus_comparison_report.json`.

---

## Project layout

```
src/chromerag/     # library (HTML in → Markdown out)
examples/          # small synthetic site for the quick start
tests/             # unit + CLI tests
poc/               # fetch, baselines, corpus comparison (not needed at runtime)
docs/              # GitHub Pages site + published metrics
scripts/           # revalidation, docs build, paper figures
papers/softwarex/  # SoftwareX manuscript sources
```

---

## Citation

If you use ChromeRAG, please cite the software (see [`CITATION.cff`](CITATION.cff)):

> B. C. Peddapudi, *ChromeRAG*, version 0.1.1, 2026. https://github.com/pedapudibhargav/ChromeRAG

## License

MIT — see [LICENSE.txt](LICENSE.txt).
