# ChromeRAG

[![PyPI](https://img.shields.io/pypi/v/chromerag.svg)](https://pypi.org/project/chromerag/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://github.com/pedapudibhargav/ChromeRAG/actions/workflows/pages.yml/badge.svg)](https://github.com/pedapudibhargav/ChromeRAG/actions/workflows/pages.yml)
[![Results](https://img.shields.io/badge/results-GitHub%20Pages-2a78d6.svg)](https://pedapudibhargav.github.io/ChromeRAG/)
[![DOI](https://zenodo.org/badge/1378773845.svg)](https://doi.org/10.5281/zenodo.22970289)

**HTML → RAG-ready Markdown and chunks.** A small learned filter, evidence-backed rules and an optional
site-template model remove navigation, footers, calls to action, cookie banners, related links and comment
threads, and keep article text, documentation, tables and code. Pure NumPy inference: no GPU, no model
download. Chunks carry their heading path, ready for a vector database. A drop-in alternative to Trafilatura,
Readability and MarkItDown when the pages are documentation, forums, marketing or product pages as well as
articles.

> Built for **RAG ingest**, **LLM chunking**, **vector indexing** and **boilerplate / noise removal** from scraped
> HTML, not for pixel-perfect web archiving.

| Owns | Does **not** own |
|---|---|
| HTML string / file → clean Markdown | Crawling, Playwright, rate limits |
| Heading-aware chunks with `embed_text` | Vector DB / embeddings |
| Optional site-chrome **learn → extract** (STCE) | Rendering JavaScript shells (it warns; render first) |
| Schema.org → YAML front-matter | Hosted SaaS API |
| Tables, code and lists kept as Markdown | PDF / Office formats |
| Precision / coverage priority knobs | |

**Paper:** *ChromeRAG: A Learned Boilerplate Filter for Web RAG Ingestion* (submitted to SoftwareX)  
**Release:** [`v0.1.4`](https://github.com/pedapudibhargav/ChromeRAG/tree/v0.1.4)  
**Author:** [Bhargava Chary Peddapudi](https://orcid.org/0009-0002-8523-8415)

---

## Install

Requires **Python 3.11+**. CPU only; no model downloads. Four direct dependencies (BeautifulSoup, lxml, PyYAML, NumPy).

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

```python
from chromerag import ChromeRAG

result = ChromeRAG().extract(open("page.html", encoding="utf-8").read(), url="https://example.com/page")
print(result.markdown)              # RAG-ready Markdown (+ YAML front-matter when Schema.org is present)
for chunk in result.chunks():       # heading-aware chunks for a vector database
    vector_db.upsert(text=chunk.embed_text, metadata=chunk.to_dict())
```

The repository ships a tiny synthetic site in [`examples/site/`](examples/) (four pages that share a
header, cookie banner, sales CTA, footer, and a repeated in-content promo strip). Run these from the
repository root:

```bash
# 1) One page → Markdown (JSON-LD becomes YAML front-matter, tables become Markdown tables)
chromerag extract examples/site/pricing.html -o out/pricing.md --priority balanced --json-meta

# 2) Learn the site's repeated chrome from ≥3 pages, then batch-extract with it
chromerag learn examples/site -o out/site_chrome.json --min-pages 3
chromerag batch examples/site -o out/batch --chrome-model out/site_chrome.json

# 3) Chunks as JSON lines
chromerag extract examples/site/pricing.html --chunks
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

### Python options

```python
from chromerag import ChromeRAG, PipelineConfig, ContentPriority

cfg = PipelineConfig.from_priority(ContentPriority.BALANCED)
result = ChromeRAG(config=cfg).extract(html, url="https://docs.example.com/docs/pricing")

print(result.front_matter)    # dict
print(result.tokens_estimate)
print(result.warnings)        # e.g. JS shell → render with Playwright first
print(result.diagnostics)     # rules that fired, kept/rejected samples, per-page confidence
```

Learn-then-extract from Python: `chromerag.learn_then_extract(pages)` or
`load_chrome_models(path)` + `ChromeRAG(site_chrome=model)`. Switches: `--no-rules`, `--no-schema`,
`--no-tables`, `--no-stce`, `--links` (keep link targets), `--table-format linearized` (key-value rows instead
of Markdown tables), `PipelineConfig(enable_lbc=False)` (the 0.1.2 density filter). Every generic chrome rule
has its own flag (`chrome_drop_toc`, `chrome_drop_pager`, `chrome_drop_comments`, `chrome_drop_related`,
`chrome_drop_cta`, `chrome_drop_share`, `chrome_drop_newsletter`, `chrome_drop_author_bio`,
`chrome_drop_nav_misc`, `chrome_trim_tail`, `chrome_drop_attr_junk`, `trafilatura_link_blocks`).

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

`result.chunks()` splits the Markdown into chunks of at most 180 words inside heading sections and never cuts a
code block or table. Each chunk has the heading path (page title → h2 → h3), its depth and `embed_text`, the body
preceded by that path. On 400 questions over 3,395 documentation chunks from sites not used in training,
prepending the path raised dense MRR from 0.853 to 0.913 and BM25 MRR by +0.060 (95% intervals exclude 0;
questions were written by Claude from each chunk and its page title; see
`evaluations/2026-10-v0.1.3/FINAL/heading_context_retrieval.json`).

```python
for chunk in ChromeRAG().extract(html).chunks():
    # chunk.embed_text == "Page Title > Section > Subsection\n<body markdown>"
    vector_db.upsert(text=chunk.embed_text, metadata=chunk.to_dict())
```

### Frequently asked

**Does it need a model download or a GPU?** No. The model is a 150 KB array file inside the wheel.
**Does it run JavaScript?** No; it warns on unrendered shells. Render with Playwright first.
**When should I pick Trafilatura instead?** For plain news or blog articles the two tie on word-level F1 against
human labels (blinded judges slightly prefer ChromeRAG on fresh articles). ChromeRAG is clearly better on forums,
service and product pages, listings and category pages, and when you can show it several pages of one site.
**How do I keep link URLs?** `PipelineConfig(include_links=True)` or `--links`.
**Can I trust the numbers?** Every table below is recomputed from files in the repository (`evaluations/`,
`docs/data/`); learned-model numbers come from cross-validation grouped by site or from a held-out set.

---

## Why ChromeRAG (vs MarkItDown / Trafilatura / Readability)?

| Tool | Best at | Gap for web RAG |
|------|---------|-----------------|
| **MarkItDown** | Office/PDF/HTML → Markdown for LLMs | Keeps most page chrome; not designed to strip nav/footer |
| **Trafilatura** | News/article main content | Weaker on forums, service and category pages; no chunks or site model |
| **Readability** | Single-article extraction | Often drops tables, lists and reference sections |
| **ChromeRAG** | Ingest-time chrome removal + schema + tables + chunks + input warnings | HTML only; fetching/rendering stays in your crawler |

Median time per page on 200 stored pages (one process, Apple M4 Pro): 52 ms ChromeRAG,
32 ms Trafilatura, 31 ms Readability, 39 ms MarkItDown.

---

## How it works

Six stages: input-quality gate → schema harvest → cleaning (YAML rules, generic chrome detectors, optional site
model) → chrome pruning and content-root ladder → learned block filter → tables and Markdown. The learned
filter splits the page into *blocks* (paragraphs, headings, list items, quotes, tables, text-only divs) and scores
each with gradient-boosted trees over about 530 numbers (its text, its place in the tree, the names of its
ancestors, the heading above it, its neighbours). A block is kept when its score reaches the threshold of the
chosen priority: `coverage` 0.30, `balanced` 0.50, `precision` 0.70. The page title, a heading above kept content
and the lead paragraph are always kept. 37 YAML rules (consent managers, share bars, documentation-framework
widgets, 16 rules adapted from Trafilatura's discard patterns, credited in `NOTICE`) and generic detectors remove
tables of contents, pagers, comment sections, related-post blocks, call-to-action buttons, share strips,
newsletter blocks, author boxes and page tails.

* The model is a 150 KB array file (`src/chromerag/assets/lbc_stage1.npz`) evaluated with NumPy only;
  scikit-learn is needed to retrain, not to run. It was trained on human-reviewed pages (WCXB development
  split, 1,495 pages).
* Output keeps headings, bold and italic, inline code, fenced code blocks with their lines, ordered and
  nested lists and GitHub Markdown tables; link targets are omitted unless requested, repeated blocks are
  written once, and the Markdown follows document order.

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
own script on raw default output gives a lower value (the front-matter counts as words).

---

## Results

All numbers below are recomputed from the files in [`docs/data/`](docs/data/) and
[`evaluations/2026-10-v0.1.3/FINAL/`](evaluations/2026-10-v0.1.3/FINAL/) and shown, with a per-page explorer, at
**https://pedapudibhargav.github.io/ChromeRAG/**.

### Human-labelled benchmark (WCXB)

Word-level F1 against human-reviewed main content on the **372 test pages absent from the development folder**
(ChromeRAG in `balanced` mode):

| Page type (n) | ChromeRAG | Trafilatura | Readability | MarkItDown |
|---|---:|---:|---:|---:|
| **All (372)** | **0.907** | 0.867 | 0.778 | 0.568 |
| Article (178) | 0.951 | 0.953 | 0.944 | 0.663 |
| Documentation (40) | 0.949 | 0.931 | 0.866 | 0.614 |
| Service (56) | 0.864 | 0.813 | 0.595 | 0.478 |
| Forum (50) | 0.895 | 0.731 | 0.628 | 0.452 |
| Listing (37) | 0.754 | 0.707 | 0.445 | 0.386 |
| Collection (9) | 0.774 | 0.717 | 0.523 | 0.512 |
| Product (2) | 0.991 | 0.491 | 0.473 | 0.157 |

ChromeRAG − Trafilatura: **+0.040** (95% CI [+0.021, +0.059]); forums +0.164 [+0.102, +0.230]; services +0.051
[+0.004, +0.107]; collections +0.057 [+0.024, +0.090]; articles, documentation and listings are ties. On all
511 test pages (139 of them also in the development folder): 0.901, 0.860, 0.763, 0.540. The test pages were
scored once with the frozen pipeline (see the paper for the leak audit).

### Blinded judging on fresh pages

328 pages from 106 sites (news and blogs, forums, listings, service and software landing pages) whose seed lists
were written before any extractor ran on them and that no development step used. A judge sees the page's text
and two outputs in random order, tool names hidden, and applies one rubric. Net score = wins − losses over pairs
(+1 = always preferred), ChromeRAG against Trafilatura:

| Judge | All (328) | Articles | Forums | Listings | Services |
|---|---:|---:|---:|---:|---:|
| Claude Sonnet 5.5 | **+0.41** [+0.33, +0.50] | +0.32 | +0.93 | +0.27 | +0.31 |
| GPT-5.6 luna | **+0.19** [+0.09, +0.29] | +0.07 | +0.48 | +0.27 | +0.17 |
| Gemini 3.7 Flash | **+0.45** [+0.35, +0.54] | +0.37 | +0.91 | +0.33 | +0.34 |

On the 367 WCXB test pages the nets are +0.25 [+0.16, +0.34] (Claude) and +0.22 [+0.13, +0.32] (GPT). Against
Readability on the fresh pages GPT gives +0.52 [+0.44, +0.61]. On 180 held-out documentation pages GPT gives
+0.07 [−0.07, +0.21] (a tie) and on 97 held-out product pages +0.40 [+0.22, +0.57]. Content kept scores higher
for ChromeRAG and chrome left out about equal. These are language-model judges, not people: agreement across
three families is evidence, not a human study. Raw verdicts: `evaluations/2026-10-v0.1.3/FINAL/`.

### Structural-anchor benchmark

**Metrics** (deterministic, computed from each input DOM, independent of any extractor):

| Metric | Meaning | Better |
|--------|---------|--------|
| **Recall** (`content_recall`) | Share of `<main>`/`<article>` 5-gram anchors kept | Higher |
| **Noise ret** (`noise_retention`) | Share of nav/header/footer/aside/cookie anchors kept | Lower |
| **Fbal** (`f_balanced`) | Harmonic mean of recall and (1 − noise) | Higher |

**Corpus:** 367 unique URLs in `poc/corpus_urls.json` → **268** unique pages fetched (plain HTTP, no
JS rendering) → **242 scoreable** (a page is scoreable when its **input HTML** has ≥ 50 main-content anchors; the rule
never looks at any tool's output). 208 of the 242 pages are documentation.

| Method | Recall ↑ | Noise ↓ | Fbal ↑ (242 scoreable) | Fbal ↑ (all 268) |
|--------|--------:|--------:|-------:|-------:|
| chromerag_coverage | 0.696 | 0.009 | **0.797** | **0.755** |
| chromerag (balanced) | 0.653 | 0.007 | 0.765 | 0.718 |
| trafilatura | 0.640 | 0.012 | 0.739 | 0.696 |
| markitdown | 0.691 | 0.250 | 0.696 | 0.661 |
| readability | 0.449 | 0.013 | 0.531 | 0.495 |

This corpus was a **development** set (rules were tuned against it; it was re-fetched on 2026-10-02) and is not
held out. Paired bootstrap (95% CI): coverage − Trafilatura Fbal **+0.058 [+0.034, +0.085]**; coverage −
MarkItDown noise **−0.242 [−0.264, −0.219]**. On the held-out landing pages the coverage Fbal is 0.741 against
0.680 for Trafilatura (+0.061 [+0.032, +0.090], 177 pages) and on 178 pages of companies fetched after the 0.1.3
freeze 0.735 against 0.649 (+0.087 [+0.054, +0.119]). The anchors come from `<main>`/`<article>`, which
ChromeRAG's content-root selection also prefers, and cannot see chrome inside `<main>`, which the rules remove, so
treat this as a proxy; the human-labelled and blinded results above are the primary evidence.

### Retrieval

Each tool's output is split into ~200-word chunks and indexed with BM25. 773 known-item queries
(page titles, section headings and content passages from the input HTML, each with exactly one
correct page) are run against each index.

| Method | Hit@5 ↑ | Chrome in top-5 context ↓ | Chunks indexed |
|--------|--------:|--------:|--------:|
| chromerag_coverage | 0.946 | 0.6% | 1,898 |
| chromerag (balanced) | 0.948 | 0.4% | 1,634 |
| trafilatura | 0.921 | 0.6% | 1,950 |
| markitdown | 0.964 | 2.6% | 3,909 |
| readability | 0.775 | 0.6% | 1,702 |

ChromeRAG (coverage) vs Trafilatura hit@5 +0.025 [+0.005, +0.047]; vs MarkItDown −0.018 [−0.036, 0.000] with
about half the chunks and a tenth of the chrome in the retrieved context. On 178 fresh-company pages
(668 queries) hit@5 is 0.894 (balanced) against 0.832 for Trafilatura, with 0.3% against 1.1% chrome in the context.

### Site-template learning (STCE)

`chromerag learn` is evaluated by `poc/run_stce_eval.py` (coverage mode, with vs without the site
model) on the benchmark's site groups with ≥ 3 unique pages and on a crawl of up to 15 same-section
pages per documentation site (`poc/stce_crawl_urls.json`, fetched with `poc/crawl_site_groups.py`).

| Set | Variant | Content recall | Noise retained | F_bal | Site-repeated text |
|---|---|---:|---:|---:|---:|
| Benchmark groups (11 sites, 47 pages) | ChromeRAG | 0.747 | 0.002 | 0.840 | 0.4% |
| | ChromeRAG + site model | 0.743 | 0.002 | 0.837 | 0.5% |
| | Trafilatura | 0.689 | 0.001 | 0.786 | 0.5% |
| | MarkItDown | 0.700 | 0.306 | 0.682 | 26.7% |
| Crawl (125 sites, 1,727 pages) | ChromeRAG | 0.790 | 0.009 | 0.866 | 2.0% |
| | ChromeRAG + site model | 0.791 | 0.008 | 0.867 | 2.0% |
| | Trafilatura | 0.759 | 0.005 | 0.841 | 2.1% |
| | MarkItDown | 0.776 | 0.244 | 0.749 | 34.9% |

Single-page extraction and the rules already remove most repeated chrome, so STCE is an optional, guarded
complement for template blocks that read like content (like the "Widget Summit" paragraph in the quick start); it
no longer adds measurable accuracy on these pages.

---

## Reproduce the evaluation

```bash
pip install -e ".[dev,baselines]"

# Offline: recompute the published cohort and every leaderboard mean from docs/data/
python scripts/revalidate_corpus.py

# Human-labelled benchmark (needs WCXB in data/wcxb/)
python -m poc.run_wcxb_eval --split test --final --out /tmp/wcxb_test.json

# Anchor benchmark: fetch the public corpus into data/raw/ and score every tool (network)
python -m poc.run_corpus_comparison            # add --no-fetch to re-score stored HTML

# Retrieval over each tool's chunks (uses the outputs written above)
python -m poc.run_retrieval_eval

# Blinded judging: build pairs, then judge them with a model of your choice
EXTRA_FINAL2=1 python -m poc.extra_corpus      # fetch the frozen fresh-page seed lists (network)
python -m poc.claude_judge_build --set final2  # writes blinded batches and a hidden key
python -m poc.gpt_judge_batches --tag final2   # GPT judge (needs OPENAI_API_KEY)
python -m poc.claude_judge_aggregate --set final2 --dir /tmp/cr/judge_gpt

# Site-template learning: benchmark sites, then a multi-page crawl (network)
python -m poc.run_stce_eval
python -m poc.crawl_site_groups --fetch        # pages listed in poc/stce_crawl_urls.json
python -m poc.run_stce_eval --raw data/stce_crawl

# Publish: copy results into docs/data, run tests, assemble _site/ (CI does this on main)
bash scripts/build_docs.sh
```

Live pages change over time, so a fresh fetch will not reproduce the published numbers exactly;
the published per-page scores are in `docs/data/corpus_comparison_report.json` and `evaluations/`. Behind a
TLS-intercepting proxy, point `SSL_EXTRA_CA` at the proxy's CA bundle before fetching.

---

## Project layout

```
src/chromerag/     # library (HTML in → Markdown and chunks out)
examples/          # small synthetic site for the quick start
tests/             # unit, CLI, rule-fixture and golden-output tests
poc/               # fetch, baselines, benchmarks, judging, retrieval and STCE evaluations (not needed at runtime)
docs/              # one-page GitHub Pages site (index.html) + published results (data/)
evaluations/       # per-page results, judge verdicts and logs behind the paper
scripts/           # revalidation, docs build, paper figures
papers/softwarex/  # SoftwareX manuscript sources
```

---

## Citation

If you use ChromeRAG, please cite the software (see [`CITATION.cff`](CITATION.cff)). To cite whichever version is
latest, use the all-versions DOI [10.5281/zenodo.22970289](https://doi.org/10.5281/zenodo.22970289):

> B. C. Peddapudi, *ChromeRAG*, Zenodo, 2026. https://doi.org/10.5281/zenodo.22970289

## License

MIT — see [LICENSE.txt](LICENSE.txt). Discard patterns adapted from Trafilatura (Apache-2.0) are credited in
[NOTICE](NOTICE).
