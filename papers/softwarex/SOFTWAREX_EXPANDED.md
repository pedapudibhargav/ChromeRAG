# ChromeRAG: A Learned Boilerplate Filter for Web RAG Ingestion

**Target journal:** Elsevier *SoftwareX* (Original Software Publication)  
**Package:** `chromerag` (v0.1.3)  
**Draft status:** Source text for `scripts/fill_softwarex_docx.py`, which fills the official SoftwareX OSP Word template (v6, March 2026). Do not submit this Markdown file as-is.

**Authors:** Bhargava Chary Peddapudi (Independent Researcher; ORCID: https://orcid.org/0009-0002-8523-8415)  
**Corresponding email:** pedapudibhargav@gmail.com

---

## Abstract

Web pages indexed for retrieval-augmented generation (RAG) carry navigation, cookie banners, related links and comments that become noisy chunks. ChromeRAG is an MIT-licensed, CPU-only Python package and command-line tool that converts HTML into RAG-ready Markdown. A 150 KB gradient-boosted tree model, run with NumPy only, scores each text block; an optional site model removes repeated templates; metadata becomes front-matter, tables become key-value rows, and JavaScript shells are flagged. On 372 WCXB test pages not present in its training folder it reaches a word-level F1 of 0.903, against 0.867 for Trafilatura and 0.568 for MarkItDown.

**Keywords:** retrieval-augmented generation; HTML extraction; boilerplate removal; main content extraction; Markdown; Python

---

## Motivation and significance

**Chrome pollutes RAG indexes.** Retrieval-augmented generation grounds a language model in retrieved passages [1]. In organizations those passages come from documentation portals, product pages and knowledge bases, HTML never written for machines. Each page mixes its content with site-wide "chrome": navigation, cookie banners, calls to action, related-article lists, comment threads and footers. Converted naively and embedded, the same text appears in the chunks of every page; these near-duplicates compete with real content at query time and use up the model's context. A 10,000-page portal with a 200-token footer adds two million tokens of identical text to the index.

**Related work and the gap.** Shallow text features [2] and neural sequence labelling [3, 4] classify blocks within one page. Trafilatura [5] and Readability [6] are widely used extractors tuned for articles; a large comparison [7] found no algorithm best on every page type. Converters such as MarkItDown [8] keep headings, tables and code but do not remove chrome, and Crawl4AI's pruning filter [9] scores nodes by text density, link density and tag weights. The WCXB benchmark [10] makes the weakness of article-tuned tools measurable: systems agree on articles (F1 about 0.93) and differ by 20 to 30 points on forums, products and collections. It reports a page-type-aware Rust extractor with a learned page classifier [11] and a 0.6B-parameter language-model block labeller [12] as the leaders, with jusText, Resiliparse and a 1.5B model, ReaderLM-v2 [13], further behind. Using several pages of one site to find its template was proposed early [14, 15] and benchmarked in [16]; query-time pruning such as HtmlRAG [17] complements ingest-time cleaning. ChromeRAG follows the feature-engineered block classification of [2] with gradient-boosted trees, and packages it as a small CPU-only component with an optional site-template model, metadata and tables in a chunk-friendly form, and explicit signals when the input is unusable or the extraction is unsure.

**What ChromeRAG provides.** (i) A *learned block filter*: trees over about 530 features of each text block, with a threshold per content priority; (ii) *site-template chrome elimination* (STCE), an optional model learned from pages of one site; (iii) Schema.org JSON-LD and Microdata as YAML front-matter; (iv) tables as key-value rows; (v) input-quality warnings and a heuristic per-page confidence estimate. It needs no model download and works in air-gapped environments.

---

## Software description

### Software architecture

ChromeRAG is a small Python package (`src/chromerag`, about 4,000 lines) built on BeautifulSoup/lxml and NumPy. Each document passes through six stages (Fig. 1). A pytest suite of 64 tests covers the pipeline, the learned filter, the rule index, golden-output regression fixtures, the CLI, STCE and the LangChain loader; continuous integration runs on Linux (Python 3.11 to 3.14), macOS and Windows.

<!-- FIG 1 -->

*Stage 1: input-quality gate.* The raw HTML is measured for visible text, script weight, single-page-application root markers and "enable JavaScript" hints; thin inputs produce warnings.

*Stage 2: schema harvest.* JSON-LD and Microdata are read before scripts are removed; title, type, description, dates, author and breadcrumb become YAML front-matter.

*Stage 3: cleaning and STCE.* Scripts, styles and SVG are removed; hidden nodes and skip links are removed unless a hidden block holds long running text with few links. A wrapper such as a page-wide `<form>`, an unclosed `<button>` or a large `<noscript>` keeps its content. A YAML rule index drops known chrome (consent managers, share bars, generator footers); every rule carries evidence and a fixture. If a site model is supplied, blocks whose signature (a hash of tag, id, classes and role, or of the text for bare blocks) is in the model are removed. `chromerag learn` keeps a signature only if it appears on at least 80% of a group's pages, stays short, repeats its leading text, and either looks like chrome or is identical on every page; at extraction a match is removed only if it is close to its learned size and does not hold `<main>` or most of the page's text.

*Stage 4: chrome pruning.* Landmark and class-word rules (`nav`, `footer`, cookie, newsletter, sidebar) remove subtrees, unless the subtree contains `<main>`, holds most of the page's text, or holds two or more long paragraphs with few links. A content-root ladder (`main`, `role=main`, `article`, content classes) is validated by size.

*Stage 5: learned block filter.* The page is split into blocks (paragraphs, headings, list items, quotes, preformatted blocks, tables, text-only containers, and loose text between block elements). Each block is described by about 530 numbers: its text (length, link density, punctuation, stop-word share, call-to-action verbs, dates), its place in the page (position, distance to headings, content root), its tree context (ancestor tags, link density and text mass of enclosing boxes, repeated sibling structures such as comment threads, overlap with the title and long paragraphs), the words of its ancestors' `class` and `id`, feature-hashed [18], and the words of the heading above. Trees (300 trees of depth 6, trained with scikit-learn) give the probability that the block is main content. The exported model is a 150 KB array file and prediction uses NumPy only. A block is kept when its probability reaches 0.30 (`coverage`), 0.50 (`balanced`) or 0.70 (`precision`). Pages with fewer than four blocks are kept whole and exact repeats are written once. `diagnostics["lbc"]` holds an estimate of the page's precision, recall and F1: with block probabilities p and word counts w, expected true words are the sum of w times p over kept blocks and expected reference words the sum over all blocks. It assumes calibrated probabilities and is a heuristic; a warning is issued below an estimate of 0.70, a threshold chosen on development folds.

*Stage 6: tables and Markdown.* Layout tables are unwrapped; data tables become `Row n -> header: value | ...` lines. The page is written in document order with safe heading levels and fenced code; link targets are omitted unless requested (`--links`).

*Training.* `poc/lbc_data.py` labels every block of the 1,495 scoreable files of the public WCXB `dev/` folder by word-trigram overlap with the human-reviewed main content (blocks listed as "without" snippets are labelled noise); `poc/train_lbc.py` fits the trees, weighting blocks by word count, in about two minutes. Two of the 1,497 files have no reference field. The folder also contains 139 files that WCXB's metadata assigns to the test split (see below), so the shipped model saw them; thresholds and features were chosen on development folds that include them.

ChromeRAG does not fetch pages, render JavaScript or crawl; those belong to the caller or to the evaluation harness in `poc/`.

### Software functionalities

The Python API centres on `ChromeRAG(config=..., site_chrome=...)`. `PipelineConfig.from_priority()` selects `COVERAGE`, `BALANCED` (default) or `PRECISION`. Stages can be switched off (`--no-rules`, `--no-schema`, `--no-tables`, `--no-stce`; `enable_lbc=False` restores the density filter of 0.1.2). `extract(html, url=None)` returns a typed `ExtractResult` with `markdown`, `front_matter`, `warnings`, `input_quality`, a token estimate and `diagnostics` (kept and rejected samples, the rules that fired, the confidence estimate). The URL is metadata only.

Table 1. ChromeRAG command-line interface.

| Task | Command | Output |
|---|---|---|
| One page | chromerag extract page.html -o page.md --priority balanced | Markdown; --json-meta prints diagnostics; --explain lists removed blocks; --fail-on-thin exits with code 3 |
| Learn site chrome | chromerag learn pages/ -o site.json --min-pages 3 | JSON site model grouped by host and path prefix |
| Batch | chromerag batch pages/ -o out/ --chrome-model site.json | One Markdown file per page and batch_summary.json flagging thin/JS-shell pages |

The package needs Python 3.11 or later and installs with `pip install chromerag` [19]. Optional LangChain and LlamaIndex components return one document per page with the front-matter as metadata.

---

## Illustrative examples

### Learning a site template

`examples/site/` holds four synthetic pages of a fictional documentation site. They share a header menu, cookie banner, sales call to action, footer and a repeated paragraph inside `<main>`: "Widget Summit 2026 is in Lisbon this autumn, and registration is open to every Widget user." Single-page extraction removes the menu, banner and footer; the paragraph reads like content, so the learned filter keeps it until a site model is learned:

```bash
pip install chromerag
chromerag learn examples/site -o out/site.json --min-pages 3
chromerag batch examples/site -o out/batch --chrome-model out/site.json
```

`learn` reports one site group (`docs.example.com/docs`) with six chrome signatures; `batch` applies them, and the paragraph disappears from all four pages. The `pricing` page keeps its JSON-LD as front-matter and its table as key-value rows:

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

WCXB [10] has 2,008 pages in seven page types, with human-reviewed main content. Word-level F1 compares the bag of words of a tool's output with the reference (title excluded); "with" and "without" snippets test that required text is present and listed chrome absent. All tools receive the same HTML and no site model. ChromeRAG's YAML front-matter is removed before scoring, because it is metadata meant for chunk metadata and not text; scoring the raw default output with the benchmark's own script gives 0.869 on the pages of Table 2, and 0.904 with schema harvesting switched off (`enable_schema=False`), which writes no front-matter. Trafilatura [5] runs with its best of four distinct settings on the development set (tables, no comments, no links, Markdown; 0.818 against 0.814 for the defaults and 0.789 for `favor_recall`); Readability [6] and MarkItDown [8] use defaults (versions: Trafilatura 2.2.0, readability-lxml 0.9, MarkItDown 0.1.7, Python 3.14).

*Development results* come from five-fold cross-validation grouped by host: F1 is 0.852 (`coverage`), 0.851 (`balanced`) and 0.837 (`precision`) against 0.818 for Trafilatura. Features and thresholds were chosen on these folds, so they are development estimates. Replacing the 0.1.2 density filter by the learned filter raises F1 from 0.822, 0.817 and 0.790 to these values; most of the gain over 0.1.2 (0.749) comes from fixing whole-page losses (wrappers, hidden blocks, nested layout tables that repeated text, breadth-first output order, link targets counted as words).

*Test results* were produced once, after the code, model and thresholds were frozen (git tag `freeze-0.1.3`). No test label was used for fitting or for choosing thresholds, but an audit afterwards found that 139 of the 511 test pages are also in the public `dev/` folder with identical HTML (26 of 28 product and 25 of 34 collection pages), most likely a packaging error in the release (its metadata lists 1,358 development pages), so the shipped model was trained on them. The primary test result therefore uses the 372 test pages absent from `dev/` (Table 2, Fig. 2); on all 511 pages the F1 values are 0.902, 0.860, 0.763 and 0.540 for ChromeRAG, Trafilatura, Readability and MarkItDown, reported for comparability only. On the 345 test pages from domains absent from `dev/`, ChromeRAG scores 0.903 and Trafilatura 0.874 (+0.029, 95% CI [+0.012, +0.046]).

Table 2. Word-level F1 on the 372 WCXB test pages absent from the development folder (ChromeRAG in `balanced` mode; product and collection have only 2 and 9 such pages).

| Page type (n) | ChromeRAG | Trafilatura | Readability | MarkItDown |
|---|---|---|---|---|
| All (372) | 0.903 | 0.867 | 0.778 | 0.568 |
| Article (178) | 0.951 | 0.953 | 0.944 | 0.663 |
| Documentation (40) | 0.954 | 0.931 | 0.866 | 0.614 |
| Service (56) | 0.836 | 0.813 | 0.595 | 0.478 |
| Forum (50) | 0.884 | 0.731 | 0.628 | 0.452 |
| Listing (37) | 0.768 | 0.707 | 0.445 | 0.386 |
| Collection (9) | 0.788 | 0.717 | 0.523 | 0.512 |
| Product (2) | 1.000 | 0.491 | 0.473 | 0.157 |

<!-- FIG 2 -->

Scores are means of page-level F1; intervals are percentile intervals of a paired bootstrap over pages (5,000 resamples, seed 0). Clustering the resampling by domain on all 511 pages gives [+0.027, +0.060] for the overall difference. On the 372 pages ChromeRAG leads Trafilatura by +0.036 (95% CI [+0.018, +0.054]) and by +0.153 on forums [+0.090, +0.219]. On articles, documentation, services and listings the intervals contain zero; the 9 collection pages give +0.071 [+0.025, +0.117] and 2 product pages allow no conclusion. For these two types cross-validation is more informative: collections 0.651 against 0.564 (+0.087) and products 0.652 against 0.626 (+0.026). Required snippets are found more often (+0.063) and forbidden snippets equally often. The benchmark's publication [10] reports 0.903 for the page-type-aware Rust extractor [11] and 0.841 for Trafilatura on all 511 test pages under its own configuration; we could not build that tool, so we quote it and claim no superiority; the settings differ and the numbers are not interchangeable.

Fig. 3 shows the trade-off on the development folds: ChromeRAG's curve passes above Trafilatura's operating point for thresholds 0.6 to 0.7 (higher precision and recall at once) and has higher F1 at every threshold up to 0.8. The page-level estimate of Stage 5 is informative but not calibrated: pages estimated below 0.70 (7.6% of development pages, scored out of fold) have an actual F1 of 0.57 on average against 0.88 for the rest.

<!-- FIG 3 -->

Median time on 200 stored pages (100 documentation, 100 landing pages), one process, one warm-up and three timed passes, on an Apple M4 Pro with 48 GB, is 36 ms for ChromeRAG, 30 ms for Trafilatura, 30 ms for Readability and 37 ms for MarkItDown; 95th percentiles are 108, 147, 108 and 104 ms.

### Marketing and landing pages, retrieval and judged quality

We also built a corpus of company landing pages (`poc/landing_corpus.py`): up to five pages per company chosen from the homepage's own links before any extractor ran. Companies were split by hash into development and held-out sets; a second list of 51 companies was fetched only after the freeze ("fresh"). The structural-anchor metric is computed from each input page, independently of any tool: content recall is the share of word 5-grams from `<main>`/`<article>` text found in the output; noise retention is the share of 5-grams from navigation, header, footer, aside and cookie containers found; 5-grams in both sets are discarded; F_bal is the harmonic mean of recall and one minus noise retention, averaged over pages with at least 50 content anchors. It is a proxy that cannot see chrome inside `<main>`, and ChromeRAG's content-root selection also prefers `<main>`/`<article>`. In `coverage` mode ChromeRAG reaches 0.759 on 177 scoreable held-out pages and 0.780 on 178 fresh pages, against 0.680 and 0.649 for Trafilatura, 0.723 and 0.741 for MarkItDown (which keeps 24 to 26% of the chrome anchors, ChromeRAG 0.1% or less) and 0.512 and 0.567 for Readability. Because 11 of 42 held-out and 9 of 47 fresh registrable domains also occur in WCXB development, we repeated the comparison on other domains: ChromeRAG minus Trafilatura is +0.052 [+0.017, +0.086] on 130 held-out pages and +0.136 [+0.105, +0.167] on 147 fresh pages (resampled by page; up to five pages share a company). On 242 documentation, pricing and article pages of the development corpus (re-fetched on 2026-10-02, not held out) the metric gives 0.833 for `coverage` and 0.739 for Trafilatura (+0.094, CI [+0.066, +0.122]); Trafilatura keeps under 20% of the content on 25 of these pages, ChromeRAG on 2.

BM25 retrieval (k1 1.2, b 0.75) with 668 known-item queries over the fresh pages (about 200-word chunks; queries are titles, headings and two 12-word passages per page from the input HTML before extraction, kept only if unique to one page; chrome is the share of retrieved text made of navigation, header and footer anchors) gives a hit@5 of 0.916 for ChromeRAG against 0.832 for Trafilatura (+0.084 [+0.045, +0.123]) and 0.949 for MarkItDown, which keeps everything (chrome in 2.3% of the retrieved context against 0.1% for ChromeRAG and 1.1% for Trafilatura). Queries come from `<main>`/`<article>`, like the anchors. With dense embeddings (`text-embedding-3-small`) all tools but Readability tie (0.708 against 0.698 for Trafilatura; +0.010 [-0.024, +0.047]). On the development documentation corpus BM25 hit@5 is 0.947 against 0.921 for Trafilatura (+0.026 [+0.001, +0.051]) and 0.964 for MarkItDown, with 2,010 chunks against 3,909.

<!-- FIG 4 -->

A pairwise judgement by one language model (gpt-5.6-luna; tool names hidden, output order randomised) was run on two samples; about 83% of pairs repeated with swapped positions got the same verdict, so the judge is noisy and, being proprietary, cannot be reproduced exactly. Prompt, samples and raw judgements are in the repository. On 100 landing pages ChromeRAG (`coverage`) was preferred over Trafilatura on 70% and over MarkItDown on 87%, against 28% and 12% (held-out pages 62% against 36%, fresh pages 78% against 20% for Trafilatura; Fig. 5). A second sample of 105 WCXB test pages (15 per type) contained 33 pages from the `dev/` folder; on the other 72, ChromeRAG (`balanced`) was preferred over MarkItDown on 79% against 21%, over Readability on 68% against 28%, and over Trafilatura on 53% against 44%, a difference whose interval includes zero. By type on these 72 pages ChromeRAG won more pairs than it lost against Trafilatura on service (11 against 4) and forum (11 against 4) pages and fewer on articles (4 against 6), documentation (5 against 9) and listings (4 against 7), in line with the F1 ties on articles and documentation. Content kept scored 4.2 against 3.9 for Trafilatura and chrome left out 3.9 against 4.0 (5 means no chrome): Trafilatura leaves slightly less chrome, ChromeRAG keeps more content.

<!-- FIG 5 -->

### Site-template learning on real sites

`poc/run_stce_eval.py` compares `coverage` output with and without the site model. On 11 benchmark site groups (49 pages) F_bal rises from 0.868 to 0.870. A crawl of up to 15 same-section pages from each documentation site (1,791 pages in 125 groups, robots.txt respected, list in `poc/stce_crawl_urls.json`) shows STCE changing 314 pages and leaving F_bal level (0.876 to 0.877); text repeated across a site falls from 12.6 to 12.3 five-grams per page, and 13 pages from seven sites lose more than 0.05 recall (not inspected individually). Since the learned filter already removes most repeated chrome (site-repeated text is 2.1% of ChromeRAG's output, 2.1% for Trafilatura and 34.9% for MarkItDown), STCE is an optional, guarded complement for template blocks that read like content, as in the example above; it is not the main source of accuracy.

---

## Impact

**Improving an existing workflow.** Chunking and embedding scraped HTML is routine data engineering, and chrome removal is often done with per-site regular expressions. ChromeRAG offers one tested step instead: CPU-only, offline, without a model download, reporting what it removed and why, with a heuristic low-confidence warning. Its accuracy gain concentrates where article-tuned tools fail: forum pages (clear on held-out data) and, by cross-validation, category pages; on articles and documentation it matches Trafilatura. On the fresh-company evaluation it retrieved the right page more often than Trafilatura (hit@5 0.916 against 0.832) and left about 23 times less chrome in the retrieved context than MarkItDown (5 times on the documentation corpus).

**Integration pathways.** The LangChain loader and LlamaIndex reader turn stored HTML files into documents whose metadata carries the front-matter, so a splitter copies title, type and breadcrumb onto every chunk. `chromerag batch` fits Airflow or Prefect jobs after a crawl; its summary sends thin pages to a headless browser, and the confidence estimate lets a job route uncertain pages to review.

**New research questions.** The repository includes the harness: site-grouped cross-validation, final-evaluation scripts, error taxonomy, the landing-corpus builder with a pre-registered split, judge and retrieval evaluations, and per-page outputs. Open questions include transfer to other languages and page mixes, and how site models age.

**Adoption.** ChromeRAG was first released on PyPI and GitHub in September 2026, so download, citation and third-party usage figures are not yet meaningful. The issue tracker, the live leaderboards at https://pedapudibhargav.github.io/ChromeRAG/ and the archived releases are the channels for outside feedback.

**Limitations.** (i) No JavaScript is run; shells are flagged, not recovered. (ii) The model was trained on one benchmark (mostly English); its features include English stop words and call-to-action verbs, and other languages and page mixes are untested. (iii) Labels are word overlaps with human-reviewed references, and annotators are inconsistent in places (documentation code samples are included on 82% of pages but omitted for repeated live samples on others), which caps the gain on documentation. (iv) The ceilings of block selection are 0.975 for articles but 0.80 to 0.85 for products, collections, listings and forums. (v) The public WCXB `dev/` folder contains 139 test pages and 166 test pages share a domain with development; we report test results without them, and cannot say much about products and collections on held-out data. Part of the landing-page and documentation evidence also shares registrable domains with development, and the documentation corpus is a development set. (vi) The anchor metric and retrieval queries come from `<main>`/`<article>`, which the content-root selection also targets; judge results come from one proprietary model; none of this is a human assessment. (vii) STCE needs at least three pages per site group. (viii) Only HTML is handled. (ix) The benchmark's author also builds a competing extractor; we use the public data and a scorer that follows the benchmark's word-F1 definition but removes ChromeRAG's front-matter.

---

## Conclusions

ChromeRAG is a focused, installable component for the ingest step of web RAG pipelines. A 150 KB learned block filter, run with NumPy, removes site chrome across page types: on 372 held-out WCXB test pages it gains 0.036 F1 over Trafilatura, with a clear gain on forum pages (+0.153) and ties on articles, documentation, services and listings; cross-validation also favours it on collections. It can learn a site's template, carries Schema.org metadata and tables into chunk-friendly form, and reports unusable inputs and uncertain pages. On company landing pages a language-model judge prefers its output to Trafilatura's on 70% of pages and to MarkItDown's on 87%; on a mixed WCXB sample it prefers it to MarkItDown's on 79% and is tied with Trafilatura. The code, the model, the scripts and the per-page results are openly available. Planned work covers multilingual training data, retraining without the 139 duplicated files, an optional sentence-encoder feature [20] and evaluation with generated answers.

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

The software, the model, the training and evaluation scripts, the benchmark URL lists (`poc/corpus_urls.json`, `poc/landing_urls.json`, `poc/landing_urls_fresh.json`, `poc/landing_split.json`, `poc/stce_crawl_urls.json`), per-page scores, judge prompts and raw judgements, and aggregate results (`evaluations/2026-10-v0.1.3/`, `docs/data/`) are openly available at https://github.com/pedapudibhargav/ChromeRAG under the MIT license. WCXB (https://arxiv.org/abs/2605.21097, CC-BY-4.0) is obtained from its authors' release. The raw third-party HTML pages are not redistributed. They can be fetched again with `python -m poc.run_corpus_comparison`, although live pages change over time.

---

## Declaration of generative AI and AI-assisted technologies in the manuscript preparation process

During the preparation of this work the author used Cursor (with a Grok-based coding agent) and Anthropic Claude (Claude Code) in order to assist with software development, code review, drafting and editing of the manuscript text, analysis scripts for the evaluation, and verification of reported numbers against the benchmark outputs. The author also used OpenAI models as components of the evaluation itself: gpt-5.6-luna as the blind pairwise judge of extraction quality and text-embedding-3-small for the dense-retrieval experiment; their prompts, samples and outputs are published with the repository. After using these tools, the author reviewed and edited the content as needed and takes full responsibility for the content of the published article.

---

## References

1. P. Lewis, E. Perez, A. Piktus, F. Petroni, V. Karpukhin, N. Goyal, H. Küttler, M. Lewis, W. Yih, T. Rocktäschel, S. Riedel, and D. Kiela, "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," in *Advances in Neural Information Processing Systems 33 (NeurIPS 2020)*, 2020, pp. 9459–9474. arXiv: 2005.11401.
2. C. Kohlschütter, P. Fankhauser, and W. Nejdl, "Boilerplate Detection Using Shallow Text Features," in *Proc. 3rd ACM Int. Conf. Web Search and Data Mining (WSDM)*, 2010, pp. 441–450. doi: 10.1145/1718487.1718542.
3. T. Vogels, O.-E. Ganea, and C. Eickhoff, "Web2Text: Deep Structured Boilerplate Removal," in *Advances in Information Retrieval (ECIR 2018)*, LNCS, 2018, pp. 167–179. doi: 10.1007/978-3-319-76941-7_13.
4. J. Leonhardt, A. Anand, and M. Khosla, "Boilerplate Removal using a Neural Sequence Labeling Model," in *Companion Proc. The Web Conf. 2020 (WWW '20)*, 2020, pp. 226–229. doi: 10.1145/3366424.3383547.
5. A. Barbaresi, "Trafilatura: A Web Scraping Library and Command-Line Tool for Text Discovery and Extraction," in *Proc. ACL-IJCNLP 2021: System Demonstrations*, 2021, pp. 122–131. doi: 10.18653/v1/2021.acl-demo.15.
6. Y. Baburov et al., *python-readability* (readability-lxml), Python port of Arc90 Readability, GitHub, accessed 2026-10-02. [Online]. Available: https://github.com/buriy/python-readability
7. J. Bevendorff, S. Gupta, J. Kiesel, and B. Stein, "An Empirical Comparison of Web Content Extraction Algorithms," in *Proc. 46th Int. ACM SIGIR Conf.*, 2023, pp. 2594–2603. doi: 10.1145/3539618.3591920.
8. Microsoft, *MarkItDown*: Python tool for converting files and office documents to Markdown, GitHub, accessed 2026-10-02. [Online]. Available: https://github.com/microsoft/markitdown
9. Crawl4AI, "Fit Markdown" (PruningContentFilter), documentation, accessed 2026-10-02. [Online]. Available: https://docs.crawl4ai.com/core/fit-markdown/
10. M. Foley, "WCXB: A Multi-Type Web Content Extraction Benchmark," arXiv: 2605.21097, May 2026. Data: CC-BY-4.0.
11. M. Foley, *rs-trafilatura*: web content extraction in Rust with page-type classification, GitHub, accessed 2026-10-02. [Online]. Available: https://github.com/Murrough-Foley/rs-trafilatura
12. M. Liu et al., "Dripper: Token-Efficient Main HTML Extraction with a Lightweight LM," arXiv: 2511.23119, 2025.
13. F. Wang, Z. Shi, B. Wang, N. Wang, and H. Xiao, "ReaderLM-v2: Small Language Model for HTML to Markdown and JSON," arXiv: 2503.01151, 2025.
14. Z. Bar-Yossef and S. Rajagopalan, "Template Detection via Data Mining and its Applications," in *Proc. 11th Int. World Wide Web Conf. (WWW)*, 2002, pp. 580–591. doi: 10.1145/511446.511522.
15. L. Yi, B. Liu, and X. Li, "Eliminating Noisy Information in Web Pages for Data Mining," in *Proc. 9th ACM SIGKDD Int. Conf. Knowledge Discovery and Data Mining*, 2003, pp. 296–305. doi: 10.1145/956750.956785.
16. J. Alarte, J. Silva, and S. Tamarit, "What Web Template Extractor Should I Use? A Benchmarking and Comparison for Five Template Extractors," *ACM Trans. Web*, vol. 13, no. 2, Art. 9, 2019. doi: 10.1145/3316810.
17. J. Tan, Z. Dou, W. Wang, M. Wang, W. Chen, and J.-R. Wen, "HtmlRAG: HTML is Better Than Plain Text for Modeling Retrieved Knowledge in RAG Systems," in *Proc. ACM Web Conf. 2025 (WWW '25)*, 2025, pp. 1733–1746. doi: 10.1145/3696410.3714546.
18. K. Weinberger, A. Dasgupta, J. Langford, A. Smola, and J. Attenberg, "Feature Hashing for Large Scale Multitask Learning," in *Proc. 26th Int. Conf. Machine Learning (ICML)*, 2009, pp. 1113–1120. doi: 10.1145/1553374.1553516.
19. B. C. Peddapudi, *ChromeRAG*, version 0.1.3, Zenodo, 2026. doi: 10.5281/zenodo.23107381 (all versions: 10.5281/zenodo.22970289). Source: https://github.com/pedapudibhargav/ChromeRAG
20. N. Reimers and I. Gurevych, "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks," in *Proc. EMNLP-IJCNLP 2019*, 2019, pp. 3980–3990. doi: 10.18653/v1/D19-1410.

---
