# ChromeRAG

[![PyPI](https://img.shields.io/pypi/v/chromerag.svg)](https://pypi.org/project/chromerag/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://github.com/pedapudibhargav/ChromeRAG/actions/workflows/pages.yml/badge.svg)](https://github.com/pedapudibhargav/ChromeRAG/actions/workflows/pages.yml)
[![Results](https://img.shields.io/badge/results-GitHub%20Pages-2a78d6.svg)](https://pedapudibhargav.github.io/ChromeRAG/)

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
**Release:** [`v0.1.2`](https://github.com/pedapudibhargav/ChromeRAG/tree/v0.1.2)  
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

## Results

All numbers below are recomputed from the files in [`docs/data/`](docs/data/) and shown, with a
per-page explorer, at **https://pedapudibhargav.github.io/ChromeRAG/**.

### Extraction benchmark

**Metrics** (deterministic, computed from each input DOM, independent of any extractor):

| Metric | Meaning | Better |
|--------|---------|--------|
| **Recall** (`content_recall`) | Share of `<main>`/`<article>` 5-gram anchors kept | Higher |
| **Noise ret** (`noise_retention`) | Share of nav/header/footer/aside/cookie anchors kept | Lower |
| **Fbal** (`f_balanced`) | Harmonic mean of recall and (1 − noise) | Higher |

**Corpus:** 367 unique URLs in `poc/corpus_urls.json` → **268** unique pages fetched (plain HTTP, no
JS rendering; a URL reached under two ids is scored once) → **242 scoreable**. A page is scoreable
when its **input HTML** has ≥ 50 main-content anchors; the rule never looks at any tool's output,
so every method is averaged over the same pages. The 26 excluded pages are 7 JS shells, 1 other
thin page, and 18 pages with too little landmarked text. 208 of the 242 pages are documentation.

| Method | Recall ↑ | Noise ↓ | Fbal ↑ (242 scoreable) | Fbal ↑ (all 268) |
|--------|--------:|--------:|-------:|-------:|
| chromerag_coverage | 0.688 | 0.007 | **0.788** | **0.747** |
| chromerag (balanced) | 0.665 | 0.006 | 0.771 | 0.731 |
| trafilatura | 0.640 | 0.012 | 0.739 | 0.696 |
| markitdown | 0.691 | 0.250 | 0.696 | 0.661 |
| readability | 0.449 | 0.013 | 0.531 | 0.495 |

Paired bootstrap (95% CI): coverage − Trafilatura Fbal **+0.049 [+0.021, +0.079]** (driven by
recall; noise difference not significant); coverage − MarkItDown noise **−0.243 [−0.266, −0.220]**
at equal recall. Trafilatura keeps less than 20% of the content on 25 pages, ChromeRAG on 13.

### Retrieval

Each tool's output is split into ~200-word chunks and indexed with BM25. 771 known-item queries
(page titles, section headings and content passages from the input HTML, each with exactly one
correct page) are run against each index.

| Method | Hit@5 ↑ | Chrome in top-5 context ↓ | Chunks indexed |
|--------|--------:|--------:|--------:|
| chromerag_coverage | 0.949 | 0.1% | 2,553 |
| trafilatura | 0.922 | 0.5% | 1,949 |
| markitdown | 0.964 | 2.6% | 3,907 |
| readability | 0.774 | 0.6% | 1,701 |

ChromeRAG vs MarkItDown hit@5 is not significantly different (−0.014, 95% CI [−0.035, +0.006])
with 35% fewer chunks; vs Trafilatura it is higher (+0.027 [+0.003, +0.053]).

### Site-template learning (STCE)

`chromerag learn` is evaluated by `poc/run_stce_eval.py` (coverage mode, with vs without the site
model) on the benchmark's site groups with ≥ 3 unique pages and on a crawl of up to 15 same-section
pages per documentation site (`poc/stce_crawl_urls.json`, fetched with `poc/crawl_site_groups.py`).

| Page set | Sites | Scored pages | Recall without → with | Pages changed | Site-repeated text* |
|----------|------:|------:|------:|------:|------:|
| Benchmark sites | 11 | 47 | 0.714 → 0.714 | 6 of 49 | 1.4% → 1.4% |
| Documentation crawl | 125 | 1,727 | 0.770 → 0.769 | 174 of 1,791 | 3.1% → 3.0% |

\* Share of a page's Markdown body (front-matter excluded) made of 5-grams that recur on ≥ 80% of
the same site's outputs. On the crawl, Trafilatura leaves 2.1% and MarkItDown 34.9%.

Single-page extraction already removes most repeated chrome, so STCE is a guarded complement for
template blocks without chrome markup (like the "Widget Summit" strip in the quick start). The 17
crawl pages that lose more than 0.05 recall come from three sites that put feedback widgets or
promotions inside `<main>`, which the anchor metric counts as content.

---

## Reproduce the evaluation

```bash
pip install -e ".[dev,baselines]"

# Offline: recompute the published cohort and every leaderboard mean from docs/data/
python scripts/revalidate_corpus.py

# Extraction benchmark: fetch the public corpus into data/raw/ and score every tool (network)
python -m poc.run_corpus_comparison            # add --no-fetch to re-score stored HTML

# Retrieval over each tool's chunks (uses the outputs written above)
python -m poc.run_retrieval_eval

# Site-template learning: benchmark sites, then a multi-page crawl (network)
python -m poc.run_stce_eval
python -m poc.crawl_site_groups --fetch        # pages listed in poc/stce_crawl_urls.json
python -m poc.run_stce_eval --raw data/stce_crawl

# Publish: copy results into docs/data, run tests, assemble _site/ (CI does this on main)
bash scripts/build_docs.sh
```

Live pages change over time, so a fresh fetch will not reproduce the published numbers exactly;
the published per-page scores are in `docs/data/corpus_comparison_report.json`. Behind a TLS-
intercepting proxy, point `SSL_EXTRA_CA` at the proxy's CA bundle before fetching.

---

## Project layout

```
src/chromerag/     # library (HTML in → Markdown out)
examples/          # small synthetic site for the quick start
tests/             # unit + CLI tests
poc/               # fetch, baselines, benchmark, retrieval and STCE evaluations (not needed at runtime)
docs/              # one-page GitHub Pages site (index.html) + published results (data/)
scripts/           # revalidation, docs build, paper figures
papers/softwarex/  # SoftwareX manuscript sources
```

---

## Citation

If you use ChromeRAG, please cite the software (see [`CITATION.cff`](CITATION.cff)):

> B. C. Peddapudi, *ChromeRAG*, version 0.1.2, 2026. https://github.com/pedapudibhargav/ChromeRAG

## License

MIT — see [LICENSE.txt](LICENSE.txt).
