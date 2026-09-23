# ChromeRAG: Ingest-Time Elimination of Site Template Noise for Enterprise Web RAG

**Target journal:** Elsevier *SoftwareX* (Original Software Publication)  
**Package:** `chromerag`  
**Draft status:** Expanded content draft (~2,940 words, abstract+body+captions) for paste into the **official SoftwareX Word/LaTeX template**. Do not submit this Markdown file as-is.

**Authors:** Bhargava Chary Peddapudi (Independent Researcher; ORCID: https://orcid.org/0009-0002-8523-8415)  
**Corresponding email:** pedapudibhargav@gmail.com

---

## Abstract

Enterprise retrieval-augmented generation (RAG) pipelines routinely index scraped HTML whose navigation chrome, marketing banners, cookie-consent notices, and footer blocks pollute the embedding space. Existing extractors such as Trafilatura and Readability are optimized for news article main-content; general Markdown converters such as MarkItDown preserve rich structure at the cost of substantial chrome retention. **ChromeRAG** (`chromerag`) is a CPU-first Python toolkit that converts HTML to RAG-ready Markdown through site-template chrome elimination (STCE), optional density/vector noise pruning (DVDF) via an ONNX MiniLM model, Schema.org front-matter fusion, and table key-value linearization. On a public benchmark corpus (373 URLs listed; 277 fetched; 238 scoreable), ChromeRAG coverage mode achieves F_bal 0.800 versus Trafilatura 0.752, MarkItDown 0.695, and Readability 0.535, while holding chrome noise retention to 0.005. JavaScript-shell inputs emit explicit operator warnings so callers can verify their fetch/render pipeline rather than silently averaging thin pages into benchmark means. The software is MIT-licensed on GitHub and PyPI (`pip install chromerag`) and ships with a CLI, static Compare Lab, and reproducible benchmark scripts.

**Keywords:** RAG; HTML extraction; boilerplate removal; vector pollution; Markdown; enterprise search

---

## Motivation and significance

**The vector-pollution problem in enterprise RAG.** Retrieval-augmented generation has become the dominant architecture for grounding large language models in organizational knowledge. Enterprise deployments typically ingest documentation portals, product knowledge bases, API references, pricing pages, and support wikis—corpora whose HTML was not authored for machine consumption. When a crawler fetches such pages, the raw HTML bundles factual prose with persistent chrome: top navigation menus repeated across every page, sidebar link trees, cookie-consent banners, global footers containing legal notices and social links, and call-to-action overlays. Converting this HTML with a generic extractor and embedding the result pollutes the vector store. At query time, high-frequency chrome chunks produce false positives, dilute genuine content neighbors, and inflate the context windows sent to the generative model. The problem compounds at scale: a 10,000-page documentation corpus in which each page carries 200 tokens of repeated footer yields two million wasted embedding tokens and a proportionate share of retrieval noise that no retriever-side heuristic can cleanly resolve.

**Why existing tools leave a gap.** The HTML extraction landscape offers several mature tools, each optimized for a different primary objective. Trafilatura [1] excels at extracting the main text of news and blog articles through a density-based boilerplate filter; it achieves strong recall on editorial content but was not designed for corporate documentation layouts where chrome and content are interleaved at similar text densities. Readability (as exposed by readability-lxml [6] and its Mozilla/Arc90 antecedents) targets single-article extraction and performs poorly on reference pages, tables, or multi-section API documentation. MarkItDown [5] faithfully preserves document structure—tables, code blocks, and headings—but is explicitly a format converter rather than a chrome filter; it retains navigation and footer text at approximately the same fidelity as body prose, yielding the high F_bal-penalizing noise retention (≈0.261) observed in the benchmark. Template-extractor research such as Alarte et al. [2] studies structural HTML patterns across corpora but does not produce an end-to-end RAG ingest toolkit. Query-time approaches such as HtmlRAG [3] prune HTML within the retrieval context window rather than at index time, making them complementary to—rather than substitutes for—ingest-time chrome removal.

**The ChromeRAG contribution.** No existing tool jointly provides: (i) a domain-adaptive, learn-then-extract site chrome model that observes multiple pages from the same domain and identifies recurrent structural fragments before extracting any individual page; (ii) Schema.org JSON-LD and Microdata harvested into YAML front-matter, giving each Markdown document typed metadata (article name, description, datePublished) for chunk-level context enrichment; (iii) pricing and specification table linearization that converts `<table>` elements into key-value pairs suitable for dense-passage embedding; and (iv) explicit input-quality warnings that distinguish correctly processed sparse pages from broken JavaScript shells that require upstream Playwright rendering. ChromeRAG targets these gaps as an **ingest-time, query-agnostic** software layer—orthogonal to query-time HTML pruning [3] and independent of any particular retriever or language model.

**Relevance to scientific and engineering practice.** Scientific discovery, software engineering assistance, and enterprise decision-support increasingly depend on assistants grounded in large organizational web corpora. A reproducible, CPU-first ingest component that reduces chrome pollution improves retrieval faithfulness without requiring GPU-based extractors or per-query HTML manipulation. The software is a citable, inspectable, MIT-licensed toolkit with a clearly bounded scope and reproducible evaluation scripts. SoftwareX is the appropriate venue because the primary contribution is the software artifact itself; the corpus benchmark serves as illustrative validation rather than a methodological claim about the state of the art.

---

## Software description

### Software architecture

ChromeRAG processes each HTML document through a sequential pipeline with clearly separated, independently testable stages.

An **input-quality gate** runs first. The raw HTML is inspected for DOM sparsity and characteristic JavaScript-shell signatures—an `<html>` tree whose `<body>` contains only `<div id="root">` or `<div id="app">` wrappers with negligible text content. Pages that meet a minimum content threshold proceed normally; pages that fail emit `WARNING:` messages on stderr and populate `result.warnings`, enabling callers to route flagged inputs to a Playwright rendering step before re-ingestion. The gate evaluates the true input, before any stripping, so warnings reflect the document as received rather than a processed residue.

The second stage harvests **Schema.org metadata**: JSON-LD `<script type="application/ld+json">` blocks and Microdata attributes are extracted from the raw HTML before any script or style removal. Properties such as article name, description, keywords, datePublished, and author are serialized as YAML front-matter prepended to the final Markdown document. Harvesting prior to cleaning ensures that metadata embedded inside `<script>` tags is not discarded with other executable content.

The third stage performs **deterministic structural cleaning** and optional STCE application: removal of `<script>`, `<style>`, `<noscript>`, and inline SVG blobs; whitespace normalization; and—when a chrome model file is supplied—application of the Site-Template Chrome Elimination model. The STCE model is a JSON artefact produced by `chromerag learn` from a multi-page sample of the same site. It encodes recurring structural patterns (CSS selector paths, text-density profiles, and positional heuristics) that identify navigation and footer fragments, pruning them before the Markdown converter runs.

The fourth stage optionally applies **DVDF** (Semantic Vector Density Filtering): an ONNX-hosted MiniLM sentence encoder computes cosine distances between each leaf text node and heuristic noise-anchor phrases (marketing/boilerplate templates). Leaf nodes below the noise threshold are dropped. DVDF is installed with the `[dvdf]` extras group and is skipped gracefully when ONNX Runtime is absent, keeping it an opt-in enhancement rather than a required dependency.

The final stage converts the cleaned DOM to **heading-safe Markdown** with fenced code blocks and table rendering. Tables are optionally linearized into key-value pairs for RAG embedding. The scope boundary is explicit: ChromeRAG owns HTML→Markdown. Fetching, Playwright rendering, crawl concurrency, and rate limiting belong to the caller or to the `poc/` evaluation harness provided in the repository.

```
HTML string
  → input-quality check (warn on thin / JS shells)
  → schema harvest (JSON-LD / Microdata) BEFORE script strip
  → deterministic clean + optional STCE (learned site chrome)
  → density / DVDF leaf prune (optional ONNX MiniLM)
  → heading-safe Markdown + YAML front-matter
  → optional table key-value linearization
```

### Software functionalities

The core public API is the `ChromeRAG` class. A `PipelineConfig` (or `PipelineConfig.from_priority(...)`) sets priority mode and DVDF/schema/table toggles; an optional `SiteChromeModel` is passed separately as `ChromeRAG(..., site_chrome=model)` after `chromerag learn`. `PipelineConfig.from_priority(ContentPriority.COVERAGE)` selects the parameter preset optimized for content recall; `ContentPriority.PRECISION` tightens chrome thresholds at the cost of some recall; `ContentPriority.BALANCED` is the default enterprise compromise. The `.extract(html, url=...)` method returns a typed `ExtractResult` with fields including `markdown`, `front_matter`, `warnings`, `diagnostics`, and `input_quality`. The URL argument is used for relative link resolution and logging metadata, not for network access.

The CLI exposes three subcommands. `chromerag extract` processes a single HTML file. `chromerag learn` builds an STCE chrome model from a directory of HTML pages. `chromerag batch` processes a directory of raw HTML files with a shared chrome model and writes a summary JSON flagging thin pages. The static Compare Lab under `docs/` is a pre-built, zero-dependency site served via GitHub Pages at `https://pedapudibhargav.github.io/ChromeRAG/`, where users can inspect side-by-side extraction results across tools and page categories without running any code locally.

| Feature | CLI / API | Notes |
|---------|-----------|-------|
| Extract | `chromerag extract page.html -o out.md` | `--priority {precision,coverage,balanced}` |
| Input warnings | stderr + `result.warnings` | JS shell / thin HTML detection |
| Learn chrome | `chromerag learn data/raw -o site.json` | STCE model from multi-page corpus |
| Batch | `chromerag batch data/raw -o data/outputs --chrome-model site.json` | Flags thin pages in summary |
| DVDF | optional `[dvdf]` extras | ONNX MiniLM noise-anchor cosine prune |
| Compare Lab | `docs/` static site | GitHub Pages–safe relative routing |

### Sample usage

A typical enterprise RAG ingest workflow proceeds in three steps. First, the operator collects a representative sample of pages from the target domain (three pages minimum) and runs `chromerag learn` to build a site chrome model. Second, `chromerag batch` processes the full crawl output using that model, writing Markdown files and flagging thin pages in the summary JSON. Third, thin-flagged pages are routed to a Playwright rendering step and re-processed.

```bash
pip install -e ".[dvdf,baselines]"
chromerag learn data/raw -o data/chrome_models/site.json --min-pages 3
chromerag batch data/raw -o data/outputs \
    --chrome-model data/chrome_models/site.json --priority coverage
python -m poc.run_corpus_comparison --no-fetch
```

Python API usage for single-page extraction with warning inspection:

```python
from chromerag import ChromeRAG, PipelineConfig, ContentPriority

result = ChromeRAG(
    config=PipelineConfig.from_priority(ContentPriority.BALANCED)
).extract(html, url="https://example.com/docs/api-reference")

md, meta = result.markdown, result.front_matter
for warning in result.warnings:
    print("WARNING:", warning)  # e.g. "Input HTML looks like a JavaScript-rendered shell..."
```

Full installation instructions, configuration reference, and step-by-step reproducibility instructions for the benchmark are maintained in the repository `README.md` and on the GitHub Pages documentation site [4], keeping this paper body focused on method and evaluation.

---

## Illustrative examples

### Corpus comparison

The benchmark corpus listed **373** publicly accessible URLs spanning eight intended page categories (docs, pricing, marketing, wiki, hub, news, article, cloud). After a single-pass fetch using the `poc/` harness (HTTP only; no Playwright rendering), **277 pages** returned non-error responses. Fetched pages were dominated by documentation and article-like HTML; **wiki** and **news** URLs in the listed set did not yield successful fetches in this run. Of the 277 fetched pages, **238** were marked *scoreable* and **39** *thin*.

Content and chrome anchors are defined from the DOM (5-grams from `<main>`/`<article>` vs `<nav>`/`<footer>`/`<header>`). A fetched page enters the **scoreable** cohort used for leaderboard *means* when ChromeRAG content recall against those DOM content anchors is ≥ 0.05. This is a disclosed **corpus hygiene filter**: near-empty or weakly landmark-ed DOMs make recall/noise undefined or near-zero for every tool and would collapse means without clarifying chrome-removal differences. The same fixed cohort is then used for **all** tools (ChromeRAG, Trafilatura, MarkItDown, Readability)—ChromeRAG does not receive a different evaluation set than baselines. The 39 thin pages include approximately 7 JS-shell-like inputs, 1 other thin DOM, and 31 pages with visible text that still fail the recall gate (unusual layouts or weak `<main>` landmarks). Listed / fetched / scoreable / thin counts are shown in Figure 4 and in `docs/data/corpus_comparison_summary.md`.

On the 238 scoreable pages:

| Method | Recall ↑ | Noise ret. ↓ | F_bal ↑ |
|--------|--------:|-------------:|--------:|
| chromerag_coverage | 0.701 | 0.005 | **0.800** |
| chromerag (balanced) | 0.678 | 0.005 | 0.783 |
| trafilatura [1] | 0.662 | 0.019 | 0.752 |
| markitdown [5] | 0.702 | 0.261 | 0.695 |
| readability [6] | 0.456 | 0.016 | 0.535 |

ChromeRAG's F_bal advantage over MarkItDown (0.800 vs 0.695) derives almost entirely from chrome noise reduction (0.005 vs 0.261) at comparable recall. The gap over Trafilatura (0.800 vs 0.752) reflects incremental recall gains from the STCE model on documentation pages where content and navigation share similar text density—precisely the case where density-only heuristics struggle. Readability's low recall (0.456) reflects its article-centric filter discarding multi-section reference pages and tables.

**Figure 1** — Bar chart of F_bal scores for all five methods across 238 scoreable pages. ChromeRAG coverage and balanced modes lead; MarkItDown's chrome retention penalty is visible despite near-equal recall.

**Figure 2** — Content recall per method. ChromeRAG coverage (0.701) and MarkItDown (0.702) are comparable; Readability (0.456) trails substantially on non-article page types.

**Figure 3** — Noise retention on a log-scale y-axis. ChromeRAG ≈ 0.005 versus MarkItDown ≈ 0.261; the ~50× gap illustrates why high recall alone is insufficient for RAG quality.

**Figure 4** — Corpus honesty funnel: 373 listed → 277 fetched → 238 scoreable / 39 thin. The funnel communicates that leaderboard numbers apply to a bounded, filter-described subset of the original URL list.

### Priority knobs and input-quality warnings

The `--priority` flag maps to three parameter presets. **Precision** mode applies tighter chrome thresholds, accepting lower recall in exchange for minimal noise; it suits corpora where chrome pollution carries a direct cost (e.g., product-specification extractors that must not return marketing boilerplate). **Coverage** mode relaxes thresholds to favour recall, accepting marginally more borderline content; this is appropriate for question-answering corpora where a missed factual sentence is more costly than a stray navigation link. **Balanced** mode is the default and the recommended starting point for general enterprise RAG.

When a page is suspected to be an unrendered JavaScript shell—identified by low visible text, script-heavy HTML, SPA root markers such as `id="root"` / `id="app"` / `__next`, or noscript “enable JavaScript” hints—ChromeRAG emits a structured warning in `result.warnings` and on stderr (for example: “Input HTML looks like a JavaScript-rendered shell … Render the page first (Playwright / Puppeteer / your crawler) …”). This fires regardless of priority mode. The `--fail-on-thin` CLI flag converts warnings to non-zero exit codes, enabling automated pipeline health checks: operators who observe a high thin-page rate in batch output can treat it as a signal that the upstream fetcher is not rendering JavaScript, and route those pages through a headless browser before re-running `chromerag batch`.

---

## Impact

### Intended users and pathways

ChromeRAG is aimed primarily at **software engineers and data engineers** building RAG corpora from corporate or public web sources. The design was validated against public documentation and pricing HTML and exercised in production-style enterprise documentation ingest workflows. Four concrete deployment pathways follow.

**Custom loaders in orchestration frameworks.** LangChain and LlamaIndex both expose pluggable document loader interfaces. ChromeRAG can be wrapped as a custom `Document` loader that accepts raw HTML from any fetch library and returns a `Document` with `page_content` set to extracted Markdown and `metadata` populated from YAML front-matter. This integration requires no changes to the retrieval or generation layers; chrome removal is transparent to the rest of the pipeline.

**Batch ingest jobs in data platforms.** In Airflow, Prefect, or Spark-based pipelines, `chromerag batch` can run as a processing operator downstream of a crawl step. The batch summary JSON allows downstream tasks to branch: scoreable pages proceed to chunking and embedding; thin-flagged pages trigger a re-crawl with Playwright rendering. This explicit quality signal is absent from converters that silently produce near-empty Markdown for unrendered JS shells and emit no diagnostic output.

**Benchmark and research baselines.** The corpus comparison benchmark—reproducible via `python -m poc.run_corpus_comparison --no-fetch`—provides a reusable Recall / Noise / F_bal evaluation harness for HTML extraction quality. Researchers developing new extraction methods can register an additional tool in the comparison module, run the benchmark against the same 238-page scoreable corpus, and report directly comparable numbers. The static Compare Lab (`docs/`) provides visual side-by-side verification for qualitative analysis and is deployable on any static host without server-side code.

**Education and demonstrators.** The Compare Lab serves as a live demonstrator for teaching RAG data quality concepts. Instructors can direct learners to the hosted GitHub Pages site without requiring local Python installation. The explicit corpus funnel (Figure 4) and per-category breakdown reinforce that reported metrics are bounded and reproducible, rather than cherry-picked from a hidden evaluation set.

The software's **direct commercial relevance** lies in reducing the engineering effort and compute cost of building and maintaining RAG corpora. Organizations that currently post-process extracted text with ad-hoc regular expressions or manual curation of navigation and footer blocks may find that a domain-adaptive STCE model offers comparable or superior chrome removal with lower maintenance overhead. Because STCE runs on CPU and requires no GPU or cloud API call, it is compatible with air-gapped deployment environments common in regulated industries.

### Limitations

Several limitations are stated explicitly so that reviewers and practitioners can calibrate expectations.

**JavaScript-rendered pages.** ChromeRAG does not execute JavaScript. Pages that ship an empty HTML skeleton and populate content in the browser produce thin or empty Markdown, and the software warns the caller explicitly rather than returning a silent low-quality result. This is a deliberate scope constraint: fetch orchestration and headless rendering belong to the caller's infrastructure layer. Callers that require rendered content should use Playwright or Puppeteer before passing HTML to ChromeRAG.

**Heuristic content anchors, not human labels.** Benchmark anchors are derived from structural HTML semantics (`<main>`, `<article>` vs. `<nav>`, `<footer>`) rather than hand-labeled text spans. This approach scales to hundreds of pages without annotation cost and keeps the evaluation tool-agnostic, but it is an approximation. Pages with poor semantic markup—where body prose is placed in unlabelled `<div>` elements—may yield misleading anchor sets. Per-category score breakdowns in `docs/data/` allow users to inspect where anchor quality may be weaker.

**Scoreable-page filter scope.** The 39 thin pages excluded from benchmark averages include some pages with visible text that nonetheless fail the recall gate due to unusual layouts. Reported F_bal numbers apply to the 238-page scoreable subset; users should consult the full listed/fetched/scoreable/thin counts (Figure 4) to understand benchmark coverage.

**DVDF optional dependency.** Vector density filtering requires ONNX Runtime and the MiniLM model weights (approximately 90 MB). The default installation omits this; users must opt in via `pip install -e ".[dvdf]"`. Air-gapped or proxy-restricted environments may need to supply model weights manually.

**Single-format scope.** ChromeRAG converts web HTML to Markdown only and does not handle PDF, Office documents, audio, or structured data formats. Users with mixed-format corpora will need additional converters—such as MarkItDown [5]—for non-HTML sources.

---

## Conclusions

ChromeRAG packages ingest-time site-chrome elimination, optional vector density pruning, Schema.org front-matter extraction, table linearization, and explicit input-quality warnings into an MIT-licensed Python CLI and API (`pip install chromerag`). On 238 scoreable pages from the fetched public corpus (docs-, article-, pricing-, marketing-, hub-, and cloud-dominated; wiki/news listed URLs did not fetch in this run), coverage mode achieves F_bal 0.800 against Trafilatura 0.752 and MarkItDown 0.695, primarily by reducing chrome noise retention to 0.005 from MarkItDown's 0.261 at comparable recall. The explicit thin-page warning mechanism ensures pipeline operators are informed of JS-shell inputs rather than silently absorbing empty pages into quality averages. Future work includes page-type adaptive extraction profiles and a Chrome Centroid Drift metric for monitoring corpus quality over time.

---

## CRediT author contribution statement

**Bhargava Chary Peddapudi:** Conceptualization, Software, Methodology, Validation, Writing — original draft, Writing — review & editing.

---

## Declaration of competing interest

The author declares that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper.

---

## Funding

This research did not receive any specific grant from funding agencies in the public, commercial, or not-for-profit sectors.

---

## Declaration of generative AI and AI-assisted technologies in the manuscript preparation process

During the preparation of this work, the author used Cursor (with Grok-assisted coding agent support) to draft software documentation structure, organize related-work notes, and polish manuscript wording. After using this tool/service, the author reviewed and edited the content as needed and takes full responsibility for the content of the published article. AI tools used inside the research software (optional ONNX MiniLM for DVDF) are described in the Software description section and are software features, not manuscript-writing tools. No generative AI was used to create SoftwareX figures; all charts are produced from corpus JSON via `scripts/generate_softwarex_figures.py`.

---

## References

1. A. Barbaresi, "Trafilatura: A Web Scraping Library and Command-Line Tool for Text Discovery and Extraction," in *Proc. ACL-IJCNLP 2021 System Demonstrations*, 2021, pp. 122–131. doi: [10.18653/v1/2021.acl-demo.15](https://doi.org/10.18653/v1/2021.acl-demo.15).
2. J. Alarte, J. Silva, and S. Tamarit, "What Web Template Extractor Should I Use? A Benchmarking and Comparison for Five Template Extractors," *ACM Trans. Web*, vol. 13, no. 2, Art. 9, 2019. doi: [10.1145/3316810](https://doi.org/10.1145/3316810).
3. J. Tan, Z. Dou, W. Wang, M. Wang, W. Chen, and J.-R. Wen, "HtmlRAG: HTML is Better Than Plain Text for Modeling Retrieved Knowledge in RAG Systems," in *Proc. ACM Web Conf. (WWW '25)*, 2025. doi: [10.1145/3696410.3714546](https://doi.org/10.1145/3696410.3714546).
4. B. C. Peddapudi, *ChromeRAG*, version 0.1.0, GitHub, 2026. [Online]. Available: https://github.com/pedapudibhargav/ChromeRAG/tree/v0.1.0
5. Microsoft, *MarkItDown*: Python tool for converting files and office documents to Markdown, GitHub. [Online]. Available: https://github.com/microsoft/markitdown
6. Mozilla Foundation / Arc90, *Readability* (readability-lxml Python binding). [Online]. Available: https://github.com/buriy/python-readability

---

## Word count estimate

| Section | Approx. words |
|---------|-------------:|
| Abstract | ~130 |
| Motivation and significance | ~620 |
| Software description | ~840 |
| Illustrative examples | ~550 |
| Impact | ~600 |
| Conclusions | ~110 |
| Figure captions (inline) | ~90 |
| **Total (abstract + body + captions)** | **~2,940** |

*Declarations and references are excluded from the SoftwareX body word count per journal convention.*
