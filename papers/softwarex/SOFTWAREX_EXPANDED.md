# ChromeRAG: A Learned Boilerplate Filter for Web RAG Ingestion

**Target journal:** Elsevier *SoftwareX* (Original Software Publication)  
**Package:** `chromerag` (v0.1.4)  
**Draft status:** Source text for `scripts/fill_softwarex_docx.py`, which fills the official SoftwareX OSP Word template (v6, March 2026). Do not submit this Markdown file as-is.

**Authors:** Bhargava Chary Peddapudi (Independent Researcher, Milpitas, California 95035, United States; ORCID: https://orcid.org/0009-0002-8523-8415)  
**Corresponding email:** pedapudibhargav@gmail.com

---

## Abstract

Web pages indexed for retrieval-augmented generation (RAG) carry navigation, banners and comment threads that become noisy chunks. ChromeRAG is an MIT-licensed, CPU-only Python package and command-line tool that converts HTML into RAG-ready Markdown and heading-aware chunks. A 150 KB gradient-boosted tree model, run with NumPy only, scores each text block; rules and an optional site model remove repeated chrome. On 372 WCXB test pages absent from its training folder it reaches a word-level F1 of 0.907 (front-matter excluded) against 0.867 for Trafilatura. On 328 pages from 106 unseen sites, blinded judges from three model families prefer it to Trafilatura (net score +0.19 to +0.45).

**Keywords:** retrieval-augmented generation; HTML extraction; boilerplate removal; main content extraction; Markdown; Python

---

## Motivation and significance

**Chrome pollutes RAG indexes.** Retrieval-augmented generation grounds a language model in retrieved passages [1]. In organizations those passages come from documentation portals, product pages and knowledge bases, HTML never written for machines. Each page mixes its content with site-wide "chrome": navigation, cookie banners, calls to action, related-article lists, comment threads and footers. Converted naively and embedded, the same text appears in the chunks of every page; these near-duplicates compete with real content at query time and use up the model's context. A 10,000-page portal with a 200-token footer adds two million tokens of identical text to the index. We met the problem while preparing web pages for a study of retrieval drift as an index grows [2], where chrome inside the chunks made clean ingestion the limiting step.

**Related work and the gap.** Shallow text features [3] and neural sequence labeling [4, 5] classify blocks within one page. Trafilatura [6] and Readability [7] are widely used extractors tuned for articles; a large comparison [8] found no algorithm best on every page type. Converters such as MarkItDown [9] keep headings, tables and code but do not remove chrome, and Crawl4AI's pruning filter [10] scores nodes by text and link density. The WCXB benchmark [11] makes the weakness of article-tuned tools measurable: systems agree on articles (F1 about 0.93) and differ by 20 to 30 points on forums, products and collections; its leaders are a page-type-aware Rust extractor [12] and a 0.6B-parameter language-model block labeler [13]. Using several pages of one site to find its template was proposed early [14, 15] and benchmarked in [16]; query-time pruning such as HtmlRAG [17] complements ingest-time cleaning. ChromeRAG follows the feature-engineered block classification of [3] with gradient-boosted trees, adapts the discard patterns of Trafilatura [6], and packages both as a small CPU-only component with an optional site-template model, metadata, Markdown tables and heading-aware chunks, and explicit signals when the input is unusable or the extraction is unsure.

**What ChromeRAG provides.** (i) A *learned block filter*: trees over about 530 features of each text block; (ii) *chrome rules*: 37 evidence-backed YAML rules and generic detectors for tables of contents, pagers, comments, related posts, call-to-action buttons, share strips, author boxes and page tails; (iii) *site-template chrome elimination* (STCE), an optional model learned from one site's pages; (iv) Schema.org metadata as YAML front-matter; (v) Markdown tables, headings, lists and code kept; (vi) *chunks* that carry their heading path; (vii) input-quality warnings and a per-page confidence estimate. It needs no model download and works in air-gapped environments.

---

## Software description

### Software architecture

ChromeRAG is a Python package (`src/chromerag`, about 5,900 lines) built on BeautifulSoup/lxml and NumPy. Each document passes through six stages (Fig. 1). A pytest suite of 195 tests covers the pipeline, rules with fixtures, golden outputs, the chunker, the CLI and STCE; continuous integration runs on Linux macOS and Windows.

<!-- FIG 1 -->

*Stage 1: input-quality gate.* The raw HTML is measured for visible text, script weight, single-page-application root markers and "enable JavaScript" hints; thin inputs produce warnings.

*Stage 2: schema harvest.* JSON-LD and Microdata are read before scripts are removed; title, type, description, dates, author and breadcrumb become YAML front-matter.

*Stage 3: cleaning, rules and STCE.* Scripts, styles and SVG are removed; hidden nodes and skip links are removed unless a hidden block holds long running text with few links. A page-wide `<form>`, an unclosed `<button>` or a large `<noscript>` keeps its content, as does the `<header>` of an `<article>` that holds the page `h1`. A YAML rule index of 37 rules drops known chrome: consent managers, share bars, documentation-framework widgets and 16 rules adapted from the discard patterns of Trafilatura [6]. Every rule carries evidence and a fixture. Generic detectors then remove in-page tables of contents, previous/next pagers, comment sections of articles, related-post blocks, standalone call-to-action buttons, share strips, newsletter blocks, author boxes, template placeholders and a footer-like tail after the last substantive block; each has guards (never the page title, a long paragraph, or more than a fixed share of the words) and a switch. If a site model is supplied, blocks whose signature (a hash of tag, id, classes and role, or of the text for bare blocks) is in the model are removed. `chromerag learn` keeps a signature only if it appears on at least 80% of a group's pages, stays short, and looks like chrome or is identical on every page.

*Stage 4: chrome pruning.* Landmark and class-word rules (`nav`, `footer`, cookie, newsletter, sidebar) remove subtrees unless they contain `<main>`, most of the page's text, or two or more long paragraphs with few links. A content-root ladder (`main`, `role=main`, `article`, content classes) is validated by size.

*Stage 5: learned block filter.* The page is split into blocks (paragraphs, headings, list items, quotes, preformatted blocks, tables, text-only containers, and loose text between block elements). Each block is described by about 530 numbers: its text, its place in the page (position, distance to headings, content root), its tree context (ancestor tags, link density of enclosing boxes, repeated sibling structures), the words of its ancestors' `class` and `id`, feature-hashed [18], and the words of the heading above. Trees (300 trees of depth 6, trained with scikit-learn) give the probability that the block is main content; the exported model is a 150 KB array file and prediction uses NumPy only. A block is kept when its probability reaches 0.30 (`coverage`), 0.50 (`balanced`) or 0.70 (`precision`). Three structure rules complement the trees: the page's own `h1` is kept, a heading is kept when one of the next two blocks is kept, and the paragraph under the title is kept when it is a real sentence. Pages with fewer than four blocks are kept whole and exact repeats are written once. `diagnostics["lbc"]` holds an estimate of the page's F1 from the block probabilities; below 0.70 a warning is issued.

*Stage 6: tables and Markdown.* Layout tables are unwrapped; rectangular data tables become Markdown tables, other tables key-value rows. The page is written in document order with heading levels, bold and italic, inline code, fenced code blocks that keep their lines, and ordered and nested lists; link targets are omitted unless requested (`--links`).

*Training.* `poc/lbc_data.py` labels every block of the 1,495 scoreable files of the public WCXB `dev/` folder by word-trigram overlap with the human-reviewed main content; `poc/train_lbc.py` fits the trees, weighting blocks by word count, in about two minutes. The folder also contains 139 files that WCXB's metadata assigns to the test split (see below), so the shipped model saw them; we therefore report test results without them. The rules and detectors of Stages 3 and 5 were written and tuned on development material only, never on the pages used for the final judgments below.

ChromeRAG does not fetch pages, render JavaScript or crawl.

### Software functionalities

The Python API centers on `ChromeRAG(config=..., site_chrome=...)`. `PipelineConfig.from_priority()` selects `COVERAGE`, `BALANCED` (default) or `PRECISION`. Stages can be switched off (for example `--no-rules`, `--no-stce`). `extract(html, url=None)` returns a typed `ExtractResult` with `markdown`, `front_matter`, `warnings`, `input_quality`, a token estimate and `diagnostics`. `result.chunks()` splits the Markdown into chunks of at most 180 words inside heading sections, never cutting a code block or table; each `Chunk` has the heading path from the page title to its section, a depth, and `embed_text`, the body preceded by that path, ready for an embedding model; `chromerag extract page.html --chunks` writes them as JSON lines.

Table 1. ChromeRAG command-line interface.

| Task | Command | Output |
|---|---|---|
| One page | chromerag extract page.html -o page.md --priority balanced | Markdown; --json-meta prints diagnostics; --explain lists removed blocks; --chunks writes JSON lines; --fail-on-thin exits with code 3 |
| Learn site chrome | chromerag learn pages/ -o site.json --min-pages 3 | JSON site model grouped by host and path prefix |
| Batch | chromerag batch pages/ -o out/ --chrome-model site.json | One Markdown file per page and batch_summary.json flagging thin/JS-shell pages |

The package needs Python 3.11 or later, installs with `pip install chromerag` [19] and has four direct dependencies (BeautifulSoup, lxml, PyYAML, NumPy). Getting Markdown takes two lines (`from chromerag import ChromeRAG; md = ChromeRAG().extract(html).markdown`); Trafilatura needs `output_format="markdown"` and table options, Readability returns HTML that must be converted again, and MarkItDown reads files or streams. Optional LangChain and LlamaIndex components return one document per page with the front-matter as metadata.

---

## Illustrative examples

### Learning a site template

`examples/site/` holds four synthetic pages of a fictional documentation site. They share a header menu, cookie banner, sales call to action, footer and a repeated paragraph inside `<main>`: "Widget Summit 2026 is in Lisbon this autumn, and registration is open to every Widget user." Single-page extraction removes the menu, banner and footer; the paragraph reads like content, so the learned filter keeps it until a site model is learned:

```bash
pip install chromerag
chromerag learn examples/site -o out/site.json --min-pages 3
chromerag batch examples/site -o out/batch --chrome-model out/site.json
```

`learn` reports one site group (`docs.example.com/docs`) with six chrome signatures; `batch` applies them, and the paragraph disappears from all four pages. The `pricing` page keeps its JSON-LD as front-matter and its table as a Markdown table:

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
| Plan | Hosted minutes | Monthly price (USD) |
| --- | --- | --- |
| Team | 20,000 | 49 |
```

`chromerag extract examples/site/pricing.html --chunks` writes one JSON object per chunk with its `heading_path` and `embed_text`. A JavaScript shell produces a warning; with `--fail-on-thin` the command exits with code 3 so pipelines can route it to a headless browser.

### Human-reviewed benchmark

WCXB [11] has 2,008 pages in seven page types, with human-reviewed main content. Word-level F1 compares the bag of words of a tool's output with the reference (title excluded); "with" and "without" snippets test that required text is present and listed chrome absent. All tools receive the same HTML and no site model. ChromeRAG's YAML front-matter is removed before scoring, because it is metadata meant for chunk metadata and not text; scoring the raw default output with the benchmark's own script gives a lower value (about 0.87, or 0.90 with `enable_schema=False`). Trafilatura [6] runs with its best of four distinct settings on the development set; Readability [7] and MarkItDown [9] use defaults (Trafilatura 2.2.0, readability-lxml 0.9, MarkItDown 0.1.7, Python 3.14).

*Development results* for the learned filter come from five-fold cross-validation grouped by host and were obtained with the 0.1.3 pipeline, which differs from the current one only in the later rules and writer: F1 0.852 (`coverage`), 0.851 (`balanced`) and 0.837 (`precision`) against 0.818 for Trafilatura. Features and thresholds were chosen on these folds.

*Test results* use the shipped model, trained once on the whole development folder, and the frozen pipeline. An audit found that 139 of the 511 test pages are also in the public `dev/` folder with identical HTML (26 of 28 product and 25 of 34 collection pages), so the shipped model was trained on them; the primary result therefore uses the 372 test pages absent from `dev/` (Table 2, Fig. 2); on all 511 pages the F1 values are 0.901, 0.860, 0.763 and 0.540 for ChromeRAG, Trafilatura, Readability and MarkItDown, reported for comparability only. On the 308 of the 372 pages from registrable domains absent from `dev/`, ChromeRAG scores 0.905 and Trafilatura 0.870 (+0.035, 95% CI [+0.016, +0.054]).

Table 2. Word-level F1 on the 372 WCXB test pages absent from the development folder (ChromeRAG in `balanced` mode; product and collection have only 2 and 9 such pages).

| Page type (n) | ChromeRAG | Trafilatura | Readability | MarkItDown |
|---|---|---|---|---|
| All (372) | 0.907 | 0.867 | 0.778 | 0.568 |
| Article (178) | 0.951 | 0.953 | 0.944 | 0.663 |
| Documentation (40) | 0.949 | 0.931 | 0.866 | 0.614 |
| Service (56) | 0.864 | 0.813 | 0.595 | 0.478 |
| Forum (50) | 0.895 | 0.731 | 0.628 | 0.452 |
| Listing (37) | 0.754 | 0.707 | 0.445 | 0.386 |
| Collection (9) | 0.774 | 0.717 | 0.523 | 0.512 |
| Product (2) | 0.991 | 0.491 | 0.473 | 0.157 |

<!-- FIG 2 -->

Scores are means of page-level F1; intervals are percentile intervals of a paired bootstrap over pages (5,000 resamples, seed 0). On the 372 pages ChromeRAG leads Trafilatura by +0.040 (95% CI [+0.021, +0.059]; resampling its 316 domains instead, [+0.019, +0.062]): by +0.164 on forums [+0.102, +0.230], +0.051 on services [+0.004, +0.107] and +0.057 on the 9 collection pages [+0.024, +0.090]; on articles, documentation and listings the intervals contain zero, and 2 product pages allow no conclusion. Required snippets are found more often (0.783 against 0.743) and forbidden snippets less often (0.064 against 0.083). The benchmark's publication [11] reports 0.903 for the page-type-aware Rust extractor [12] and 0.841 for Trafilatura on all 511 test pages under its own configuration; we could not build that tool, so we quote it and claim no superiority; the settings differ and the numbers are not interchangeable.

Fig. 3 shows the trade-off on the development folds: ChromeRAG's curve passes above Trafilatura's operating point for thresholds 0.6 to 0.7 and has higher F1 at every threshold up to 0.8. Median time on 200 stored pages (100 documentation, 100 landing pages), one process, on an Apple M4 Pro, is 52 ms for ChromeRAG, 32 ms for Trafilatura, 31 ms for Readability and 39 ms for MarkItDown.

<!-- FIG 3 -->

### Blinded judging on pages never used in development

F1 against human labels cannot see everything a RAG index cares about, so we added blinded pairwise judging. Before any extractor ran on them, we wrote seed lists of 135 sites that no earlier step had used: 40 news, magazine and engineering-blog sites, 25 forums and question-and-answer sites, 30 listing and category pages and 40 service and software landing sites. A fixed script fetched 328 pages from the 106 sites that responded (130 articles, 56 forum threads, 30 listings, 112 service pages; robots.txt respected). For each page, a judge saw the page's visible text and two outputs, ChromeRAG (`balanced`) and Trafilatura, in random order with tool names hidden (ChromeRAG's front-matter removed, long outputs shortened alike), and applied one rubric: which output is better to index for RAG (content kept, chrome left out, structure), with 1-to-5 scores for content and chrome. Three model families judged the same pairs: Claude Sonnet 5.5 (sub-agents), GPT-5.6 luna and Gemini 3.7 Flash. The net score is wins minus losses divided by pairs (range -1 to +1; ties count zero); intervals are bootstrapped over pages. Code, rubric, pairs and verdicts are in the repository.

Table 3. Net score of ChromeRAG against Trafilatura (+1 = always preferred) on the 328 fresh pages and on the 367 WCXB test pages absent from `dev/` that both outputs cover.

| Set (pages) | Claude | GPT | Gemini |
|---|---|---|---|
| Fresh, all (328) | +0.41 [+0.33, +0.50] | +0.19 [+0.09, +0.29] | +0.45 [+0.35, +0.54] |
| Articles (130) | +0.32 [+0.18, +0.45] | +0.07 [-0.08, +0.23] | +0.37 [+0.22, +0.52] |
| Forums (56) | +0.93 [+0.84, +1.00] | +0.48 [+0.25, +0.70] | +0.91 [+0.80, +1.00] |
| Listings (30) | +0.27 [-0.07, +0.57] | +0.27 [-0.07, +0.60] | +0.33 [0.00, +0.67] |
| Services (112) | +0.31 [+0.14, +0.47] | +0.17 [-0.01, +0.35] | +0.34 [+0.17, +0.51] |
| WCXB clean, all (367) | +0.25 [+0.16, +0.34] | +0.22 [+0.13, +0.32] | not run |

<!-- FIG 4 -->

As Table 3 and Fig. 4 show, all three families rank ChromeRAG ahead of Trafilatura overall, with intervals above zero; the size of the margin differs by judge, and the families agree that forums gain most and that the gain on articles, listings and services is smaller (and, with GPT, not distinguishable from zero on articles, listings and services). Content kept scored higher for ChromeRAG (4.26 against 3.75 with Claude, 4.14 against 3.88 with GPT and 4.49 against 3.75 with Gemini on the fresh pages) and chrome left out scored about equal (4.02 against 3.88, 4.09 against 4.16 and 4.46 against 4.26). Against Readability, GPT prefers ChromeRAG on the fresh pages with +0.52 [+0.44, +0.61]. On two held-out sets of 180 documentation pages from 40 sites and 97 product pages from 22 shops (fetched the same way), GPT gives +0.07 [-0.07, +0.21] and +0.40 [+0.22, +0.57]: a tie on documentation and a clear gain on product pages. The judges are language models, so their agreement is evidence, not a human assessment. An early version was judged worse than Trafilatura (net -0.13 on the WCXB pages); the fixes that reversed this came from reading the judges' reasons on development material, which is why the fresh pages were fixed in advance and used once.

### Retrieval, anchors and chunks

The structural-anchor metric is computed from each input page, independently of any tool: content recall is the share of word 5-grams from `<main>`/`<article>` text found in the output, noise retention the share of 5-grams from navigation, header, footer, aside and cookie containers found, and F_bal their harmonic combination. It cannot see chrome inside `<main>`, which the rules now remove, so it understates ChromeRAG. In `coverage` mode ChromeRAG reaches 0.741 on 177 held-out landing pages and 0.735 on 178 pages of 51 companies fetched after the 0.1.3 freeze, against 0.680 and 0.649 for Trafilatura (+0.061 [+0.032, +0.090] and +0.087 [+0.054, +0.119]), and 0.797 against 0.739 on 242 documentation pages that were a development set (+0.058 [+0.034, +0.085]).

BM25 retrieval (k1 1.2, b 0.75) with known-item queries (titles, headings and two 12-word passages per page, about 200-word chunks) gives a hit@5 of 0.894 for ChromeRAG (`balanced`) against 0.832 for Trafilatura and 0.949 for MarkItDown on 668 queries over the fresh landing pages, and 0.948 against 0.921 and 0.964 on 773 queries over the documentation corpus. MarkItDown retrieves slightly more because it keeps everything, at 2.3 to 2.6% chrome in the retrieved context against 0.3 to 0.4% for ChromeRAG and 0.6 to 1.1% for Trafilatura.

Do chunks that carry their heading path retrieve better? We cut 354 documentation pages from 50 sites not used in training into 3,395 chunks and had Claude write one natural question for each of 400 chunks, given the chunk and its page title. Prepending the title and heading path to the embedded text raised dense MRR (text-embedding-3-small) from 0.853 to 0.913 (+0.060, 95% CI [+0.036, +0.083]) and BM25 MRR by the same amount (+0.060 [+0.039, +0.081]); the title alone gives about two thirds of the gain. This supports contextual chunk headers [20] on one corpus; the question writer saw the page title, and other page types and languages are untested.

### Site-template learning on real sites

`poc/run_stce_eval.py` compares `coverage` output with and without the site model. On 11 benchmark site groups (47 scoreable pages) F_bal is 0.840 without and 0.837 with the model. On a crawl of 125 documentation and product sites (1,727 scoreable pages) it is 0.866 without and 0.867 with the model, against 0.841 for Trafilatura. Since the learned filter and the rules already remove most repeated chrome (site-repeated text is 0.4% of ChromeRAG's output and 0.5% of Trafilatura's, against 26.7% for MarkItDown), STCE is an optional, guarded complement for template blocks that read like content, as in the example above; it no longer adds accuracy on these pages.

---

## Impact

**Improving an existing workflow.** Chunking and embedding scraped HTML is routine data engineering, and chrome removal is often done with per-site regular expressions. ChromeRAG offers one tested step instead: CPU-only, offline, reporting what it removed and why. Its gain concentrates where article-tuned tools fail (forums, service and category pages) and it matches Trafilatura on articles and documentation by F1. On the fresh-company pages it retrieved the right page more often than Trafilatura (hit@5 0.894 against 0.832) and left about eight times less chrome in the retrieved context than MarkItDown.

**Integration pathways.** The LangChain loader and LlamaIndex reader turn stored HTML files into documents whose metadata carries the front-matter, so a splitter copies title, type and breadcrumb onto every chunk; `chunks()` does the same for vector databases without a framework.

**New research questions.** The repository includes the full harness: cross-validation, corpus builders with frozen seed lists, blinded judge builders and per-page outputs. Open questions include other languages and page mixes, how site models age, and agreement between language-model and human judges.

**Adoption.** ChromeRAG was first released on PyPI and GitHub in September 2026, so download, citation and third-party usage figures are not yet meaningful.

**Limitations.** (i) No JavaScript is run; shells are flagged, not recovered. (ii) The model was trained on one mostly English benchmark, and its features include English stop words and call-to-action verbs. (iii) Labels are word overlaps with human-reviewed references, with some annotator inconsistency (documentation code samples are included on 82% of pages), which caps the gain on documentation. (iv) The public WCXB `dev/` folder contains 139 test pages, and 166 test pages share a domain with development; we report test results without the former and can say little about products and collections. (v) The anchor metric and the known-item queries come from the pages themselves (self-retrieval, not answer accuracy); judged results come from language models, whose verdicts are noisy (about 83% of swapped pairs repeated in an earlier check with one judge) and, for GPT and Gemini, not exactly reproducible; none is a human assessment. (vi) The rules were developed on documentation, landing and WCXB development pages; the fresh pages were used once, but the judges' summary scores had shown which page types needed work. (vii) STCE needs at least three pages per site group and added no accuracy on the pages we measured. (viii) Only HTML is handled. (ix) The benchmark's author also builds a competing extractor; we use the public data, a scorer that follows the benchmark's F1 definition, independent corpora and independent judges. (x) We did not compare with language-model extractors [13, 21], which need a GPU or a hosted model.

---

## Conclusions

ChromeRAG is a focused, installable component for the ingest step of web RAG pipelines. A 150 KB learned block filter, structural rules adapted from Trafilatura's discard patterns and a heading-aware chunker remove site chrome across page types: on 372 held-out WCXB test pages it gains 0.040 F1 over Trafilatura (forums +0.164, services +0.051) and ties on articles, documentation and listings; on 328 fresh pages blinded judges from three model families prefer it, and it retrieves better than Trafilatura with heading context adding 0.06 MRR. It can learn a site's template, carries Schema.org metadata and tables into chunk-friendly form, and reports unusable inputs and uncertain pages. Planned work covers multilingual training data, retraining without the 139 duplicated files, human-rated judgments and an optional sentence-encoder feature [22].

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

The software, the model, the training and evaluation scripts, the benchmark URL lists and frozen seed lists (`poc/corpus_urls.json`, `poc/landing_urls.json`, `poc/landing_urls_fresh.json`, `poc/landing_split.json`, `poc/stce_crawl_urls.json`, `poc/extra_seeds*.json`), per-page scores, judge prompts and raw judgments, and aggregate results (`evaluations/2026-10-v0.1.3/`, `docs/data/`) are openly available at https://github.com/pedapudibhargav/ChromeRAG under the MIT license, and version 0.1.4 is archived at Zenodo (doi: 10.5281/zenodo.23126161). WCXB (https://arxiv.org/abs/2605.21097, CC-BY-4.0) is obtained from its authors' release. The raw third-party HTML pages are not redistributed. They can be fetched again with the scripts in `poc/`, although live pages change over time.

---

## Declaration of generative AI and AI-assisted technologies in the manuscript preparation process

During the preparation of this work the author used Anthropic Claude (Claude Code) and AI coding agents in a code editor in order to assist with software development, code review, drafting and editing of the manuscript text, analysis scripts for the evaluation, and verification of reported numbers against the benchmark outputs. The author also used language models as components of the evaluation itself: Claude Sonnet, OpenAI gpt-5.6-luna and Google Gemini 3.7 Flash as blind pairwise judges of extraction quality, Claude to write retrieval questions, and OpenAI text-embedding-3-small for the dense-retrieval experiment; their prompts, samples and outputs are published with the repository. After using these tools, the author reviewed and edited the content as needed and takes full responsibility for the content of the published article.

---

## References

1. P. Lewis, E. Perez, A. Piktus, F. Petroni, V. Karpukhin, N. Goyal, H. Küttler, M. Lewis, W. Yih, T. Rocktäschel, S. Riedel, and D. Kiela, "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," in *Advances in Neural Information Processing Systems 33 (NeurIPS 2020)*, 2020, pp. 9459–9474. arXiv: 2005.11401.

2. B. C. Peddapudi, "Vector Retrieval Drift under Corpus Growth: A Controlled Empirical Study with Metadata Filtering on EnterpriseRAG-Bench," manuscript under review, 2026. Artifacts: https://pedapudibhargav.github.io/vector-drift-study/

3. C. Kohlschütter, P. Fankhauser, and W. Nejdl, "Boilerplate Detection Using Shallow Text Features," in *Proc. 3rd ACM Int. Conf. Web Search and Data Mining (WSDM)*, 2010, pp. 441–450. doi: 10.1145/1718487.1718542.

4. T. Vogels, O.-E. Ganea, and C. Eickhoff, "Web2Text: Deep Structured Boilerplate Removal," in *Advances in Information Retrieval (ECIR 2018)*, LNCS, 2018, pp. 167–179. doi: 10.1007/978-3-319-76941-7_13.

5. J. Leonhardt, A. Anand, and M. Khosla, "Boilerplate Removal using a Neural Sequence Labeling Model," in *Companion Proc. The Web Conf. 2020 (WWW '20)*, 2020, pp. 226–229. doi: 10.1145/3366424.3383547.

6. A. Barbaresi, "Trafilatura: A Web Scraping Library and Command-Line Tool for Text Discovery and Extraction," in *Proc. ACL-IJCNLP 2021: System Demonstrations*, 2021, pp. 122–131. doi: 10.18653/v1/2021.acl-demo.15.

7. Y. Baburov et al., *python-readability* (readability-lxml), Python port of Arc90 Readability, GitHub, accessed 2026-10-02. [Online]. Available: https://github.com/buriy/python-readability

8. J. Bevendorff, S. Gupta, J. Kiesel, and B. Stein, "An Empirical Comparison of Web Content Extraction Algorithms," in *Proc. 46th Int. ACM SIGIR Conf.*, 2023, pp. 2594–2603. doi: 10.1145/3539618.3591920.

9. Microsoft, *MarkItDown*: Python tool for converting files and office documents to Markdown, GitHub, accessed 2026-10-02. [Online]. Available: https://github.com/microsoft/markitdown

10. Crawl4AI, "Fit Markdown" (PruningContentFilter), documentation, accessed 2026-10-02. [Online]. Available: https://docs.crawl4ai.com/core/fit-markdown/

11. M. Foley, "WCXB: A Multi-Type Web Content Extraction Benchmark," arXiv: 2605.21097, May 2026. Data: CC-BY-4.0.

12. M. Foley, *rs-trafilatura*: web content extraction in Rust with page-type classification, GitHub, accessed 2026-10-02. [Online]. Available: https://github.com/Murrough-Foley/rs-trafilatura

13. M. Liu et al., "Dripper: Token-Efficient Main HTML Extraction with a Lightweight LM," arXiv: 2511.23119, 2025.

14. Z. Bar-Yossef and S. Rajagopalan, "Template Detection via Data Mining and its Applications," in *Proc. 11th Int. World Wide Web Conf. (WWW)*, 2002, pp. 580–591. doi: 10.1145/511446.511522.

15. L. Yi, B. Liu, and X. Li, "Eliminating Noisy Information in Web Pages for Data Mining," in *Proc. 9th ACM SIGKDD Int. Conf. Knowledge Discovery and Data Mining*, 2003, pp. 296–305. doi: 10.1145/956750.956785.

16. J. Alarte, J. Silva, and S. Tamarit, "What Web Template Extractor Should I Use? A Benchmarking and Comparison for Five Template Extractors," *ACM Trans. Web*, vol. 13, no. 2, Art. 9, 2019. doi: 10.1145/3316810.

17. J. Tan, Z. Dou, W. Wang, M. Wang, W. Chen, and J.-R. Wen, "HtmlRAG: HTML is Better Than Plain Text for Modeling Retrieved Knowledge in RAG Systems," in *Proc. ACM Web Conf. 2025 (WWW '25)*, 2025, pp. 1733–1746. doi: 10.1145/3696410.3714546.

18. K. Weinberger, A. Dasgupta, J. Langford, A. Smola, and J. Attenberg, "Feature Hashing for Large Scale Multitask Learning," in *Proc. 26th Int. Conf. Machine Learning (ICML)*, 2009, pp. 1113–1120. doi: 10.1145/1553374.1553516.

19. B. C. Peddapudi, *ChromeRAG*, version 0.1.4, Zenodo, 3 October 2026. doi: 10.5281/zenodo.23126161 (all versions: 10.5281/zenodo.22970289). Source: https://github.com/pedapudibhargav/ChromeRAG

20. Anthropic, "Introducing Contextual Retrieval," 19 September 2024. [Online]. Available: https://www.anthropic.com/news/contextual-retrieval

21. F. Wang, Z. Shi, B. Wang, N. Wang, and H. Xiao, "ReaderLM-v2: Small Language Model for HTML to Markdown and JSON," arXiv: 2503.01151, 2025.

22. N. Reimers and I. Gurevych, "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks," in *Proc. EMNLP-IJCNLP 2019*, 2019, pp. 3980–3990. doi: 10.18653/v1/D19-1410.
