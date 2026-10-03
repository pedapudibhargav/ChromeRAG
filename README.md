# ChromeRAG

[![PyPI](https://img.shields.io/pypi/v/chromerag.svg)](https://pypi.org/project/chromerag/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://github.com/pedapudibhargav/ChromeRAG/actions/workflows/pages.yml/badge.svg)](https://github.com/pedapudibhargav/ChromeRAG/actions/workflows/pages.yml)
[![Results](https://img.shields.io/badge/results-GitHub%20Pages-2a78d6.svg)](https://pedapudibhargav.github.io/ChromeRAG/)
[![DOI](https://zenodo.org/badge/1378773845.svg)](https://doi.org/10.5281/zenodo.22970289)

**HTML → RAG-ready Markdown.** A small learned filter (plus optional site-template learning) removes navigation, footers, CTAs, cookie banners, related links and comment threads, and keeps article text, documentation and pricing tables. Pure NumPy inference: no GPU, no model download, about 36 ms per page. A drop-in alternative to Trafilatura, Readability and MarkItDown when the pages are documentation, marketing or product pages as well as articles.

> Built for **enterprise RAG ingest**, **LLM chunking**, **vector indexing**, and **boilerplate / noise removal** from scraped HTML — not for pixel-perfect web archiving.

| Owns | Does **not** own |
|---|---|
| HTML string / file → clean Markdown | Crawling, Playwright, rate limits |
| Optional site-chrome **learn → extract** (STCE) | Rendering JavaScript shells (it warns; render first) |
| Schema.org → YAML front-matter | Vector DB / embeddings |
| Table → key-value row linearization | Hosted SaaS API |
| Precision / coverage priority knobs | PDF / Office formats |

**Paper:** *ChromeRAG: Ingest-Time Elimination of Site Template Noise for Enterprise Web RAG* (submitted to SoftwareX)  
**Release:** [`v0.1.3`](https://github.com/pedapudibhargav/ChromeRAG/tree/v0.1.3)  
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
"Widget Summit" paragraph survives single-page extraction but is removed once the site model is applied.

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

### Use it in a RAG pipeline

```python
# LangChain:  pip install "chromerag[langchain]"
from chromerag.integrations.langchain import ChromeRAGLoader
docs = ChromeRAGLoader(["pages/pricing.html"], urls={"pages/pricing.html": "https://example.com/pricing"}).load()

# LlamaIndex: pip install "chromerag[llamaindex]"
from chromerag.integrations.llamaindex import ChromeRAGReader
docs = ChromeRAGReader().load_data(["pages/pricing.html"])
```

Front-matter (title, type, dates, breadcrumb) becomes document metadata, so a text splitter copies it
onto every chunk.

### Chunks for vector databases

ChromeRAG can split extracted Markdown into heading-aware chunks sized for embedding. Prepend the
heading path to the embedded text (page title → h2 → h3) for better retrieval: on a held-out test of
400 questions over 3,395 documentation chunks from sites not used in training, dense MRR rose from
0.853 to 0.913 and BM25 MRR by +0.060 (95% CI excludes 0). Questions were written by Claude from
each chunk and its page title.

```python
result = ChromeRAG().extract(html, url="https://docs.example.com/guide")
for chunk in result.chunks():
    vector_db.upsert(text=chunk.embed_text, metadata=chunk.to_dict())
# chunk.embed_text == "Page Title > Section > Subsection\n<body markdown>"
```

CLI: `chromerag extract page.html --chunks` writes one JSON object per line (JSONL).

### Frequently asked

**Does it need a model download or a GPU?** No. The model is a 150 KB array file inside the wheel.
**Does it run JavaScript?** No; it warns on unrendered shells. Render with Playwright first.
**When should I pick Trafilatura instead?** For pure news/blog articles it is as good (the two tie in
our benchmark). ChromeRAG is better on documentation sites, marketing and product pages, forums and
listings, and when you can show it several pages of one site.
**How do I keep link URLs?** `PipelineConfig(include_links=True)` or `--links`.
**Can I trust the numbers?** Every table is recomputed from files in the repository; learned-model numbers
come from cross-validation grouped by site (see below and `evaluations/`).

---

## Why ChromeRAG (vs MarkItDown / Trafilatura)?

| Tool | Best at | Gap for corporate web RAG |
|------|---------|---------------------------|
| **MarkItDown** | Office/PDF/HTML → Markdown for LLMs | Keeps most page chrome; not designed to strip nav/footer |
| **Trafilatura** | News/article main content | Occasionally drops most of a multi-section docs page |
| **Readability** | Single-article extraction | Often drops tables / reference sections |
| **ChromeRAG** | Ingest-time chrome removal + schema + tables + input warnings | HTML only; fetching/rendering stays in your crawler |

---

## Learned block filter (new in 0.1.3)

Version 0.1.3 replaces the hand-set density thresholds with a small learned model. The page is
cleaned as before (tags, hidden nodes, rules, site chrome, obvious navigation), then split into
*blocks* (paragraphs, headings, list items, quotes, tables, text-only divs). Each block is
described by about 500 numbers (its text, its place in the tree, the names of its ancestors, the
heading above it, its neighbours) and scored by gradient-boosted trees. A block is kept when its
score reaches the threshold of the chosen priority: `coverage` 0.30, `balanced` 0.50,
`precision` 0.70.

* The model is a 150 KB array file (`src/chromerag/assets/lbc_stage1.npz`) evaluated with NumPy
  only; scikit-learn is needed to retrain, not to run.
* It was trained on human-reviewed pages (WCXB development split, 1,495 pages). Cross-validated development F1
  (5 folds grouped by site) is 0.852 / 0.851 / 0.837 against Trafilatura 0.818. On the WCXB test split, after removing
  the 138 pages that duplicate development pages (373 pages left), word-level F1 is **0.903** (`balanced`) against
  Trafilatura 0.867, Readability 0.778 and MarkItDown 0.567: +0.036 [+0.018, +0.054], a clear gain on forum pages
  (+0.153) and ties on articles, documentation, services and listings (all 511 pages: 0.902 vs 0.860).
  A language-model judge preferred ChromeRAG to MarkItDown on 79-87% of pages and to Trafilatura on 70% of landing
  pages, but tied with Trafilatura on a mixed WCXB sample. Everything is in `evaluations/2026-10-v0.1.3/`.
* Link targets are no longer written by default (`PipelineConfig(include_links=True)` or
  `--links` brings back `[text](url)`), repeated blocks are written once, and the Markdown now
  follows document order.
* Switch it off with `PipelineConfig(enable_lbc=False)` to get the 0.1.2 density filter.

Retrain (needs `pip install -e ".[train]"` and WCXB in `data/wcxb/`):

```bash
python -m poc.lbc_data --split dev                      # block table -> data/outputs/lbc/lbc_dev.npz
python -m poc.train_lbc --fit-all --out-dir src/chromerag/assets
python -m poc.run_wcxb_eval --split dev --out /tmp/wcxb_dev.json   # sanity check (in-sample after --fit-all)
```

**WCXB data.** Get WCXB v1.0 (CC-BY-4.0, https://arxiv.org/abs/2605.21097) into `data/wcxb/{dev,test}/{ground-truth/*.json,html/*.html.gz}`.
`python -m poc.run_wcxb_eval --split dev|test [--final] --out FILE` scores the tools (the test split needs `--final`; always pass
`--out`, the default overwrites a tracked file). The public `dev/` folder contains 139 files that WCXB's metadata assigns to
the test split (`poc/wcxb_leaked_ids.json`); `load_split("test", drop_leaked=True)` drops them, and the paper reports test
results without them. Scores are computed on the Markdown body with ChromeRAG's YAML front-matter removed; the benchmark's
own script on raw default output gives 0.869 (372 clean test pages), and 0.904 with `enable_schema=False`.


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
| chromerag_coverage | 0.739 | 0.010 | **0.833** | **0.790** |
| chromerag (balanced) | 0.688 | 0.004 | 0.798 | 0.755 |
| trafilatura | 0.640 | 0.012 | 0.739 | 0.696 |
| markitdown | 0.691 | 0.250 | 0.696 | 0.661 |
| readability | 0.449 | 0.013 | 0.531 | 0.496 |

This corpus was a **development** set for 0.1.3 (the learned filter was tuned and checked against it; it was
re-fetched on 2026-10-02) and is not held out. Paired bootstrap (95% CI): coverage − Trafilatura Fbal
**+0.094 [+0.066, +0.122]**; coverage − MarkItDown recall +0.048 [+0.027, +0.070] and noise **−0.240
[−0.266, −0.216]**. Trafilatura keeps less than 20% of the content on 25 pages, ChromeRAG on 2. The anchors
come from `<main>`/`<article>`, which ChromeRAG's content-root selection also prefers, so treat this as a
proxy; the human-reviewed WCXB benchmark below is the primary evidence.

### Retrieval

Each tool's output is split into ~200-word chunks and indexed with BM25. 773 known-item queries
(page titles, section headings and content passages from the input HTML, each with exactly one
correct page) are run against each index.

| Method | Hit@5 ↑ | Chrome in top-5 context ↓ | Chunks indexed |
|--------|--------:|--------:|--------:|
| chromerag_coverage | 0.947 | 0.5% | 2,010 |
| chromerag (balanced) | 0.935 | 0.1% | 1,712 |
| trafilatura | 0.921 | 0.6% | 1,950 |
| markitdown | 0.964 | 2.6% | 3,909 |
| readability | 0.775 | 0.6% | 1,702 |

ChromeRAG (coverage) vs MarkItDown hit@5 is not significantly different (−0.017, 95% CI [−0.037, +0.003])
with 49% fewer chunks; vs Trafilatura +0.026 [+0.001, +0.051] (marginal). On 178 fresh-company pages
(`evaluations/2026-10-v0.1.3/FINAL/`) hit@5 is 0.916 vs 0.832 for Trafilatura, with 0.1% vs 1.1% chrome in the context.

### Site-template learning (STCE)

`chromerag learn` is evaluated by `poc/run_stce_eval.py` (coverage mode, with vs without the site
model) on the benchmark's site groups with ≥ 3 unique pages and on a crawl of up to 15 same-section
pages per documentation site (`poc/stce_crawl_urls.json`, fetched with `poc/crawl_site_groups.py`).

| Page set | Sites | Scored pages | Recall without → with | Pages changed | Site-repeated text* |
|----------|------:|------:|------:|------:|------:|
| Benchmark sites | 11 | 47 | 0.776 → 0.778 | 8 of 49 | 0.5% → 0.5% |
| Documentation crawl | 125 | 1,727 | 0.805 → 0.805 | 314 of 1,791 | 2.1% → 2.1% |

\* Share of a page's Markdown body (front-matter excluded) made of 5-grams that recur on ≥ 80% of
the same site's outputs. On the crawl, Trafilatura leaves 2.1% and MarkItDown 34.9%.

Single-page extraction already removes most repeated chrome, so STCE is a guarded complement for
template blocks that the learned filter keeps because they read like content (like the "Widget Summit"
paragraph in the quick start). On the crawl, 13 pages from 7 sites lose more than 0.05 recall; we have not
inspected them individually.

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

> B. C. Peddapudi, *ChromeRAG*, version 0.1.3, Zenodo, 2026. https://doi.org/10.5281/zenodo.23107381

To cite whichever version is latest, use the all-versions DOI [10.5281/zenodo.22970289](https://doi.org/10.5281/zenodo.22970289).

## License

MIT — see [LICENSE.txt](LICENSE.txt).
