# ChromeRAG: A Learned Boilerplate Filter and Site-Template Learner for Web RAG Ingestion

**Target journal:** Elsevier *SoftwareX* (Original Software Publication)  
**Package:** `chromerag` (v0.1.3)  
**Draft status:** Source text for `scripts/fill_softwarex_docx.py`, which fills the official SoftwareX OSP Word template (v6, March 2026). Do not submit this Markdown file as-is.

**Authors:** Bhargava Chary Peddapudi (Independent Researcher; ORCID: https://orcid.org/0009-0002-8523-8415)  
**Corresponding email:** pedapudibhargav@gmail.com

---

## Abstract

Web pages indexed for retrieval-augmented generation (RAG) carry navigation, cookie banners, related links and comments that become noisy chunks. ChromeRAG is an MIT-licensed, CPU-only Python package and command-line tool that converts HTML into RAG-ready Markdown. A 150 KB gradient-boosted model, evaluated with NumPy, scores each text block; an optional site model removes repeated templates; metadata becomes front-matter, tables become key-value rows, and JavaScript shells are flagged. On the 511 held-out WCXB pages it reaches a word-level F1 of 0.902, against 0.860 for Trafilatura and 0.540 for MarkItDown.

**Keywords:** retrieval-augmented generation; HTML extraction; boilerplate removal; main content extraction; Markdown; Python

---

## Motivation and significance

**Chrome pollutes RAG indexes.** Retrieval-augmented generation grounds a language model in retrieved passages [1]. In organizations those passages usually come from documentation portals, product and pricing pages and knowledge bases, and that HTML was never written for machines to read. Each page mixes its own content with site-wide "chrome": navigation, sidebar link trees, cookie-consent banners, sales calls to action, related-article lists, comment threads and legal footers. If this HTML is converted naively and embedded, the same text appears in the chunks of every page. At query time these near-duplicates compete with real content, produce false positives and use up the model's context window. The cost grows with corpus size: a 10,000-page portal with a 200-token footer adds two million tokens of identical text to the index.

**Related work and the gap.** Boilerplate removal is an established problem. Shallow text features [2] and neural sequence labelling over words and tags [3, 4] classify blocks within one page. Trafilatura [5] and Readability [6] are widely used extractors tuned for articles, and a large comparison [8] found that no algorithm is best on every page type. Format converters such as MarkItDown [7] keep headings, tables and code but do not try to remove chrome. The recent WCXB benchmark [9] makes the weakness of article-tuned tools measurable: on seven page types, systems agree on articles (F1 about 0.93) and differ by 20 to 30 points on forums, products and collections. A page-type-aware Rust extractor with a learned page classifier [10] and a language-model block labeller (MinerU-HTML, 0.6B parameters, GPU) [11] lead that benchmark. Using several pages of one site to find the template was proposed early [12, 13] and benchmarked in [14]; query-time pruning such as HtmlRAG [15] complements ingest-time cleaning. What practitioners lack is a small, installable, CPU-only component for the ingest step that combines a learned single-page filter, an optional site-template model, metadata and tables in a chunk-friendly form, and explicit signals when the input is unusable or the extraction is unsure.

**What ChromeRAG provides.** (i) A *learned block filter*: gradient-boosted trees over about 530 structural and lexical features of each text block, with a threshold per content priority; (ii) *site-template chrome elimination* (STCE), a learn-then-extract model built from pages of the same site; (iii) Schema.org JSON-LD and Microdata as YAML front-matter; (iv) tables as key-value rows; (v) input-quality warnings and a per-page confidence estimate. The package is independent of any retriever or model, needs no model download and works in air-gapped environments.

**How it is used.** A crawler or headless browser stores HTML files. ChromeRAG converts each file, or a directory, into Markdown for chunking and embedding. When several pages of one site are available, `chromerag learn` builds a site model first.

---

## Software description

### Software architecture

ChromeRAG is a small Python package (`src/chromerag`, about 4,000 lines) built on BeautifulSoup/lxml and NumPy. Each document passes through six stages (Fig. 1), each in its own module. A pytest suite of 64 tests covers the pipeline, the learned filter, the rule index, regression fixtures with exact golden outputs, the CLI, STCE and the LangChain loader; continuous integration runs on Linux (Python 3.11 to 3.14), macOS and Windows.

<!-- FIG 1 -->

*Stage 1: input-quality gate* (`input_quality.py`). The raw HTML is measured for visible text, script weight, single-page-application root markers and "enable JavaScript" hints. Thin inputs produce warnings on stderr and in `result.warnings`.

*Stage 2: schema harvest* (`schema_fusion.py`). JSON-LD and Microdata are read before scripts are removed; title, type, description, dates, author and breadcrumb become YAML front-matter.

*Stage 3: cleaning and STCE* (`site_chrome.py`, `hidden.py`, `rules_engine.py`). Scripts, styles and SVG are removed; hidden nodes and skip links are removed unless a hidden block holds long running text with few links (pages that reveal content by script). A wrapper tag such as a page-wide `<form>`, an unclosed `<button>` or a large `<noscript>` keeps its content. A YAML rule index drops known chrome (consent managers, share bars, generator footers), and every rule carries evidence and a fixture. If a site model is supplied, blocks whose signature is in the model are removed. A signature hashes the tag, id, classes and role, or the text for blocks without attributes. `chromerag learn` keeps a signature only if it appears on at least 80% of a site group's pages, stays short, repeats its leading text, and looks like chrome or is identical on every page; at extraction time a match is removed only if it is close to its learned size, holds no `<main>`, and does not hold most of the page's text.

*Stage 4: chrome pruning* (`density.py`, `content_root.py`). Landmark and class-word rules (`nav`, `footer`, cookie, newsletter, sidebar) remove subtrees, with guards: a subtree that contains `<main>`, holds most of the page's text, or holds two or more long paragraphs with few links is kept. A content-root ladder (`main`, `role=main`, `article`, content classes) is validated by size.

*Stage 5: learned block filter* (`blockfeatures.py`, `lbc.py`). The cleaned page is split into blocks: paragraphs, headings, list items, quotes, preformatted blocks, tables, text-only containers, and runs of loose text between block elements. Each block is described by about 530 numbers in five groups: its text (length, link density, punctuation, stop-word share, call-to-action verbs, dates), its place in the page (position, distance to headings, whether it is in the content root), its tree context (ancestor tags, link density and text mass of enclosing boxes, repeated sibling structures such as comment threads and card grids, overlap with the title and the page's long paragraphs), the words of its ancestors' `class` and `id`, feature-hashed [16], and the words of the heading above it. Trees (300 trees of depth 6, trained with scikit-learn) give the probability that the block is main content; the exported model is a 150 KB array file and prediction uses NumPy only. A block is kept when its probability reaches 0.30 (`coverage`), 0.50 (`balanced`) or 0.70 (`precision`). Pages with fewer than four blocks are kept whole, exact repeats are written once, and the model's own expected precision, recall and F1 for the page are stored in `diagnostics["lbc"]`; a warning is issued below an expected F1 of 0.70.

*Stage 6: tables and Markdown* (`tables.py`, `markdown_out.py`). Layout tables (nested, or cells with block content) are unwrapped; data tables become `Row n -> header: value | ...` lines. The page is written in document order with safe heading levels and fenced code; link targets are omitted unless requested (`--links`).

*Training.* `poc/lbc_data.py` labels every block of the 1,495 WCXB development pages by word-trigram overlap with the human-reviewed main content (blocks the annotators list as "without" snippets are labelled noise) and `poc/train_lbc.py` fits the trees, weighting blocks by word count. Retraining takes about two minutes. The WCXB test split is never used for training or tuning.

Scope is deliberately narrow: HTML in, Markdown out. ChromeRAG does not fetch pages, render JavaScript or crawl; those belong to the caller or to the evaluation harness in `poc/`.

### Software functionalities

The Python API centres on `ChromeRAG(config=..., site_chrome=...)`. `PipelineConfig.from_priority()` selects `COVERAGE`, `BALANCED` (default) or `PRECISION`. Stages can be switched off individually (`--no-rules`, `--no-schema`, `--no-tables`, `--no-stce`, `enable_lbc=False` for the density filter of version 0.1.2). `extract(html, url=None)` returns a typed `ExtractResult` with `markdown`, `front_matter`, `warnings`, `input_quality`, a token estimate and `diagnostics` (kept and rejected samples with reasons, the rules that fired, the model's expected F1). The URL is metadata only and is never fetched.

Table 1. ChromeRAG command-line interface.

| Task | Command | Output |
|---|---|---|
| One page | chromerag extract page.html -o page.md --priority balanced | Markdown; --json-meta prints diagnostics; --explain lists removed blocks; --fail-on-thin exits with code 3 |
| Learn site chrome | chromerag learn pages/ -o site.json --min-pages 3 | JSON site model grouped by host and path prefix |
| Batch | chromerag batch pages/ -o out/ --chrome-model site.json | One Markdown file per page and batch_summary.json flagging thin/JS-shell pages |

The package needs Python 3.11 or later and installs with `pip install chromerag` [18]. Optional LangChain and LlamaIndex components (`chromerag.integrations`) return one document per page with the front-matter as metadata. The repository adds the tests, the evaluation harness, a Docker image and a one-page GitHub Pages site with the leaderboards.

---

## Illustrative examples

### Learning a site template

The repository includes four synthetic pages from a fictional documentation site (`examples/site/`). They share a header menu, cookie banner, sales call to action, footer and a repeated "Widget Summit: register now" strip inside `<main>`. Single-page extraction removes the menu, banner and footer; the in-content strip has no chrome-like markup and survives until a site model is learned:

```bash
pip install chromerag
chromerag learn examples/site -o out/site.json --min-pages 3
chromerag batch examples/site -o out/batch --chrome-model out/site.json
```

`learn` reports one site group (`docs.example.com/docs`) with six chrome signatures; `batch` applies them to all four pages. The `pricing` page keeps its JSON-LD as front-matter and its table as key-value rows:

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

A JavaScript shell (`<div id="root"></div>` plus a script tag) produces a warning to render the page first; with `--fail-on-thin` the command exits with code 3 so pipelines can route such pages to a headless browser.

### Human-reviewed benchmark

WCXB [9] has 2,008 pages from 1,613 domains in seven page types, split into 1,497 development and 511 test pages, with human-reviewed main content. Word-level F1 compares the bag of words of an extractor's output with the reference (title excluded); "with" and "without" snippets test that required text is present and that listed chrome is absent. All tools receive the same HTML and none gets a site model. Trafilatura [5] is run with its best of five settings on the development set (tables, no comments, no links, Markdown output; 0.818 against 0.814 for the defaults, 0.789 for `favor_recall`); MarkItDown [7] and Readability [6] use their defaults.

*Development results* come from five-fold cross-validation grouped by site, so every page is scored by a model that never saw its site. F1 is 0.852 (`coverage`), 0.851 (`balanced`) and 0.837 (`precision`) against 0.818 for Trafilatura. Replacing the density filter of 0.1.2 by the learned filter raises F1 from 0.822, 0.817 and 0.790 to these values; the larger part of the gain over 0.1.2 (0.749) comes from fixing whole-page losses: wrapper tags, hidden blocks, nested layout tables that repeated text, breadth-first output order, and link targets counted as words.

*Test results* were produced once, after the code, model and thresholds were frozen (git tag `freeze-0.1.3`), by a model trained on all development pages (Table 2, Fig. 2).

Table 2. Word-level F1 on the 511 WCXB test pages (ChromeRAG in `balanced` mode).

| Page type (n) | ChromeRAG | Trafilatura | Readability | MarkItDown |
|---|---|---|---|---|
| All (511) | 0.902 | 0.860 | 0.763 | 0.540 |
| Article (257) | 0.954 | 0.952 | 0.926 | 0.643 |
| Documentation (42) | 0.956 | 0.934 | 0.872 | 0.615 |
| Service (59) | 0.844 | 0.817 | 0.612 | 0.471 |
| Forum (51) | 0.867 | 0.717 | 0.616 | 0.443 |
| Product (28) | 0.874 | 0.724 | 0.527 | 0.335 |
| Collection (34) | 0.795 | 0.626 | 0.450 | 0.284 |
| Listing (40) | 0.760 | 0.722 | 0.439 | 0.386 |

<!-- FIG 2 -->

The paired bootstrap difference to Trafilatura is +0.043 (95% CI [+0.027, +0.059]) overall, +0.150 on forums [+0.091, +0.217], +0.150 on products [+0.069, +0.243] and +0.169 on collections [+0.080, +0.264]. On articles, documentation, services and listings the intervals contain zero. The fraction of required snippets found is 0.798 against 0.720 (+0.078 [+0.051, +0.105]); the fraction of forbidden snippets found is 0.077 against 0.083 (no difference). The benchmark's publication [9] reports 0.903 for a page-type-aware Rust extractor and 0.841 for Trafilatura on the same test pages under its own configuration; we could not build that tool here, so we quote it and make no claim of superiority. The two sets of numbers use different Trafilatura settings and are not interchangeable.

Fig. 3 shows the trade-off on the development folds. ChromeRAG's curve lies above Trafilatura's single operating point for thresholds from 0.6 to 0.7 (higher precision and recall at once) and has higher F1 at every threshold up to 0.8. The model's confidence is informative: pages with an expected F1 below 0.70 (7.6% of pages) score 0.57 on average against 0.88 for the rest.

<!-- FIG 3 -->

Median time on 200 stored pages in one process is 36 ms for ChromeRAG, 30 ms for Trafilatura, 30 ms for Readability and 37 ms for MarkItDown; the 95th percentile is 108 ms against 147 ms for Trafilatura.

### Marketing and landing pages, retrieval and judged quality

The WCXB service, product and collection pages are the nearest public proxy for enterprise marketing content, but we also built a corpus of company landing pages (`poc/landing_corpus.py`): up to five pages per company chosen from the homepage's own links before any extractor was run. Companies were split by a hash into development and held-out sets, and a second list of 51 companies was fetched only after the freeze ("fresh", 178 scoreable pages). On the structural-anchor metric (recall of word 5-grams from `<main>`/`<article>`, retention of anchors from navigation, header, footer and cookie containers, balanced F), `coverage` mode reaches 0.759 on the 177 held-out pages and 0.780 on the fresh pages, against 0.680 and 0.649 for Trafilatura, 0.723 and 0.741 for MarkItDown (which keeps 22 to 26% of the chrome anchors, ChromeRAG 0.1% or less) and 0.512 and 0.567 for Readability. On 242 documentation, pricing and article pages with at least 50 content anchors, the same metric gives 0.833 for `coverage` and 0.739 for Trafilatura (+0.094, CI [+0.066, +0.123]); Trafilatura keeps under 20% of the content on 25 of these pages, ChromeRAG on 2.

BM25 retrieval with 668 known-item queries over the fresh pages (chunks of about 200 words) gives a hit@5 of 0.916 for ChromeRAG against 0.832 for Trafilatura (+0.084 [+0.045, +0.123]) and 0.949 for MarkItDown, which keeps everything (chrome in 2.3% of the retrieved context against 0.1% for ChromeRAG and 1.1% for Trafilatura). With dense embeddings (`text-embedding-3-small`) all tools but Readability tie (0.708 against 0.698 for Trafilatura; difference +0.010 [-0.024, +0.047]). On the documentation corpus, BM25 hit@5 is 0.947 against 0.921 for Trafilatura and 0.964 for MarkItDown, with 2,010 chunks against MarkItDown's 3,909.

<!-- FIG 4 -->

A blind pairwise judgement by a language model (gpt-5.6-luna; tool names hidden, output order randomised, about 83% of repeated pairs with swapped positions judged the same) was run on two samples. On 100 held-out and fresh landing pages, ChromeRAG (`coverage`) was preferred over Trafilatura on 70% of pages and over MarkItDown on 87%, against 28% and 12% (Fig. 5). On 105 WCXB test pages, 15 per page type, ChromeRAG (`balanced`) was preferred over MarkItDown on 83% of pages and over Trafilatura on 56% against 42%, a difference whose interval includes zero (net +0.14, 95% CI [-0.05, +0.33]). By type the judge favours ChromeRAG on forum, product, collection and service pages (67 to 73%) and Trafilatura on articles (60%), documentation (67%) and listings (53%), which matches the F1 ties. The judge scored content kept at 4.2 against 3.7 for Trafilatura and chrome left at 3.9 against 4.1 on a 5-point scale where 5 means no chrome: Trafilatura leaves a little less chrome, ChromeRAG keeps more content.

<!-- FIG 5 -->

### Site-template learning on real sites

`poc/run_stce_eval.py` compares coverage-mode output with and without the site model. On 11 benchmark site groups (49 pages) F_bal rises from 0.868 to 0.870. A crawl of up to 15 same-section pages from each documentation site (1,791 pages in 125 groups, robots.txt respected, list in `poc/stce_crawl_urls.json`) shows STCE changing 314 pages and keeping F_bal level (0.876 to 0.877, recall 0.805 both); text repeated across a site falls from 12.6 to 12.3 five-grams per page. Thirteen pages from seven sites lose more than 0.05 recall, which we did not inspect individually. Because most repeated chrome is already removed before STCE (site-repeated text is 2.1% of ChromeRAG's output, 2.1% for Trafilatura and 34.9% for MarkItDown), STCE is a guarded complement for template blocks without chrome markup, as in the example above.

---

## Impact

**Improving an existing workflow.** Chunking and embedding scraped HTML is routine data engineering, and chrome removal is often done with per-site regular expressions. ChromeRAG replaces them with one tested step that runs on CPU without network access or a model download, reports what it removed and why, and tells the caller when it is unsure. Its accuracy gain concentrates where article-tuned tools fail: forums, product pages, category pages and multi-section service pages. For retrieval it keeps the content that BM25 needs (hit@5 above Trafilatura on landing and documentation pages) while leaving 20 times less chrome in the retrieved context than a structure-preserving converter.

**Integration pathways.** The LangChain loader and LlamaIndex reader turn stored HTML files into documents whose metadata carries the front-matter, so a splitter copies title, type and breadcrumb onto every chunk. `chromerag batch` fits Airflow or Prefect jobs after a crawl; `batch_summary.json` sends thin pages to a headless browser, and the confidence estimate lets a job route low-confidence pages to review or to a heavier extractor.

**New research questions.** The repository includes a tool-agnostic harness: cross-validation by site, final-evaluation scripts, error taxonomy, frontier and confidence calibration (`poc/wcxb_*`), the landing-page corpus builder with a pre-registered split, the judge and retrieval evaluations, and all per-page outputs. Open questions include how far block-level labels from one benchmark transfer to other languages and page mixes, whether a sentence encoder improves on the lexical features, and how site-template models age.

**Adoption.** ChromeRAG was first released on PyPI and GitHub in September 2026, so download, citation and third-party usage figures are not yet meaningful. The issue tracker, the live leaderboards at https://pedapudibhargav.github.io/ChromeRAG/ and the archived releases (Zenodo) are the channels for outside feedback.

**Limitations.** (i) ChromeRAG does not run JavaScript; it warns about shells but cannot recover their content. (ii) The model was trained on one benchmark (WCXB development pages, mostly English); its features include English stop words and call-to-action verbs, and other languages and page mixes are untested. (iii) Labels are word overlaps with human-reviewed references, and annotators are inconsistent in places: documentation code samples are included on 82% of pages but left out of repeated live samples on others, which caps the gain on documentation (ChromeRAG and Trafilatura are within noise there). (iv) The ceilings of block selection are 0.975 for articles but only 0.80 to 0.85 for products, collections, listings and forums, so absolute scores on those types stay lower. (v) Landing-page evidence uses a structural-anchor metric that cannot see chrome inside `<main>`, an LLM judge and BM25/dense retrieval over known-item queries, not human ratings of answers. (vi) STCE needs at least three pages per site group. (vii) Only HTML is handled. (viii) The benchmark's author also builds a competing extractor; we use the public data and our own scorer, which matches the benchmark's definition.

---

## Conclusions

ChromeRAG is a focused, installable component for the ingest step of web RAG pipelines. A 150 KB learned block filter, evaluated with NumPy, removes site chrome on a wide range of page types: on the 511 held-out WCXB pages it gains 0.043 F1 over Trafilatura, with large gains on forums, products and collections and ties on articles and documentation. It also learns a site's template, carries Schema.org metadata and tables into chunk-friendly form, and reports unusable inputs and low-confidence pages. On company landing pages a blind judge prefers its output to Trafilatura's on 70% of pages (and to MarkItDown's on 87%); on a mixed WCXB sample it prefers it to MarkItDown's on 83% and is statistically tied with Trafilatura. The code, the model, the training and evaluation scripts, and per-page results are openly available. Planned work covers multilingual training data, an optional sentence-encoder feature [17] and evaluation with generated answers.

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

The software, the list of benchmark URLs (`poc/corpus_urls.json`), the evaluation harness, per-page scores, the retrieval and STCE evaluations, the STCE crawl list (`poc/stce_crawl_urls.json`) and aggregate results (`docs/data/`) are openly available at https://github.com/pedapudibhargav/ChromeRAG under the MIT license. The raw third-party HTML pages are not redistributed. They can be fetched again with `python -m poc.run_corpus_comparison`, although live pages change over time.

---

## Declaration of generative AI and AI-assisted technologies in the manuscript preparation process

During the preparation of this work the author used Cursor (with a Grok-based coding agent) and Anthropic Claude (Claude Code) in order to assist with software development, code review, drafting and editing of the manuscript text, and verification of reported numbers against the benchmark outputs, and analysis scripts for the evaluation. After using these tools, the author reviewed and edited the content as needed and takes full responsibility for the content of the published article.

---

## References

1. P. Lewis, E. Perez, A. Piktus, F. Petroni, V. Karpukhin, N. Goyal, H. Küttler, M. Lewis, W. Yih, T. Rocktäschel, S. Riedel, and D. Kiela, "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," in *Advances in Neural Information Processing Systems 33 (NeurIPS 2020)*, 2020, pp. 9459–9474. arXiv: 2005.11401.
2. C. Kohlschütter, P. Fankhauser, and W. Nejdl, "Boilerplate Detection Using Shallow Text Features," in *Proc. 3rd ACM Int. Conf. Web Search and Data Mining (WSDM)*, 2010, pp. 441–450. doi: 10.1145/1718487.1718542.
3. T. Vogels, O.-E. Ganea, and C. Eickhoff, "Web2Text: Deep Structured Boilerplate Removal," in *Advances in Information Retrieval (ECIR 2018)*, LNCS, 2018, pp. 167–179. doi: 10.1007/978-3-319-76941-7_13.
4. J. Leonhardt, A. Anand, and M. Khosla, "Boilerplate Removal using a Neural Sequence Labeling Model," in *Companion Proc. The Web Conf. 2020 (WWW '20)*, 2020. arXiv: 2004.14294.
5. A. Barbaresi, "Trafilatura: A Web Scraping Library and Command-Line Tool for Text Discovery and Extraction," in *Proc. ACL-IJCNLP 2021: System Demonstrations*, 2021, pp. 122–131. doi: 10.18653/v1/2021.acl-demo.15.
6. Y. Baburov et al., *python-readability* (readability-lxml), Python port of Arc90 Readability, GitHub. [Online]. Available: https://github.com/buriy/python-readability
7. Microsoft, *MarkItDown*: Python tool for converting files and office documents to Markdown, GitHub. [Online]. Available: https://github.com/microsoft/markitdown
8. J. Bevendorff, S. Gupta, J. Kiesel, and B. Stein, "An Empirical Comparison of Web Content Extraction Algorithms," in *Proc. 46th Int. ACM SIGIR Conf.*, 2023, pp. 2594–2603. doi: 10.1145/3539618.3591920.
9. M. Foley, "WCXB: A Multi-Type Web Content Extraction Benchmark," arXiv: 2605.21097, May 2026. Data: CC-BY-4.0.
10. M. Foley, *rs-trafilatura*: web content extraction in Rust with page-type classification, GitHub. [Online]. Available: https://github.com/Murrough-Foley/rs-trafilatura
11. M. Liu et al., "Dripper: Token-Efficient Main HTML Extraction with a Lightweight LM," arXiv: 2511.23119, 2025.
12. Z. Bar-Yossef and S. Rajagopalan, "Template Detection via Data Mining and its Applications," in *Proc. 11th Int. World Wide Web Conf. (WWW)*, 2002, pp. 580–591. doi: 10.1145/511446.511522.
13. L. Yi, B. Liu, and X. Li, "Eliminating Noisy Information in Web Pages for Data Mining," in *Proc. 9th ACM SIGKDD Int. Conf. Knowledge Discovery and Data Mining*, 2003, pp. 296–305. doi: 10.1145/956750.956785.
14. J. Alarte, J. Silva, and S. Tamarit, "What Web Template Extractor Should I Use? A Benchmarking and Comparison for Five Template Extractors," *ACM Trans. Web*, vol. 13, no. 2, pp. 1–19, 2019. doi: 10.1145/3316810.
15. J. Tan, Z. Dou, W. Wang, M. Wang, W. Chen, and J.-R. Wen, "HtmlRAG: HTML is Better Than Plain Text for Modeling Retrieved Knowledge in RAG Systems," in *Proc. ACM Web Conf. 2025 (WWW '25)*, 2025, pp. 1733–1746. doi: 10.1145/3696410.3714546.
16. K. Weinberger, A. Dasgupta, J. Langford, A. Smola, and J. Attenberg, "Feature Hashing for Large Scale Multitask Learning," in *Proc. 26th Int. Conf. Machine Learning (ICML)*, 2009, pp. 1113–1120. doi: 10.1145/1553374.1553516.
17. N. Reimers and I. Gurevych, "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks," in *Proc. EMNLP-IJCNLP 2019*, 2019, pp. 3980–3990. doi: 10.18653/v1/D19-1410.
18. B. C. Peddapudi, *ChromeRAG*, version 0.1.3, Zenodo, 2026. doi: 10.5281/zenodo.23107381 (all versions: 10.5281/zenodo.22970289). Source: https://github.com/pedapudibhargav/ChromeRAG

---
