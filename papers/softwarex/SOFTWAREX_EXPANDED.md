# ChromeRAG: Ingest-Time Elimination of Site Template Noise for Enterprise Web RAG

**Target journal:** Elsevier *SoftwareX* (Original Software Publication)  
**Package:** `chromerag` (v0.1.1)  
**Draft status:** Source text for `scripts/fill_softwarex_docx.py`, which fills the official SoftwareX OSP Word template (v6, March 2026). Do not submit this Markdown file as-is.

**Authors:** Bhargava Chary Peddapudi (Independent Researcher; ORCID: https://orcid.org/0009-0002-8523-8415)  
**Corresponding email:** pedapudibhargav@gmail.com

---

## Abstract

Web pages indexed for retrieval-augmented generation (RAG) carry navigation menus, cookie banners, calls to action and footers that end up as noisy chunks in the vector store. ChromeRAG is an MIT-licensed, CPU-only Python package and command-line tool that converts HTML into RAG-ready Markdown. It removes this site-template "chrome", optionally learns a site's repeated chrome from a few sample pages, turns Schema.org metadata into YAML front-matter, linearizes tables, and warns when the input is an unrendered JavaScript shell. On 250 public pages, ChromeRAG reached a balanced F-score of 0.791, compared with 0.740 for Trafilatura and 0.694 for MarkItDown. The benchmark harness is included for reproduction.

**Keywords:** retrieval-augmented generation; HTML extraction; boilerplate removal; web template detection; Markdown; Python

---

## Motivation and significance

**Chrome pollutes RAG indexes.** Retrieval-augmented generation grounds a language model in retrieved passages [1]. In organizations those passages usually come from documentation portals, API references, pricing pages and knowledge bases, and that HTML was never written for machines to read. Each page mixes its own content with site-wide "chrome": top navigation, sidebar link trees, cookie-consent banners, sales calls to action and legal footers. If this HTML is converted naively and embedded, the same chrome text appears in every page's chunks. At query time these near-duplicate chunks compete with real content, show up as false positives, and use up the model's context window. The cost grows with corpus size. A 10,000-page portal with a 200-token footer adds two million tokens of identical text to the index.

**Related work and the gap.** Boilerplate removal is an established problem. Shallow text features [2] and neural sequence labelling [3] classify blocks within a single page. Trafilatura [4] and Readability [5] are widely used main-content extractors tuned for articles, and a recent large-scale comparison [7] found that no single algorithm is best on every page type. Format converters such as MarkItDown [6] keep headings, tables and code blocks, but they do not try to remove chrome. Using several pages from the same site was proposed early on [8, 9]: blocks that repeat across a site's pages are likely to be template rather than content. Alarte et al. [10] benchmarked such template extractors. Query-time methods such as HtmlRAG [11] prune HTML after retrieval, so they complement ingest-time cleaning and do not replace it. What practitioners lack is a small, installable component at the ingest step of a RAG pipeline that combines four things: single-page chrome removal, an optional learned model of a site's repeated template, structured metadata and tables in a form suited to chunking, and explicit signals when the input HTML is unusable.

**What ChromeRAG provides.** ChromeRAG fills that gap with (i) *site-template chrome elimination* (STCE), a learn-then-extract model built from pages of the same site; (ii) Schema.org JSON-LD and Microdata harvested into YAML front-matter, so every chunk can carry typed metadata; (iii) linearization of tables into key–value rows that survive chunking; and (iv) input-quality warnings that separate legitimately short pages from JavaScript shells that must be rendered first. The package is query-agnostic and independent of any retriever or model. It runs on CPU without downloading a model, so it also works in air-gapped environments.

**How it is used.** A crawler or headless browser stores HTML files. ChromeRAG converts each file, or a whole directory, into Markdown for chunking and embedding. When several pages from one site are available, `chromerag learn` builds a site chrome model first.

---

## Software description

### Software architecture

ChromeRAG is a small, dependency-light Python package (`src/chromerag`, about 2,200 lines) built on BeautifulSoup/lxml. Each document passes through five stages (Fig. 1). Each stage is a separate module with its own unit tests.

<!-- FIG 1 -->

*Stage 1: input-quality gate* (`input_quality.py`). The raw HTML is measured for visible text, script weight, single-page-application root markers (`id="root"`, `id="app"`, `__next`) and `<noscript>` "enable JavaScript" hints. Inputs that look thin produce `WARNING:` lines on stderr and entries in `result.warnings`. The gate runs on the document as received, before anything is removed.

*Stage 2: schema harvest* (`schema_fusion.py`). JSON-LD blocks and Microdata are read before scripts are removed. Fields such as title, type, description, dates, author and breadcrumb become YAML front-matter.

*Stage 3: cleaning and STCE* (`site_chrome.py`). Scripts, styles, forms and SVG are removed. If a site model is supplied, blocks whose signature is in the model are removed. A signature is a hash of the block's tag, id, classes and ARIA role, or of its text when the block has no attributes. `chromerag learn` groups pages by host and first path segment. A signature enters the model only when it appears on at least a set share of the group's pages (default 80%) *and* looks like chrome: chrome-related class tokens or phrases, or high link density. Long blocks are never removed this way. Frequency alone is not enough, so shared content blocks are kept.

*Stage 4: structural and density pruning* (`density.py`, `dvdf.py`). Landmark and class heuristics remove `nav`, `footer`, cookie, newsletter and similar subtrees. A guard stops a subtree from being removed if it contains `<main>` or holds most of the page's visible text. Candidate blocks are then scored by link density and text density. DVDF (density/vector filtering) embeds each block as a deterministic 384-dimensional feature-hashing vector [12] and drops blocks whose cosine similarity to a bank of boilerplate anchor phrases passes a threshold. Because the embedding is lexical, it catches near-verbatim boilerplate, not paraphrases, and needs no model download.

*Stage 5: tables and Markdown* (`tables.py`, `markdown_out.py`). Tables become `Row n -> header: value | …` lines. The remaining DOM is written as Markdown with safe heading levels and fenced code.

Scope is deliberately narrow: ChromeRAG takes HTML in and returns Markdown. It does not fetch pages, render JavaScript or crawl sites. Those jobs belong to the caller, or to the separate evaluation harness in `poc/`, which is not needed at runtime.

### Software functionalities

The Python API centres on `ChromeRAG(config=…, site_chrome=…)`. `PipelineConfig.from_priority()` selects one of three presets. `COVERAGE` loosens thresholds to keep more content, `PRECISION` tightens them to remove more chrome, and `BALANCED` is the default. Each stage can be switched off on its own (`--no-dvdf`, `--no-schema`, `--no-tables`, `--no-stce`). `extract(html, url=None)` returns a typed `ExtractResult` with `markdown`, `front_matter`, `warnings`, `input_quality`, a token estimate, and `diagnostics` (samples of kept and rejected blocks with the reason for each decision). The URL is used only as metadata (page-type hints, site grouping and the `url` front-matter field), never to access the network.

The CLI has three subcommands (Table 1).

Table 1. ChromeRAG command-line interface.

| Task | Command | Output |
|---|---|---|
| One page | chromerag extract page.html -o page.md --priority coverage | Markdown; --json-meta prints diagnostics; --fail-on-thin exits with code 3 |
| Learn site chrome | chromerag learn pages/ -o site.json --min-pages 3 | JSON site model grouped by host and path prefix |
| Batch | chromerag batch pages/ -o out/ --chrome-model site.json | One Markdown file per page and batch_summary.json flagging thin/JS-shell pages |

The package needs Python 3.11 or later and installs with `pip install chromerag` [14]. The repository adds unit tests (`pytest`), the benchmark harness, and a static GitHub Pages site with the leaderboard and per-page outputs.

---

## Illustrative examples

### Learning a site template

The repository includes four small synthetic pages from a fictional documentation site (`examples/site/`). They share a header menu, cookie banner, sales call-to-action, footer and a repeated "Widget Summit: register now" strip inside `<main>`. Stage 4 removes the menu, banner and footer because of their markup. The in-content strip has no chrome-like markup, so it survives single-page extraction. It is removed only after learning:

```bash
pip install chromerag
chromerag learn examples/site -o out/site.json --min-pages 3
chromerag batch examples/site -o out/batch --chrome-model out/site.json
```

`learn` reports one site group (`docs.example.com/docs`) with six chrome signatures. `batch` applies them to all four pages. The resulting `pricing` page keeps its JSON-LD as front-matter and its table as key–value rows:

```text
---
url: https://docs.example.com/docs/pricing
title: Plans and pricing
type: TechArticle
description: Compare Widget plans.
lastUpdated: '2026-01-15'
---
# Plans and pricing
Every plan includes unlimited local runs. ...
Row 2 -> Plan: Team | Hosted minutes: 20,000 | Monthly price (USD): 49
```

A JavaScript shell (`<div id="root"></div>` plus a script tag) instead produces a warning telling the caller to render the page with Playwright or Puppeteer first. With `--fail-on-thin`, the command exits with code 3, so pipelines can route such pages to a headless browser.

### Public benchmark

The harness (`poc/run_corpus_comparison.py`) compares ChromeRAG's three presets with Trafilatura [4], Readability [5], MarkItDown [6], markdownify, html2text and BeautifulSoup text extraction. All tools run on the same stored HTML. No tool receives a site model, so the benchmark measures single-page extraction without STCE. The corpus lists 373 public URLs (documentation, pricing, marketing, cloud, article and hub pages). A plain HTTP fetch without JavaScript rendering returned 277 pages.

The metrics use structural anchors taken from each input DOM: word 5-grams from `<main>`/`<article>` text (content) and from `<nav>`, `<header>`, `<footer>`, `<aside>` and cookie/newsletter containers (noise). 5-grams found in both sets are discarded. *Recall* is the share of content anchors that appear in a tool's output. *Noise retention* is the share of noise anchors that appear. *F_bal* is the harmonic mean of recall and (1 − noise retention). A page counts as *scoreable* when its input DOM has at least 50 content anchors. This rule looks only at the input and never at any tool's output. It keeps 250 pages and excludes 27: 7 JavaScript shells, 1 other thin page, and 19 pages with too little landmarked text to score (Fig. 5).

Table 2. Mean scores per method on the 250 scoreable pages, with F_bal over all 277 fetched pages for comparison.

| Method | Recall ↑ | Noise ret. ↓ | F_bal ↑ (250 scoreable) | F_bal ↑ (all 277) |
|---|---|---|---|---|
| ChromeRAG coverage | 0.691 | 0.007 | 0.791 | 0.752 |
| ChromeRAG balanced | 0.667 | 0.006 | 0.774 | 0.736 |
| Trafilatura [4] | 0.640 | 0.012 | 0.740 | 0.698 |
| MarkItDown [6] | 0.692 | 0.253 | 0.694 | 0.661 |
| Readability [5] | 0.450 | 0.013 | 0.531 | 0.499 |

<!-- FIG 2 -->
<!-- FIG 3 -->
<!-- FIG 4 -->
<!-- FIG 5 -->

Table 2 and Figs. 2–4 show two different trade-offs. Against MarkItDown, ChromeRAG keeps the same amount of content: the paired bootstrap difference in recall is −0.001, with a 95% CI of [−0.023, 0.020]. It keeps far less chrome (difference in noise retention −0.246, CI [−0.269, −0.222]), and its median output is 825 tokens against 3,505 for MarkItDown. Against Trafilatura, noise retention does not differ significantly (−0.005, CI [−0.014, 0.004]). ChromeRAG's higher F_bal (+0.051, CI [+0.025, +0.081]) comes from recall. Page by page, the two tools win about equally often (106 against 111 pages, with 33 ties). The difference in means comes from failures: Trafilatura keeps less than 20% of the content on 26 pages, against 13 for ChromeRAG, mostly multi-section documentation and marketing pages. Per-page outputs, per-category tables and the all-page means are published with the code, so readers can check individual cases.

---

## Impact

**Improving an existing workflow.** Chunking and embedding scraped HTML is now a routine data-engineering task, and chrome removal is often done with ad hoc regular expressions written for each site. ChromeRAG replaces those with one tested step whose behaviour is documented. It works on CPU without network access, and it reports what it removed and why (`diagnostics`). Two properties matter most for RAG corpora. Across a whole site, the learned model can remove template blocks that look like content on any single page. On single pages, output stays about four times shorter than a structure-preserving converter while keeping the same content, which reduces embedding cost and context-window use.

**Integration pathways.** ChromeRAG can be wrapped as a document loader in LangChain or LlamaIndex. It takes raw HTML and returns Markdown plus front-matter metadata. `chromerag batch` fits into Airflow or Prefect jobs after a crawl step. Its `batch_summary.json` lets later tasks send thin or JavaScript-shell pages to a headless browser instead of indexing empty text without notice. The typed front-matter (title, type, dates, breadcrumb) can be copied onto every chunk for filtering and citation.

**New research questions.** The repository includes a reproducible, tool-agnostic evaluation harness for web content extraction aimed at RAG, not news archiving. Researchers can register another extractor in `poc/baselines.py` and score it on the same pages and anchors. They can also use it to study questions the paper does not answer: how much ingest-time chrome removal changes end-to-end retrieval and answer quality, how site-level template models age as sites are redesigned, and whether semantic encoders improve on the lexical DVDF filter.

**Adoption.** ChromeRAG was first released on PyPI and GitHub in September 2026, so download, citation and third-party usage figures are not yet meaningful. The public issue tracker and the live leaderboard at https://pedapudibhargav.github.io/ChromeRAG/ are the channels for outside feedback.

**Limitations.** (i) ChromeRAG does not run JavaScript. It warns about shell pages but cannot recover their content. (ii) The metrics use structural anchors, not human-labelled spans. Pages without landmarks are under-represented, and extractors that also use landmarks may have an advantage. For this reason, all per-page outputs are published. (iii) DVDF compares lexical hashed vectors, not semantic embeddings. (iv) STCE needs at least three pages from the same site group and is not part of the public benchmark numbers. (v) Only HTML is handled. PDF and Office formats need other converters such as MarkItDown.

---

## Conclusions

ChromeRAG is a focused, installable component for the ingest step of web RAG pipelines. It converts HTML into Markdown without site chrome, can learn a site's repeated template, carries Schema.org metadata and tables into chunk-friendly form, and reports unusable inputs instead of hiding them. On a public benchmark of 250 pages, with a cohort chosen from the input alone, ChromeRAG matches MarkItDown's content recall while keeping about 35 times less chrome. It is ahead of Trafilatura on F_bal, mainly because it has fewer catastrophic content losses. The code, tests, benchmark harness and per-page results are openly available. Planned work covers page-type-specific presets, an optional sentence-encoder backend for DVDF [13], and end-to-end retrieval evaluation.

---

## CRediT author contribution statement

**Bhargava Chary Peddapudi:** Conceptualization, Methodology, Software, Validation, Formal analysis, Data curation, Visualization, Writing — original draft, Writing — review & editing.

---

## Declaration of competing interest

The author declares that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper.

---

## Funding

This research did not receive any specific grant from funding agencies in the public, commercial, or not-for-profit sectors.

---

## Data availability

The software, the list of benchmark URLs (`poc/corpus_urls.json`), the evaluation harness, per-page scores and aggregate results (`docs/data/`) are openly available at https://github.com/pedapudibhargav/ChromeRAG under the MIT license. The raw third-party HTML pages are not redistributed. They can be fetched again with `python -m poc.run_corpus_comparison`, although live pages change over time.

---

## Declaration of generative AI and AI-assisted technologies in the manuscript preparation process

During the preparation of this work the author used Cursor (with a Grok-based coding agent) and Anthropic Claude (Claude Code) in order to assist with software development, code review, drafting and editing of the manuscript text, and verification of reported numbers against the benchmark outputs. After using these tools, the author reviewed and edited the content as needed and takes full responsibility for the content of the published article.

---

## References

1. P. Lewis, E. Perez, A. Piktus, F. Petroni, V. Karpukhin, N. Goyal, H. Küttler, M. Lewis, W. Yih, T. Rocktäschel, S. Riedel, and D. Kiela, "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," in *Advances in Neural Information Processing Systems 33 (NeurIPS 2020)*, 2020, pp. 9459–9474. arXiv: 2005.11401.
2. C. Kohlschütter, P. Fankhauser, and W. Nejdl, "Boilerplate Detection Using Shallow Text Features," in *Proc. 3rd ACM Int. Conf. Web Search and Data Mining (WSDM)*, 2010, pp. 441–450. doi: 10.1145/1718487.1718542.
3. T. Vogels, O.-E. Ganea, and C. Eickhoff, "Web2Text: Deep Structured Boilerplate Removal," in *Advances in Information Retrieval (ECIR 2018)*, LNCS, 2018, pp. 167–179. doi: 10.1007/978-3-319-76941-7_13.
4. A. Barbaresi, "Trafilatura: A Web Scraping Library and Command-Line Tool for Text Discovery and Extraction," in *Proc. ACL-IJCNLP 2021: System Demonstrations*, 2021, pp. 122–131. doi: 10.18653/v1/2021.acl-demo.15.
5. Y. Baburov et al., *python-readability* (readability-lxml), Python port of Arc90 Readability, GitHub. [Online]. Available: https://github.com/buriy/python-readability
6. Microsoft, *MarkItDown*: Python tool for converting files and office documents to Markdown, GitHub. [Online]. Available: https://github.com/microsoft/markitdown
7. J. Bevendorff, S. Gupta, J. Kiesel, and B. Stein, "An Empirical Comparison of Web Content Extraction Algorithms," in *Proc. 46th Int. ACM SIGIR Conf.*, 2023, pp. 2594–2603. doi: 10.1145/3539618.3591920.
8. Z. Bar-Yossef and S. Rajagopalan, "Template Detection via Data Mining and its Applications," in *Proc. 11th Int. World Wide Web Conf. (WWW)*, 2002, pp. 580–591. doi: 10.1145/511446.511522.
9. L. Yi, B. Liu, and X. Li, "Eliminating Noisy Information in Web Pages for Data Mining," in *Proc. 9th ACM SIGKDD Int. Conf. Knowledge Discovery and Data Mining*, 2003, pp. 296–305. doi: 10.1145/956750.956785.
10. J. Alarte, J. Silva, and S. Tamarit, "What Web Template Extractor Should I Use? A Benchmarking and Comparison for Five Template Extractors," *ACM Trans. Web*, vol. 13, no. 2, pp. 1–19, 2019. doi: 10.1145/3316810.
11. J. Tan, Z. Dou, W. Wang, M. Wang, W. Chen, and J.-R. Wen, "HtmlRAG: HTML is Better Than Plain Text for Modeling Retrieved Knowledge in RAG Systems," in *Proc. ACM Web Conf. 2025 (WWW '25)*, 2025, pp. 1733–1746. doi: 10.1145/3696410.3714546.
12. K. Weinberger, A. Dasgupta, J. Langford, A. Smola, and J. Attenberg, "Feature Hashing for Large Scale Multitask Learning," in *Proc. 26th Int. Conf. Machine Learning (ICML)*, 2009, pp. 1113–1120. doi: 10.1145/1553374.1553516.
13. N. Reimers and I. Gurevych, "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks," in *Proc. EMNLP-IJCNLP 2019*, 2019, pp. 3980–3990. doi: 10.18653/v1/D19-1410.
14. B. C. Peddapudi, *ChromeRAG*, version 0.1.1, GitHub, 2026. [Online]. Available: https://github.com/pedapudibhargav/ChromeRAG/tree/v0.1.1

---
