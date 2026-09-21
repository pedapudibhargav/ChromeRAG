# ChromeRAG

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![GitHub Pages](https://img.shields.io/badge/docs-GitHub%20Pages-222.svg)](https://pedapudibhargav.github.io/ChromeRAG/)

**HTML → RAG-ready Markdown** that strips site-template chrome (nav, footer, CTAs, cookie banners) while keeping documentation, pricing tables, and article body text.

> Built for **enterprise RAG ingest**, **LLM chunking**, **vector indexing**, and **boilerplate / noise removal** from scraped HTML — not for pixel-perfect web archiving.

| Owns | Does **not** own |
|---|---|
| HTML string / file → clean Markdown | Crawling, Playwright, rate limits |
| Optional site-chrome **learn → extract** (STCE) | Full browser rendering of empty JS shells (warns; caller must render first) |
| Schema.org → YAML front-matter | Vector DB / embeddings |
| Precision / coverage priority knobs | Hosted SaaS API |

**Paper:** *ChromeRAG: Ingest-Time Elimination of Site Template Noise for Enterprise Web RAG*
**Release:** [`v0.1.0`](https://github.com/pedapudibhargav/ChromeRAG/tree/v0.1.0)  
**Author:** [Bhargava Chary Peddapudi](https://orcid.org/0009-0002-8523-8415)

---

## Why ChromeRAG (vs MarkItDown / Trafilatura)?

| Tool | Best at | Gap for corporate web RAG |
|------|---------|---------------------------|
| **MarkItDown** | Office/PDF/HTML → Markdown for LLMs | Keeps a lot of page chrome; not tuned to strip SaaS nav/footer |
| **Trafilatura** | News/article main-content | Weaker on docs hubs, pricing matrices, marketing shells |
| **Readability** | Article extraction | Often drops tables / side content needed for RAG |
| **ChromeRAG** | Ingest-time chrome elimination + schema + tables | Focused HTML→RAG Markdown (fetch stays in your crawler) |

---

## Benchmarks (public corpus)

**Deterministic metrics** (primary claims) — independent of any single extractor:

| Metric | Meaning | Better |
|--------|---------|--------|
| **Recall** (`content_recall`) | Fraction of main/article text anchors kept | Higher |
| **Noise ret** (`noise_retention`) | Fraction of nav/footer chrome anchors kept | Lower |
| **Fbal** (`f_balanced`) | Balance of high recall + low noise | Higher |

**Baselines compared:** ChromeRAG (balanced / coverage / precision), Trafilatura, Readability, **MarkItDown**, markdownify, html2text, BeautifulSoup text.

**Corpus:** **373** URLs listed in `poc/corpus_urls.json` across `docs`, `pricing`, `marketing`, `wiki`, `hub`, `news`, `article`, `cloud`. Latest run fetched **277** HTML pages; **238** were scoreable (ChromeRAG recall ≥ 0.05); **39** thin pages are excluded from leaderboard *means* so empty JS shells are not silently averaged into SOTA claims. All baselines are scored on the same scoreable set.

**Latest leaderboard (238 scoreable pages):**

| Method | Recall ↑ | Noise ↓ | Fbal ↑ |
|--------|--------:|--------:|-------:|
| chromerag_coverage | 0.701 | 0.005 | **0.800** |
| chromerag (balanced) | 0.678 | 0.005 | 0.783 |
| trafilatura | 0.662 | 0.019 | 0.752 |
| markitdown | 0.702 | 0.261 | 0.695 |
| readability | 0.456 | 0.016 | 0.535 |

Full tables + per-category breakdown: [Results](https://pedapudibhargav.github.io/ChromeRAG/results.html) · `docs/data/corpus_comparison_summary.md`.

**Optional LLM judge** (secondary): stratified sample scored 1–5 on content keep / noise strip / structure when `OPENAI_API_KEY` is set (`python -m poc.run_llm_eval`). Does not replace Recall/Noise/Fbal.

---

## Quick start (from source — recommended)

No PyPI publish required. Install from this repo:

```bash
git clone https://github.com/pedapudibhargav/ChromeRAG.git
cd ChromeRAG
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Core library + CLI
pip install -e .

# Optional: comparison baselines + tests
pip install -e ".[dev,baselines]"
```

### CLI

```bash
# Single page
chromerag extract path/to/page.html -o out.md --priority balanced --json-meta

# Priorities: precision | balanced | coverage
chromerag extract page.html -o clean.md --priority coverage

# Thin / JS-shell HTML prints WARNING on stderr (caller must Playwright-render first)
# chromerag extract spa.html -o out.md --fail-on-thin   # exit 3 if thin

# Learn site chrome across a folder, then batch-extract
chromerag learn data/raw -o data/chrome_models/site.json --min-pages 3
chromerag batch data/raw -o data/outputs --chrome-model data/chrome_models/site.json
```

### Python

```python
from chromerag import ChromeRAG, PipelineConfig, ContentPriority

html = open("page.html", encoding="utf-8").read()
result = ChromeRAG(
    config=PipelineConfig.from_priority(ContentPriority.BALANCED, enable_dvdf=False)
).extract(html, url="https://example.com/docs")

print(result.markdown)       # RAG-ready Markdown (+ YAML front-matter when Schema.org present)
print(result.front_matter)   # dict
print(result.tokens_estimate)
print(result.warnings)       # e.g. JS shell → render with Playwright first
```

---

## Reproduce the evaluation

```bash
# 1) Fetch / refresh the public corpus (uses poc/corpus_urls.json)
python -m poc.run_corpus_comparison

# 2) Export tables + JSON into docs/ for GitHub Pages
python -m poc.export_site_results

# 3) Revalidate published numbers + classify thin pages
python scripts/revalidate_corpus.py

# 4) Optional LLM subset judge (needs OPENAI_API_KEY)
python -m poc.run_llm_eval --sample 40

# 5) Unit tests + regenerate docs/tests.html
./scripts/build_docs.sh
```

Skip re-fetch if HTML is already under `data/raw/`:

```bash
python -m poc.run_corpus_comparison --no-fetch
```

---

## Docs site (GitHub Pages)

Static files live in [`docs/`](docs/) (relative links only).

CI (`.github/workflows/pages.yml`) on every push to **`main`**:

1. runs `pytest`
2. rebuilds `docs/tests.html` + exports corpus results
3. deploys `docs/` → **`gh-pages`** branch

Enable once: **Settings → Pages → Deploy from a branch → `gh-pages` / (root)**.  
Site: https://pedapudibhargav.github.io/ChromeRAG/

---

## Project layout

```
src/chromerag/     # library (HTML in → Markdown out)
poc/               # fetch, baselines, corpus comparison, LLM eval (not required at runtime)
docs/              # GitHub Pages site + published metrics
tests/             # unit tests
papers/softwarex/  # SoftwareX manuscript draft
```

---


## Publishing (SoftwareX)

- Manuscript draft (Markdown): [`papers/softwarex/SOFTWAREX_DRAFT.md`](papers/softwarex/SOFTWAREX_DRAFT.md)
- Filled official OSP Word manuscript: [`papers/softwarex/ChromeRAG_SoftwareX_OSP.docx`](papers/softwarex/ChromeRAG_SoftwareX_OSP.docx)
- Figures: [`papers/softwarex/figures/`](papers/softwarex/figures/)
- Limitations (JS shells / scoreable filter): [docs/limitations.html](docs/limitations.html)
- Draft self-check: `python scripts/check_softwarex_draft.py`
- Highlights / APC / refs explained: [`papers/softwarex/WHAT_THESE_MEAN.md`](papers/softwarex/WHAT_THESE_MEAN.md)
- Optional screencast shot list: [`papers/softwarex/SCREENCAST.md`](papers/softwarex/SCREENCAST.md)

SoftwareX APC (journal OA fee) is paid **only after acceptance**, not at submission.


## License

MIT — see [LICENSE](LICENSE) / [LICENSE.txt](LICENSE.txt) (SoftwareX naming) · also `Licence.txt`.
