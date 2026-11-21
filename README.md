# ChromeRAG

[![PyPI](https://img.shields.io/pypi/v/chromerag.svg)](https://pypi.org/project/chromerag/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![ci](https://github.com/pedapudibhargav/ChromeRAG/actions/workflows/ci.yml/badge.svg)](https://github.com/pedapudibhargav/ChromeRAG/actions/workflows/ci.yml)
[![Results](https://img.shields.io/badge/results-0.1.5%20evaluation-2a78d6.svg)](evaluations/2026-11-final/)
[![DOI](https://zenodo.org/badge/1378773845.svg)](https://doi.org/10.5281/zenodo.22970289)

**HTML → RAG-ready Markdown and chunks.** A small learned block filter and a few evidence-backed rules remove
navigation, footers, calls to action, cookie banners, share strips and comment sections of articles, and keep
article text, documentation, forum threads, tables and code. Pure NumPy inference: no GPU, no model download.
Chunks carry their heading path, ready for a vector database.

> Built for **RAG ingest**, **LLM chunking**, **vector indexing** and **boilerplate / noise removal** from stored
> HTML, not for pixel-perfect web archiving.

| Owns | Does **not** own |
|---|---|
| HTML string / file → clean Markdown | Crawling, Playwright, rate limits |
| Heading-aware chunks with `embed_text` | Vector DB / embeddings |
| Schema.org → YAML front matter | Rendering JavaScript shells (it warns; render first) |
| Tables, code and lists kept as Markdown | Hosted SaaS API |
| Precision / coverage priority modes | PDF / Office formats |
| Optional site-template model (`learn` → `batch`), experimental | |

**Paper:** *ChromeRAG: A Learned Boilerplate Filter for Web RAG Ingestion* (under revision at SoftwareX)  
**Release:** [`v0.1.6`](https://github.com/pedapudibhargav/ChromeRAG/tree/v0.1.6) (evaluated code: [`v0.1.5`](https://github.com/pedapudibhargav/ChromeRAG/tree/v0.1.5); 0.1.6 only fixes `chunks()`) · DOI (all versions) [10.5281/zenodo.22970289](https://doi.org/10.5281/zenodo.22970289)  
**Author:** [Bhargava Chary Peddapudi](https://orcid.org/0009-0002-8523-8415)

---

## Install

Requires **Python 3.11+**. CPU only; no model downloads. Four direct dependencies (BeautifulSoup, lxml, PyYAML, NumPy).

```bash
pip install chromerag==0.1.6
chromerag --version          # chromerag 0.1.6
```

From source (adds tests and the benchmark baselines):

```bash
git clone https://github.com/pedapudibhargav/ChromeRAG.git
cd ChromeRAG
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev,baselines]"
ruff check .
pytest -q
```

The `ci` workflow runs `ruff check .` and `pytest -q` on Linux, macOS and Windows with Python 3.11 and 3.13 on every
push and pull request; tests that need the WCXB data or optional integrations are skipped there. The `pypi-smoke`
workflow installs each release from PyPI on the same systems and runs [`scripts/readme_smoke.sh`](scripts/readme_smoke.sh),
which follows the quick start below.

---

## Quick start

```python
from chromerag import ChromeRAG

result = ChromeRAG().extract(open("page.html", encoding="utf-8").read(), url="https://example.com/page")
print(result.markdown)              # RAG-ready Markdown with YAML front matter (always written; Schema.org fields when present)
for chunk in result.chunks():       # heading-aware chunks for a vector database
    vector_db.upsert(text=chunk.embed_text, metadata=chunk.to_dict())
```

The repository ships a small synthetic documentation site in [`examples/site/`](examples/): four pages that share a
header menu, cookie banner, sales call to action, footer and a repeated event paragraph inside `<main>`. Run these from
the repository root:

```bash
# 1) One page → Markdown (JSON-LD becomes YAML front matter, the plan table becomes a Markdown table;
#    --json-meta prints front matter, warnings, input quality and diagnostics as JSON on stderr)
chromerag extract examples/site/pricing.html -o out/pricing.md --priority balanced --json-meta

# 2) Chunks as JSON lines, each with heading_path and embed_text
chromerag extract examples/site/pricing.html --chunks

# 3) Optional: learn the site's repeated blocks from ≥3 pages, then batch-extract with the site model
chromerag learn examples/site -o out/site_chrome.json --min-pages 3
chromerag batch examples/site -o out/batch --chrome-model out/site_chrome.json
```

`out/pricing.md` starts with the front matter (`title: Plans and pricing`, `type: TechArticle`, …), then the page
title, the intro paragraph and the plan table (`| Team | 20,000 | 49 |`); the menu, cookie banner, call to action,
event paragraph and footer are gone. The pricing page gives one chunk with `heading_path`
`["Plans and pricing", "Reference table"]`.

`learn` finds six chrome signatures in one site group (`docs.example.com/docs`); `batch` writes
`out/batch/<page>/chromerag.md` plus `out/batch/batch_summary.json`. In version 0.1.4 the learned filter kept the
repeated event paragraph and only the site model removed it. The 0.1.5 filter already removes it from every page, so
`batch` gives byte-identical Markdown with and without the site model on this example. The site model (STCE) helps
only when a template block reads like content to the filter; it is optional, off unless a site model is given or `batch` learns one (five or more pages per site group;
`--no-learn` turns it off), and was
last measured with version 0.1.4 (see [Earlier evaluations](#earlier-evaluations-v014-superseded)).

Priorities: `precision` (strip more) · `balanced` (default) · `coverage` (keep more).

### Thin / JavaScript-shell input

ChromeRAG does not execute JavaScript. Unrendered single-page-application shells produce a warning on stderr (and in
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
print(result.diagnostics)     # rules that fired, tables rescued, per-page confidence estimate
```

Learn-then-extract from Python: `chromerag.learn_then_extract([BatchPage(html=..., url=..., page_id=...)])`
(`from chromerag.batch import BatchPage`), or `models = load_chrome_models(path)` and
`ChromeRAG(site_chrome=models["docs.example.com/docs"])`. Command-line switches: `--no-rules`, `--no-schema`, `--no-tables` (drop tables), `--no-stce`,
`--links` (keep link targets), `--table-format linearized` (key-value rows instead of Markdown tables). Every stage
can be switched off in `PipelineConfig` (`enable_lbc`, `enable_rules`, `enable_generic_chrome`, `enable_chrome_prune`,
`enable_trafilatura_rules`, `enable_lbc_structure_rules`, `enable_lbc_stage2`, `lbc_rescue_tables`,
`lbc_rich_collapsed_retry`), and every generic chrome detector has its own flag (`chrome_drop_toc`,
`chrome_drop_comments`, `chrome_drop_cta`, `chrome_drop_share`, `chrome_drop_newsletter`, `chrome_drop_author_bio`,
`chrome_drop_nav_misc`, `chrome_trim_tail`, `chrome_drop_attr_junk`; `chrome_drop_pager` and `chrome_drop_related`
are off by default since 0.1.5).

### Use it in a RAG pipeline

```python
# LangChain:  pip install "chromerag[langchain]"
from chromerag.integrations.langchain import ChromeRAGLoader
docs = ChromeRAGLoader(["pages/pricing.html"], urls={"pages/pricing.html": "https://example.com/pricing"}).load()

# LlamaIndex: pip install "chromerag[llamaindex]"
from chromerag.integrations.llamaindex import ChromeRAGReader
docs = ChromeRAGReader().load_data(["pages/pricing.html"])
```

Front matter (title, type, lastUpdated, breadcrumb) becomes document metadata, so a text splitter copies it onto every chunk.

### Chunks for vector databases

`result.chunks()` splits the Markdown into chunks of up to about 180 words inside heading sections and never cuts a
paragraph, code block or table. A short section is merged into a neighbouring chunk and then carries that chunk's heading
path; in 0.1.5 a short section with no neighbour to merge with is dropped (fixed in 0.1.6). Each chunk has the heading path (page title → h2 → h3), its depth and `embed_text`, the body
preceded by that path.

```python
for chunk in ChromeRAG().extract(html).chunks():
    # chunk.embed_text == "Page Title > Section > Subsection\n<body markdown>"
    vector_db.upsert(text=chunk.embed_text, metadata=chunk.to_dict())
```

### Frequently asked

**Does it need a model download or a GPU?** No. The model is a 152 KB array file inside the wheel.
**Does it run JavaScript?** No; it warns on unrendered shells. Render with Playwright first.
**When should I pick Trafilatura instead?** For plain news or blog articles Trafilatura is slightly better on WCXB
(0.952 against 0.940 word F1) and about three times faster. ChromeRAG's gain is largest on forums and
question-and-answer threads, and it adds front matter, Markdown tables, chunks and input warnings.
**How do I keep link URLs?** `PipelineConfig(include_links=True)` or `--links`.
**Can I trust the numbers?** The 0.1.5 numbers below come from a frozen tag (`freeze-0.1.5`) and the result files in
[`evaluations/2026-11-final/`](evaluations/2026-11-final/), with a ledger of the held-out runs. The WCXB test split
was consulted during earlier development and is reported as such.

---

## How it works

Six stages: input-quality gate → schema harvest → cleaning (YAML rules, generic chrome detectors, optional site
model) → chrome pruning → learned block filter → tables and Markdown. The learned filter splits the page into
*blocks* (paragraphs, headings, list items, tables, preformatted or loose text) and scores each with gradient-boosted
trees (300 trees of depth 6) over 535 features: its text, its position, its tree context, feature-hashed class and id
words of its ancestors and the heading above it. A block is kept when its score reaches the threshold of the chosen
priority: `coverage` 0.30, `balanced` 0.50, `precision` 0.70. The page title, headings above kept content and the lead
paragraph are kept; a table rescue keeps data tables under kept headings, and a retry in coverage mode handles
collapsed output (the richer collapse signal follows a design described for rs-trafilatura). 13 YAML rules (3 consent
managers, 2 share/related blocks, 8 rules adapted from Trafilatura's discard patterns, credited in `NOTICE`) and
generic detectors remove in-page tables of contents, comment sections of articles, call-to-action buttons, share
strips, newsletter blocks, author boxes and footer-like page tails. A per-page F1 estimate below 0.70 raises a warning.

* The model is a 152,432-byte array file (`src/chromerag/assets/lbc_stage1.npz`) evaluated with NumPy only;
  scikit-learn is needed to retrain, not to run. Version 0.1.5 is trained on a strict subset of the public WCXB
  development folder: of its 1,473 pages with at least 30 reference words, the 139 that duplicate test pages and the 96
  whose registrable domain (Public Suffix List) occurs in the test split are removed, leaving 1,238 pages. A test asserts that no training domain is a test domain.
* A five-fold, domain-grouped ablation on those 1,238 pages
  ([`evaluations/2026-10-v0.1.3/strict_ablation_cv.json`](evaluations/2026-10-v0.1.3/strict_ablation_cv.json)) decided
  which components to drop: five Trafilatura-derived rule groups and 16 documentation-framework rules were dropped and
  the pager and related-post detectors switched off. Structure rules, table rescue and a few switches without a
  measured benefit (among them the consent rules) were kept and are listed in Table S5 of the supplement.
* Output keeps headings, bold and italic, inline code, fenced code blocks with their lines, ordered and nested lists
  and GitHub Markdown tables (up to 200 rows and 12 columns; larger tables become key-value rows, and a table is never
  split across chunks, so one large table forms one large chunk); link targets are omitted unless requested.

Retrain the shipped strict model (needs `pip install -e ".[train]"` and WCXB in `data/wcxb/`). From the repository root
with `PYTHONPATH=src:.`:

```bash
bash poc/rebuild_strict.sh          # full sequence: ids, feature table, 5 fold models, fit-all verify (byte-identical
                                    # to the shipped model), strict_dev_cv.json, ablation_cv, golden (long)
# Or step by step:
python -m poc.strict_split --write  # refreshes poc/wcxb_strict_train_ids.json
python -m poc.lbc_data --split dev  # -> data/outputs/lbc/lbc_strict.npz (default strict ids)
for k in 0 1 2 3 4; do
  python -m poc.train_lbc --data data/outputs/lbc/lbc_strict.npz --holdout-fold "$k" \
    --out-dir "data/outputs/lbc/cv/fold_$k"
done
python -m poc.train_lbc --data data/outputs/lbc/lbc_strict.npz --fit-all --out-dir data/outputs/lbc/verify_a
cmp data/outputs/lbc/verify_a/lbc_stage1.npz src/chromerag/assets/lbc_stage1.npz
python -m poc.update_strict_manifest --verify-npz data/outputs/lbc/verify_a/lbc_stage1.npz
python -m poc.run_strict_dev_cv --jobs 6
python -m poc.ablation_cv --no-cache --train-stack --jobs 6
python -m poc.golden --write
```

**WCXB data.** Get WCXB v1.0 (CC-BY-4.0, https://arxiv.org/abs/2605.21097) into
`data/wcxb/{dev,test}/{ground-truth/*.json,html/*.html.gz}`. Scores are computed on the Markdown body with ChromeRAG's
YAML front matter removed unless a row says "raw"; the front matter counts against precision because the reference
holds body text only.

---

## Results (version 0.1.5)

All numbers are read from the files in [`evaluations/2026-11-final/`](evaluations/2026-11-final/); supplementary
tables S1–S9 are in [`evaluations/2026-11-final/SUPPLEMENT.md`](evaluations/2026-11-final/SUPPLEMENT.md). The code
was frozen (tag `freeze-0.1.5`) before any held-out run of 0.1.5 code; the protocol, page list and rubric were tagged before the runs
they govern (`protocol-2026-11`, `protocol-2026-11a`, `pages-2026-11`, `rubric-2026-11`); the human page list changed
before rating (Table S6). Scripted runs are listed in
[`results/held_out_runs.jsonl`](evaluations/2026-11-final/results/held_out_runs.jsonl), and runs without a ledger row
(author records) in Table S1b of the supplement.

### WCXB test split (511 pages, human-reviewed main content)

Word-level F1, "without" = share of listed chrome snippets left in (lower is better), "with" = share of required
snippets kept. All tools receive the same HTML and no site model; Trafilatura 2.2.0 runs without metadata.

| Tool | F1 | Without | With |
|---|---:|---:|---:|
| **ChromeRAG 0.1.5 balanced** | **0.884** | 0.070 | 0.759 |
| ChromeRAG balanced, raw default output (front matter kept) | 0.853 | 0.092 | 0.761 |
| ChromeRAG coverage / precision | 0.882 / 0.872 | 0.083 / 0.060 | 0.781 / 0.725 |
| Trafilatura 2.2.0 | 0.860 | 0.083 | 0.720 |
| rs-trafilatura 0.1.1 | 0.891 | 0.111 | 0.864 |
| Readability | 0.763 | 0.089 | 0.552 |
| BoilerPy3 1.0.7 Default / Article | 0.753 / 0.686 | 0.150 / 0.099 | 0.695 / 0.545 |
| jusText 3.0.2 | 0.713 | 0.058 | 0.593 |
| MarkItDown 0.1.7 | 0.540 | 0.967 | 0.768 |

Balanced ChromeRAG minus Trafilatura (both without metadata): **+0.024** [+0.008, +0.042] (paired, 5,000 resamples of
444 sites). Raw default output against Trafilatura's default: −0.006 [−0.022, +0.010], a tie; with metadata on both
sides: +0.022 [+0.007, +0.037]. rs-trafilatura ties with ChromeRAG on F1 (+0.007 [−0.013, +0.025]) and leaves more
listed chrome; it was developed against the same development folder, and no superiority is claimed. The freeze-0.1.3
code with the 0.1.5 model scores 0.885, so later rule changes did not raise F1 here.

| Page type (n) | ChromeRAG | Trafilatura | Difference [95% CI] | rs-trafilatura |
|---|---:|---:|---|---:|
| Article (257) | 0.940 | 0.952 | −0.012 [−0.024, −0.001] | 0.951 |
| Documentation (42) | 0.954 | 0.934 | +0.020 [−0.022, +0.070] | 0.973 |
| Service (59) | 0.849 | 0.817 | +0.031 [−0.008, +0.071] | 0.832 |
| Forum (51) | 0.866 | 0.717 | +0.149 [+0.092, +0.230] | 0.836 |
| Listing (40) | 0.732 | 0.722 | +0.010 [−0.113, +0.140] | 0.748 |
| Product (28) | 0.805 | 0.724 | +0.081 [+0.000, +0.181] | 0.777 |
| Collection (34) | 0.704 | 0.626 | +0.078 [−0.002, +0.152] | 0.775 |

The gain comes from forums and, less certainly, products and collections; Trafilatura leads on articles. **The WCXB
test split was consulted during development of versions 0.1.3 and 0.1.4**, so it is not clean held-out evidence (Table
S1). On the 1,238 strict development pages (five folds grouped by registrable domain) balanced F1 is 0.859 against
0.828 for Trafilatura.

### Human raters and AI judges (75 new pages)

Five volunteer raters compared ChromeRAG (balanced), Trafilatura and Readability blind on 75 pages from 48 sites, mostly three
raters per page, with an analysis plan fixed before rating. Net = share of pages won minus share lost (majority
verdict per page), 95% site-bootstrap interval:

| Judge | vs Trafilatura, all 75 | Forums (10) | Without forums (65) | vs Readability, all 75 |
|---|---|---|---|---|
| Human majority | +0.23 [+0.01, +0.42] | +0.80 [+0.60, +1.00] | +0.14 [−0.09, +0.35] | +0.33 [+0.13, +0.52] |
| GPT gpt-5.6-luna | +0.21 [−0.03, +0.44] | +0.60 [+0.00, +1.00] | +0.15 [−0.09, +0.39] | +0.35 [+0.12, +0.56] |
| Grok 4.5 | +0.25 [+0.03, +0.48] | +1.00 [+1.00, +1.00] | +0.14 [−0.09, +0.37] | +0.32 [+0.08, +0.54] |
| Gemini | +0.25 [+0.01, +0.48] | +1.00 [+1.00, +1.00] | +0.14 [−0.11, +0.39] | +0.33 [+0.10, +0.55] |

Outside forums the interval against Trafilatura includes zero. Agreement among raters is low
(Krippendorff's α 0.42). Pseudonymized ratings: [`evaluations/2026-11-final/human_set_ratings/`](evaluations/2026-11-final/human_set_ratings/);
the analysis is [`poc/human_set_analysis.py`](poc/human_set_analysis.py); the rating app is in [`evaluators/`](evaluators/).
On 296 further new pages a GPT judge preferred ChromeRAG to Trafilatura (158–114–24), but longer outputs won 65% of
decided pairs and a fixed-order check ties 74–74, so this is weak evidence (Table S8).

### Answers on CRAG (500 questions, split 1, run once)

Each tool's output is cut into 200-word chunks, BM25 retrieves the top five, and gpt-5.6-luna answers from them and
grades the answers (score = accurate − incorrect). Balanced ChromeRAG 0.306, Trafilatura 0.298: +0.008
[−0.040, +0.054], no measurable difference in answer accuracy, from an index of 1,948 against 2,335 words per page.

### Speed

Median time per page on the 511 WCXB test pages, one process, one timed pass after a warm-up, Apple M4 Pro, Python
3.14, with other processes running on the machine
([`revision_rows/speed.json`](evaluations/2026-11-final/results/revision_rows/speed.json)):

| Tool | Median ms | 90th percentile ms |
|---|---:|---:|
| ChromeRAG 0.1.5 balanced | 39.6 | 86.3 |
| Trafilatura 2.2.0 | 14.2 | 41.1 |
| Readability | 15.8 | 38.2 |
| jusText | 8.1 | 17.0 |

ChromeRAG is about three times slower than Trafilatura here, about 20–25 pages per second per process. Timings depend
on the page set, Python version and machine load: the v0.1.4 measurement on 200 other stored pages gave 52 ms against
32 ms (1.6 times). Repeat the measurement from a `v0.1.5` checkout (see below; the script runs on macOS) with `python -m poc.revision_rows speed --wcxb-root data/wcxb --out out/speed.json`; on your
own pages, time `ChromeRAG().extract`.

### Earlier evaluations (v0.1.4, superseded)

The v0.1.4 README reported 0.907 F1 on 372 WCXB test pages, 52 ms per page, blinded LLM-judge panels on 328 fresh
pages (Claude, GPT, Gemini), a structural-anchor benchmark, BM25 retrieval, a heading-path retrieval study with
questions written by Claude, and the site-template (STCE) study. Those results came from a model trained with test
domains present, from pages and judge rounds used while the code was still changing, and partly from Claude-judged
rounds; they are superseded and not used for claims. The files stay in
[`evaluations/2026-10-v0.1.3/`](evaluations/2026-10-v0.1.3/) and [`docs/data/`](docs/data/) for the record. The last
STCE measurement (version 0.1.4) changed a structural score by 0.001 or less on 1,727 crawled pages.

---

## Reproduce the evaluation

The evaluation scripts check that `src/` matches tag `freeze-0.1.5` and stop otherwise, so run them from the
evaluated release (0.1.6 changes only `chunks()`):

```bash
git checkout v0.1.5
pip install -e ".[dev,baselines]"
# baseline versions used in the paper (the extras pin only minimums)
pip install "trafilatura==2.2.0" "readability-lxml==0.9" "markitdown==0.1.7" "justext==3.0.2" "boilerpy3==1.0.7"
export PYTHONPATH=src:.

# WCXB test split: the protocol run and the revision rows (need WCXB in data/wcxb/)
python -m poc.final_wcxb --wcxb-root data/wcxb --outputs-dir out/wcxb_outputs --out out/wcxb_test.json
python -m poc.revision_rows --help             # extract, p07, p03, justext, boilerpy3, speed, gt-manifest

# Strict development cross-validation and the component ablation
python -m poc.run_strict_dev_cv --jobs 6
python -m poc.ablation_cv --no-cache --jobs 6

# Human rating set: analysis fixed in advance, from the pseudonymized ratings and the label key
python -m poc.human_set_analysis --out out/human_set

# AI page judge and CRAG answer test (need OPENAI_API_KEY; CRAG data from its authors). The 296-page judge run cannot
# be repeated (raw HTML not retained); its verdicts are in evaluations/2026-11-final/results/new_pages/.
python -m poc.final_page_judge --help
python -m poc.crag_answer_eval --help

# Held-out ledgers: scripted 0.1.5 runs are in evaluations/2026-11-final/results/held_out_runs.jsonl (others: Table S1b).
# evaluations/2026-10-v0.1.3/HELD_OUT_LEDGER.csv was built once from the original checkout's file times;
# do not regenerate it from a clone (poc.held_out_ledger overwrites it only with --write).
```

Third-party HTML pages are not redistributed; page lists, URLs and hashes are in `evaluations/2026-11-final/`.

---

## Project layout

```
src/chromerag/     # library (HTML in → Markdown and chunks out)
examples/          # small synthetic site for the quick start
evaluators/        # blind human-rating kit (stdlib app + author build/analyse); see evaluators/README.md
tests/             # unit, CLI, rule-fixture and golden-output tests
poc/               # training, baselines, benchmarks, judging and analysis scripts (not needed at runtime)
evaluations/       # protocols, page lists, per-page results, ratings and the held-out ledger behind the paper
docs/              # one-page GitHub Pages site (v0.1.4 results, marked superseded) + data
scripts/           # README smoke test, docs build, paper figures and template filling
papers/softwarex/  # SoftwareX manuscript sources
```

---

## Citation

If you use ChromeRAG, please cite the software (see [`CITATION.cff`](CITATION.cff)):

> B. C. Peddapudi, *ChromeRAG*, version 0.1.5, Zenodo, 2026. https://doi.org/10.5281/zenodo.24411402

The all-versions DOI always resolves to the latest version; each version's own DOI is listed on that record:
[10.5281/zenodo.22970289](https://doi.org/10.5281/zenodo.22970289).

## License

MIT — see [LICENSE.txt](LICENSE.txt). Discard patterns adapted from Trafilatura (Apache-2.0) are credited in
[NOTICE](NOTICE).
