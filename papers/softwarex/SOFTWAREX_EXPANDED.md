# ChromeRAG: A Learned Boilerplate Filter for Web RAG Ingestion

**Target journal:** Elsevier *SoftwareX* (Original Software Publication)  
**Package:** `chromerag` (v0.1.5)  
**Draft status:** Revision 1 (manuscript SOFTX-S-26-01950). Source text for `scripts/fill_softwarex_docx.py`, which fills the official SoftwareX OSP Word template (v6, March 2026). Do not submit this Markdown file as-is. Supplementary tables S1–S9: `evaluations/2026-11-final/SUPPLEMENT.md`.

**Authors:** Bhargava Chary Peddapudi (Independent Researcher, Milpitas, California 95035, United States; ORCID: https://orcid.org/0009-0002-8523-8415)  
**Corresponding email:** pedapudibhargav@gmail.com

---

## Abstract

Web pages indexed for retrieval-augmented generation (RAG) carry site chrome that becomes noisy chunks. ChromeRAG is an MIT-licensed, CPU-only Python package that converts HTML into Markdown with metadata and heading-aware chunks; a 150 KB tree model scores each text block. Version 0.1.5, retrained without any known test-split domain, reaches word F1 0.884 on the 511 WCXB test pages (a split consulted during earlier development) against 0.860 for Trafilatura, mostly on forums; raw output with front matter ties (0.853). Five human raters preferred it to Trafilatura on 75 pages (net +0.23 [+0.01, +0.42]), mainly on forums. On 500 CRAG questions accuracy did not measurably differ, from a 15–17% smaller index.

**Keywords:** retrieval-augmented generation; HTML extraction; boilerplate removal; main content extraction; Markdown; Python

---

## Motivation and significance

**Chrome pollutes RAG indexes.** Retrieval-augmented generation grounds a language model in retrieved passages [1], often from web pages never written for machines. Each page mixes its content with site-wide "chrome": navigation, cookie banners, calls to action, related-article lists and footers. Embedded naively, this text recurs in every page's chunks, competes with real content and uses up context. Support forums and question-and-answer threads are where extractors tuned for news articles lose most [2].

**Related software and how ChromeRAG differs.** Learned main-content detectors range from shallow text features with decision trees [3] and tree ensembles over diverse features, including class and id words [4], to neural sequence labeling [5, 6] and small language models [7, 8]. Heuristic extractors include jusText [9], Readability [10] and Trafilatura [11]; a comparison on eight datasets found no extractor best on every page genre [12]. The WCXB benchmark [2] adds forum, service, listing, product and collection pages; its leading system, rs-trafilatura [13], routes pages through a learned page-type classifier. Converters such as MarkItDown [14] and Crawl4AI [15] produce Markdown for language-model pipelines, and HtmlRAG [16] prunes HTML at query time. ChromeRAG proposes no new algorithm: its block classifier follows [3, 4] with gradient-boosted trees, and some rules are adapted from Trafilatura. It is an engineering integration with checkable deliverables: one offline, CPU-only call returning Markdown, Schema.org front matter, heading-aware chunks and input-quality warnings; three content-priority modes with measured trade-offs; training on domains disjoint from the test split; and an ablation after which most components without measured benefit were removed. No single feature is new (Table 1).

Table 1. Related software, with WCXB test F1 on the same 511 pages: published [2] and our own run (n/p, not published).

| Tool | Method | Decision unit | Output | F1 published / own run |
|---|---|---|---|---|
| BoilerPy3 [3, 17] | Learned, shallow features (2010 news model) | Text block | Text | n/p / 0.753 |
| Dragnet [4] | Learned, tree ensemble | Block | Text | n/p / not run |
| Web2Text, BoilerNet [5, 6] | Neural sequence labeling | Block, node | Labels | n/p / not run |
| jusText [9] | Heuristic | Paragraph | Text | n/p / 0.713 |
| Readability [10] | Heuristic | DOM subtree | HTML | 0.736 / 0.763 |
| Trafilatura [11] | Heuristic | DOM element | Text, Markdown, metadata | 0.841 / 0.860 |
| rs-trafilatura [13] | Rules, learned page type | DOM, per page type | Markdown, metadata, confidence | 0.903 / 0.891 |
| Dripper (MinerU-HTML), ReaderLM-v2 [7, 8] | Language model (0.6B, 1.5B) | Block, page | HTML, Markdown | n/p / not run |
| ChromeRAG 0.1.5 | Learned, tree ensemble, rules | Text block | Markdown, front matter, chunks, warnings | n/p / 0.884 |

**What ChromeRAG provides.** A *learned block filter*; switchable *chrome rules* and detectors; optional, experimental *site-template chrome elimination* (STCE), off by default; Schema.org front matter; structured Markdown; heading-aware *chunks*; and input-quality warnings with a per-page confidence estimate, all offline.

---

## Software description

### Software architecture

ChromeRAG 0.1.5 is a Python package (`src/chromerag`, about 7,400 lines) built on BeautifulSoup/lxml and NumPy. Each document passes through six stages (Fig. 1), and each component can be switched off.

<!-- FIG 1 -->

*Stages 1–2: input gate and schema.* Visible text, script weight and single-page-application markers are measured, and thin inputs produce warnings. JSON-LD and Microdata become YAML front matter (title, type, description, dates, author, breadcrumb).

*Stage 3: cleaning and rules.* Scripts, styles and hidden nodes are removed. Thirteen YAML rules, each with evidence and a fixture, drop consent managers, share bars and patterns adapted from Trafilatura's discard list; Trafilatura-style density passes then drop link-dense blocks and very short leaves. Guarded generic detectors remove in-page tables of contents, article comment sections, calls to action, share strips, newsletter and author boxes and a footer-like tail. If a site model is supplied, STCE removes blocks whose signature (a hash of tag, id, classes and role) it lists.

*Stage 4: chrome pruning.* Landmark and class-word rules (`nav`, `footer`, cookie, sidebar) remove subtrees unless they hold `<main>` or most of the page's running text.

*Stage 5: learned block filter.* Each text block is described by 535 features of its text, position, tree context (ancestor tags, link density, repeated siblings), feature-hashed class and id words of its ancestors [18] and the heading above. Gradient-boosted trees (300 of depth 6, scikit-learn) give the probability that it is main content; the exported 152,432-byte model runs with NumPy only. A block is kept at probability 0.30 (`coverage`), 0.50 (`balanced`, default) or 0.70 (`precision`). With the filter switched off, an older density score (text length, link and text density) decides instead. Structure rules keep the `h1`, headings above kept content and the lead paragraph; a table rescue and a retry handle collapsed output. A per-page F1 estimate below 0.70 raises a warning.

*Stage 6: Markdown.* Tables, headings, lists and fenced code keep their structure.

*Training.* The 0.1.5 model is trained on a strict subset of the public WCXB `dev/` folder: the 139 files that duplicate test pages and the 96 pages whose registrable domain (Public Suffix List) occurs in the test split are removed, leaving 1,238 pages, of which 1,233 yield features. A test asserts that no training domain is a test domain; three training pages and one test page have no URL and could not be checked. `poc/rebuild_strict.sh` reproduces the model byte for byte.

*Testing.* The pytest suite has 366 tests; two skip without optional data or extras. `ci.yml` runs ruff and pytest on every push and pull request on Linux, macOS and Windows (Python 3.11 and 3.13), skipping tests that need local data; a second workflow runs the README commands on each PyPI release.


### Software functionalities

`ChromeRAG(config=..., site_chrome=...)` is the main API, and `PipelineConfig.from_priority()` selects the mode. `extract(html, url=None)` returns an `ExtractResult` with `markdown`, `front_matter`, `warnings`, `input_quality` and `diagnostics`. `result.chunks()` splits the Markdown into chunks of at most 180 words inside heading sections, never cutting a code block or table; each chunk has its heading path and `embed_text`, the body preceded by that path. Table 2 lists the command-line tasks. The package needs Python 3.11 or later, installs with `pip install chromerag` [19] and has four direct dependencies.

Table 2. ChromeRAG command-line interface.

| Task | Command | Output |
|---|---|---|
| One page | chromerag extract page.html -o page.md --priority balanced | Markdown; --explain lists removed blocks; --chunks writes JSON lines; --fail-on-thin exits with code 3 |
| Learn site chrome (experimental) | chromerag learn pages/ -o site.json --min-pages 3 | JSON site model grouped by host and path prefix |
| Batch | chromerag batch pages/ -o out/ --chrome-model site.json | One Markdown file per page and a summary flagging thin pages |

---

## Illustrative examples

### Pages to Markdown and chunks

`examples/site/` holds four synthetic pages of a documentation site with a header menu, cookie banner, sales call to action, footer and a repeated event paragraph inside `<main>`.

```bash
pip install chromerag
chromerag extract examples/site/pricing.html -o pricing.md
chromerag extract examples/site/pricing.html --chunks
```

The pricing page keeps its JSON-LD as front matter and its table as a Markdown table; `--chunks` writes JSON lines with `heading_path` ("Plans and pricing > Reference table") and `embed_text`. A JavaScript shell produces a warning; with `--fail-on-thin` the command exits with code 3, so pipelines can route it to a headless browser.

`chromerag learn examples/site -o site.json --min-pages 3` finds six chrome signatures. With 0.1.4 only the site model removed the repeated event paragraph; the 0.1.5 filter removes it, so `chromerag batch` output is byte-identical with and without the site model, and we know of no 0.1.5 case where STCE helps. It stays an experimental option. Site-template detection is long established [20, 21]; with 0.1.4, STCE changed a structural score by 0.001 or less on 1,727 crawled pages. It is externally triggered adaptation; nothing evaluates or changes the classifier or rules, so ChromeRAG is not self-improving.

### Evaluation protocol and held-out use

The v0.1.4 manuscript said that the fresh pages were "fixed in advance and used once" and that rules were never tuned on pages used for final judgments. Both statements were wrong. After the freeze-0.1.3 run the WCXB test split was scored in full 12 more times during rule development and AI judges ran 10 times on sets that included test pages (Table S1a); rule groups were kept only if test F1 held, and judge reasons from test pages guided fixes. The 328 fresh pages were judged in several rounds while the code changed. For 0.1.5 the code was frozen (tag freeze-0.1.5) before any held-out run of 0.1.5 code; earlier that day 0.1.4 code (void), Trafilatura variants and rs-trafilatura had been scored on the test split (Table S1b). Protocol, page list and rubric were tagged before the runs they govern, and no code or setting changed after any held-out result. The 296 new pages, CRAG split 1 and the human set were each scored once (one 296-page judge run crashed unseen and was rerun; two ledger rows were reconstructed later). The WCXB test split, scored on 1 November as planned, was re-scored on 20 November with the frozen code, as a dated protocol amendment records, for rows requested in review (raw output, subsets, old code, BoilerPy3) and rows the author added (jusText, Trafilatura options, speed). It is therefore reported as previously consulted. The held-out evidence is the human set, the 296 new pages and CRAG split 1. The v0.1.4 retrieval and Claude-judged results are superseded.

### WCXB test split

WCXB [2] has human-reviewed main content for pages of seven types. Word F1 compares an output's bag of words with the reference; "with" and "without" snippet rates test that required text is present and listed chrome absent. All tools receive the same HTML and no site model. Trafilatura 2.2.0, the version installed for the protocol runs, runs without metadata (tables on); jusText 3.0.2 uses its English stop list; BoilerPy3 1.0.7 [17], which ships the news-trained classifier of [3], and rs-trafilatura 0.1.1 ran once in CI on an identical copy of the split. Intervals are paired percentile intervals from 5,000 resamples of 444 sites (443 registrable domains and one group for the page without URL).

Table 3. WCXB test split, all 511 pages (ChromeRAG front matter removed unless "raw"; lower without-rate is better).

| Tool | F1 | Without | With |
|---|---|---|---|
| ChromeRAG balanced | 0.884 | 0.070 | 0.759 |
| ChromeRAG balanced, raw default output | 0.853 | 0.092 | 0.761 |
| ChromeRAG coverage / precision | 0.882 / 0.872 | 0.083 / 0.060 | 0.781 / 0.725 |
| Trafilatura 2.2.0 | 0.860 | 0.083 | 0.720 |
| Trafilatura 2.2.0 with metadata, raw | 0.832 | 0.110 | 0.725 |
| rs-trafilatura 0.1.1 | 0.891 | 0.111 | 0.864 |
| Readability | 0.763 | 0.089 | 0.552 |
| BoilerPy3 Default / Article | 0.753 / 0.686 | 0.150 / 0.099 | 0.695 / 0.545 |
| jusText | 0.713 | 0.058 | 0.593 |
| MarkItDown | 0.540 | 0.967 | 0.768 |

Against Trafilatura, both without metadata (the primary comparison fixed in the protocol), balanced ChromeRAG gains +0.024 [+0.008, +0.042]. The raw default output ties Trafilatura's default (−0.006 [−0.022, +0.010]); with metadata on both sides the gain is +0.022 [+0.007, +0.037]. The reference holds body text only, and ChromeRAG always writes front matter (42 words on average); pipelines that pass front matter as chunk metadata get the stripped figure. Trafilatura 2.3.1, scored on 1 November before the freeze, reaches 0.8625, a gain of about +0.021 (unpaired); its recall and precision options score lower (0.845, 0.787; Table S3). In F1, rs-trafilatura minus ChromeRAG is +0.007 [−0.013, +0.025], a tie; rs-trafilatura keeps more required text (with-rate +0.105 [+0.075, +0.134]) and more listed chrome (without-rate +0.041 [+0.025, +0.059]) and leads on 4 of 7 page types. It was developed against the development set [2], on which ChromeRAG is also trained; we claim no superiority. The freeze-0.1.3 code with the 0.1.5 model, which predates the later test-split use, has the same F1 (0.1.5 minus it −0.002 [−0.008, +0.005]), but 0.1.5 has lower without-rate (−0.022 [−0.034, −0.011]) and with-rate (−0.035 [−0.049, −0.022]): rules added while this split was consulted changed its snippet rates, so ChromeRAG's without-rate is the figure most exposed to that use. Subsets appear in Table S3.

Table 4. WCXB test F1 by page type (balanced ChromeRAG minus Trafilatura, 95% site-bootstrap interval).

| Page type (n) | ChromeRAG | Trafilatura | Difference | rs-trafilatura |
|---|---|---|---|---|
| Article (257) | 0.940 | 0.952 | −0.012 [−0.024, −0.001] | 0.951 |
| Documentation (42) | 0.954 | 0.934 | +0.020 [−0.022, +0.070] | 0.973 |
| Service (59) | 0.849 | 0.817 | +0.031 [−0.008, +0.071] | 0.832 |
| Forum (51) | 0.866 | 0.717 | +0.149 [+0.092, +0.230] | 0.836 |
| Listing (40) | 0.732 | 0.722 | +0.010 [−0.113, +0.140] | 0.748 |
| Product (28) | 0.805 | 0.724 | +0.081 [+0.000, +0.181] | 0.777 |
| Collection (34) | 0.704 | 0.626 | +0.078 [−0.002, +0.152] | 0.775 |

The gain comes from forums (Fig. 2) and, less certainly, products and collections; documentation, services and listings tie, and Trafilatura leads on articles by 0.012. The split holds out domains, not forum software. In a post hoc check with a mechanical platform detector, the gain is +0.157 [+0.099, +0.249] on 34 forum pages whose platform occurs among training forum pages and +0.059 [−0.071, +0.187] on 13 whose platform does not (4 unidentified; Table S4). Median time per page (Fig. 3) is 39.6 ms for ChromeRAG (90th percentile 86.3), 14.2 ms for Trafilatura, 15.8 ms for Readability and 8.1 ms for jusText: ChromeRAG is about three times slower than Trafilatura, or 20 pages per second per process.

<!-- FIG 2 -->

<!-- FIG 3 -->

### Component ablation

The ablation uses five-fold cross-validation grouped by registrable domain on the 1,238 strict development pages (Table 5; Table S5). Only the learned model is cross-validated; rules, detectors and thresholds were developed on these pages, which favors the full pipeline. A rule fixed beforehand dropped any component whose removal neither lowered F1 nor raised the without-snippet rate: five Trafilatura-derived rule groups, 15 documentation-framework rules and two detectors. Structure rules and table rescue were kept as disclosed exceptions (removing them lost content on some pages), and a stacked second model was not shipped (ten times the size for +0.004 F1). On the frozen run the consent rules and two Trafilatura-derived groups also meet the rule but remain as switches (Table S5). The learned filter carries the gain: without it F1 falls by 0.030, to 0.830 (Trafilatura 0.828). Rules, detectors, density passes and pruning together add 0.019 F1 and lower leftover chrome. The same trees trained only on the 22 shallow block and neighbour features of [3] lose 0.016 F1 and leave more chrome; DOM, position and heading context recover it (Table S5b).

Table 5. Ablation on strict development pages (balanced; change against the full pipeline: F1 0.859, without-rate 0.055; all intervals in Table S5).

| Removed or changed | ΔF1 | ΔWithout |
|---|---|---|
| Learned filter (density score instead) | −0.0296 [−0.0363, −0.0234] | +0.0210 |
| Learned filter and density score (rules only) | −0.0215 [−0.0281, −0.0153] | +0.0339 |
| Rules, detectors, density passes and pruning (filter only) | −0.0188 [−0.0252, −0.0125] | +0.1491 |
| Chrome pruning | −0.0062 [−0.0105, −0.0019] | +0.0470 |
| Trafilatura-style density passes | +0.0017 [−0.0022, +0.0059] | +0.0164 |
| Generic detectors | −0.0009 [−0.0021, +0.0004] | +0.0065 |
| YAML rules | +0.0002 [−0.0003, +0.0009] | +0.0002 |
| Structure rules (kept) | +0.0003 [−0.0006, +0.0010] | −0.0069 |
| Shallow features only (22) | −0.0157 [−0.0206, −0.0113] | +0.0321 |

Per-type F1 here, ChromeRAG against Trafilatura: articles 0.944/0.936, forums 0.801/0.687, services 0.819/0.771, products 0.609/0.619 (Table S4).

### Human rating with AI judges

Five unpaid volunteers from the author's professional network, not authors, rated 75 pages from 48 sites on an author-approved list of mainstream sites; two rated the full set and three one part each. After skips, 67 pages had three ratings, 3 had two and the 5 anchor pages four or five. A blind offline app showed the saved page text and three outputs labelled A, B and C in random order (ChromeRAG balanced, Trafilatura, Readability), with difference highlighting (on by default) that marks text found in only one or two outputs and lists text an output lacks. Raters ticked the best output and scored content kept and noise left in from 1 to 5 under a written rubric (Table S9). The analysis was fixed in a commit before any rating: majority verdict per page, 95% intervals from 10,000 site resamples. Forums were fixed at 10 of 75 pages, knowing that forums suit ChromeRAG. GPT, Grok and Gemini judged the same outputs in pairs, without highlighting, under the same rubric, and their verdicts were saved before any rating was read (Table S2). Before any rater saw it, this set replaced the protocol's random draw from the 296 new pages, for rater safety; GPT's verdicts against Trafilatura were 34–32–9 (net +0.03) on that draw and 42–27–6 (+0.20) on the new set. After the AI judges' totals were seen, two tool-blind length rules swapped 5 pages (Table S6).

Table 6. Net preference for ChromeRAG (share of pages won minus share lost; 95% site-bootstrap interval). AI judges: gpt-5.6-luna, grok-4.5, gemini-4-argon-medium.

| Judge | vs Trafilatura, all 75 | Forums (10) | Without forums (65) | vs Readability, all 75 |
|---|---|---|---|---|
| Humans | +0.23 [+0.01, +0.42] | +0.80 [+0.60, +1.00] | +0.14 [−0.09, +0.35] | +0.33 [+0.13, +0.52] |
| GPT | +0.21 [−0.03, +0.44] | +0.60 [+0.00, +1.00] | +0.15 [−0.09, +0.39] | +0.35 [+0.12, +0.56] |
| Grok | +0.25 [+0.03, +0.48] | +1.00 [+1.00, +1.00] | +0.14 [−0.09, +0.37] | +0.32 [+0.08, +0.54] |
| Gemini | +0.25 [+0.01, +0.48] | +1.00 [+1.00, +1.00] | +0.14 [−0.11, +0.39] | +0.33 [+0.10, +0.55] |

The primary outcome (Fig. 4), the overall net against Trafilatura, is above zero (32 wins, 15 losses, 28 ties), mainly from forum threads (10 pages from 6 sites); outside forums the interval includes zero. Raters scored ChromeRAG higher on content kept (+0.38 [+0.05, +0.67] on the 1–5 scale) and about equal on noise (+0.10 [−0.07, +0.28]). Like the AI judges, humans favored the longer output (net +0.69 when ChromeRAG's was longer, −0.44 when Trafilatura's was); on 25 pages of similar length the net is +0.12 [−0.16, +0.40] (exploratory). Against Readability the preference holds without forums (+0.29 [+0.08, +0.49]). Without the one rater flagged by the careless-rating rule fixed beforehand, the net is +0.19 [+0.06, +0.31]. Agreement among raters is low to moderate (Krippendorff's α 0.42); opposite verdicts occurred on 7 of 75 pages. Post hoc, 34 pages (20 sites; 5 of the 10 forum pages) are on registrable domains of WCXB pages used in development, 20 of training and 14 of test pages, though no URL is shared; without them the net is +0.22 [−0.05, +0.46] on 41 pages. Other post hoc checks (ties excluded, one rater left out, forums reweighted to their WCXB share) agree in direction, but some intervals include zero (Table S6). In a post hoc error analysis coded by a Claude model after unblinding, ChromeRAG lost a content block on 6 and structure on 3 of the 15 pages won by Trafilatura. AI judges agree with the human majority with Cohen's κ 0.37–0.47 against Trafilatura and 0.27–0.34 against Readability, mostly disagreeing on pages humans called a tie. As raters had the highlighting and three outputs while AI judges compared pairs without it, κ compares related but different tasks, and the aid may have made lost content easier for humans to see.

<!-- FIG 4 -->

On the 296 new pages the protocol's primary GPT net against Trafilatura is +0.15 [+0.04, +0.25] (158–114–24), but longer outputs won 65% of decided pairs and a fixed-order check from the same scores ties 74–74, so this is weak evidence; GPT slightly preferred MarkItDown to ChromeRAG (151–143; Table S8). No Claude model served as a judge in this version.

### Answer-level test on CRAG

CRAG [22] supplies independently written questions with up to five retrieved web pages each. Each tool's output is cut into 200-word chunks, BM25 retrieves the top five from that question's pages (at most 1,200 words), gpt-5.6-luna answers from that context only, and the same model grades each answer as accurate, missing or incorrect; the score is accurate minus incorrect. Split 0 was used during development, including to choose the default mode; split 1 (500 questions, seed 0) was run once on the frozen code. On split 1 balanced ChromeRAG scores 0.306 and Trafilatura 0.298 (+0.008 [−0.040, +0.054]) while indexing 1,948 against 2,335 words per page (2,061 against 2,419 extracted): no measurable difference in answer accuracy from an index 15–17% smaller. The planned hit@5 on short answers is level (0.543 against 0.549), a post hoc regrade under a stricter rubric gives +0.014, and the split 0 lead (+0.056) did not repeat (Table S7).

---

## Impact

**Improving an existing workflow.** Chrome removal is often done with per-site expressions; ChromeRAG offers one tested, offline, CPU-only step that reports what it removed and why. Its measured advantage is on forums and question-and-answer pages: +0.149 F1 on WCXB, a human net of +0.80 on 10 forum pages from 6 sites, and positive nets from all three AI judges. It trails Trafilatura on WCXB articles by 0.012, and slightly on development-set products. Its WCXB F1 exceeds that of Readability, BoilerPy3 (a 2010 news-trained model), jusText and MarkItDown, though GPT slightly preferred MarkItDown on the 296 new pages.

**Integration pathways.** Optional LangChain and LlamaIndex components put the front matter into document metadata, so every chunk carries title, type and breadcrumb; `chunks()` does the same without a framework.

**Research artifacts.** The strict split and cross-validation, ablation switches, held-out ledger, locked protocol and rubric, and an offline blind three-way rating app with its analyzer (`evaluators/`) are reusable for other extractors.

**Adoption.** ChromeRAG was released on PyPI and GitHub in September 2026, so usage figures are not yet meaningful.

**Limitations.** (i) No JavaScript is run; shells are flagged, not recovered. (ii) Training data are one mostly English benchmark, and features include English stop words. (iii) The WCXB test split was consulted during earlier development, and its without-rate is most exposed to that use; it holds out domains, not forum software; product and collection results rest on 28 and 34 pages. (iv) The human study covers 75 pages from approved mainstream sites, 34 on WCXB domains, read as offline text with a highlighting aid the AI judges lacked; agreement is low to moderate. (v) AI judges and humans favor longer outputs. Grok and Gemini ran with settings we could not control. GPT also judged repeatedly in v0.1.4 development, where its reasons may have guided fixes; Grok and Gemini models also wrote or reviewed code. (vi) The CRAG test uses one model and BM25 over each question's own pages, so chrome repeated across a corpus is not tested; Readability and the planned retrieved-chrome share were not run. (vii) ChromeRAG is about three times slower than Trafilatura. (viii) STCE has no measured benefit in 0.1.5. (ix) Dragnet, Web2Text, BoilerNet and language-model extractors were not run (unmaintained dependencies or a GPU); the shallow-feature method of [3] was retrained on our pages only within ChromeRAG's harness (Table S5b). (x) The benchmark's author also develops a competing extractor; we use the public data, a scorer following its F1 definition, and independent pages and raters.

---

## Conclusions

ChromeRAG is a small, installable component for the ingest step of web RAG pipelines. Retrained without any known WCXB test-split domain, it gains 0.024 F1 over Trafilatura on the previously consulted test split, mostly on forums; its raw default output ties, and it trails slightly on articles. Human raters preferred it, mainly on forum threads, and CRAG answer accuracy did not measurably differ. Planned work covers multilingual training and faster features.

---

## CRediT author contribution statement

**Bhargava Chary Peddapudi:** Conceptualization, Methodology, Software, Validation, Formal analysis, Investigation, Data curation, Visualization, Writing — original draft, Writing — review & editing.

---

## Declaration of competing interest

The author declares that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper.

---

## Funding

This research did not receive any specific grant from funding agencies in the public, commercial, or not-for-profit sectors.

---

## Data availability

The software, the model, the training, evaluation and rating code and all aggregate and per-page results are openly available at https://github.com/pedapudibhargav/ChromeRAG under the MIT license; version 0.1.5 is archived at Zenodo (doi: [ZENODO-DOI-0.1.5]). Evaluation folders: `evaluations/2026-11-final/` (protocol, rubric, page lists, results for the WCXB test split, CRAG, the 296 new pages, AI judges on the human set, revision rows, held-out ledger, post hoc analyses, supplementary tables S1–S9 in `SUPPLEMENT.md`) and `evaluations/2026-10-v0.1.3/` (strict split manifest, strict cross-validation and ablation, the v0.1.3–v0.1.4 held-out ledger and round hashes). The rating app and analyzer are in `evaluators/`; pseudonymized human ratings and the label key are in `evaluations/2026-11-final/human_set_ratings/`, and post hoc analyses in `evaluations/2026-11-final/results/human_set_analysis/` and `results/posthoc_round2/`. WCXB (CC-BY-4.0) and CRAG (CC BY-NC 4.0) are obtained from their authors' releases. Third-party HTML pages are not redistributed. The raw HTML of the 296 new pages was not retained; their URLs, HTML and output hashes and the judgments are published, and a new fetch would return different pages. Per-question CRAG labels were not kept, so CRAG intervals are quoted from the result files.

---

## Ethics statement

The human rating study involved five adult unpaid volunteers, recruited from the author's professional network, who rated text extracted from public web pages. Each rater received a study note with the rating package and read it before rating. The note explained the task and that participation was voluntary and could be withdrawn. Each rater confirmed by email that they agreed to take part and to be named in the acknowledgments; the study note they had read stated that ratings would be published under a neutral code. For most raters, these email confirmations were received after they had rated. Raters are not authors. Raters also described their background and experience; these answers are kept private and are not published. Published rating files use neutral codes and hold no names and no start or end times. Pages shown to raters were saved offline with links, images and scripts removed. The author is an independent researcher without an institutional review board, and no formal ethics review was sought. All five raters stated that they used no AI tool while rating.

---

## Declaration of generative AI and AI-assisted technologies in the manuscript preparation process

During the preparation of this work the author used Claude models (Anthropic) to assist with software development, code review, analysis scripts, checking reported numbers against result files, and drafting and editing the manuscript, supplement and response letter. A separate Claude agent made one of the two safety reviews of the web addresses and pages shown to human raters (Grok made the other), and a Claude model coded the post hoc error analysis of the human-rated pages after unblinding. Grok (xAI) models also wrote and reviewed code and reviewed the raters' practice notes, Gemini (Google) models reviewed code and the protocol, and part of the code was written with a coding model offered in a third-party coding-agent tool. Language models are also components of the evaluation: OpenAI gpt-5.6-luna as a blind pairwise page judge and as the answer and grading model of the CRAG test, and grok-4.5 and gemini-4-argon-medium as additional page judges on the human-rated pages, run through that third-party tool, whose settings the author could not control: the "medium" reasoning level is the model variant selected in the tool, and whether it was applied, the temperature and other settings could not be set or verified (Table S2). GPT also judged repeatedly during v0.1.4 development, and its reasons may have guided fixes. No Claude model served as a judge in any comparison reported in this version; the v0.1.4 Claude-judged results are superseded. Prompts, settings and verdicts are published with the repository. After using these tools, the author reviewed and edited the content as needed and takes full responsibility for the content of the published article.

---

## Acknowledgements

The author thanks the five volunteer raters, Vinod Kumar Reddy Veerapuram, Devi Chandana, Anil Kumar Mangalparthi, Satish Mahadevan and Dinesh Reddy Musani, and the three reviewers, whose comments led to the stricter evaluation reported here. The retry signal for collapsed output was adapted from a design described for rs-trafilatura.

---

## References

[1] Lewis P, Perez E, Piktus A, Petroni F, Karpukhin V, Goyal N, et al. Retrieval-augmented generation for knowledge-intensive NLP tasks. Advances in Neural Information Processing Systems 2020;33:9459–74. arXiv:2005.11401.

[2] Foley M. WCXB: a multi-type web content extraction benchmark. arXiv:2605.21097, v1, 20 May 2026. https://doi.org/10.48550/arXiv.2605.21097. Data: https://doi.org/10.5281/zenodo.19316874 (CC-BY-4.0).

[3] Kohlschütter C, Fankhauser P, Nejdl W. Boilerplate detection using shallow text features. Proc 3rd ACM Int Conf Web Search and Data Mining (WSDM '10), 2010, p. 441–50. https://doi.org/10.1145/1718487.1718542.

[4] Peters ME, Lecocq D. Content extraction using diverse feature sets. Proc 22nd Int Conf World Wide Web (WWW '13 Companion), 2013, p. 89–90. https://doi.org/10.1145/2487788.2487828.

[5] Vogels T, Ganea O-E, Eickhoff C. Web2Text: deep structured boilerplate removal. Advances in Information Retrieval (ECIR 2018), LNCS, 2018, p. 167–79. https://doi.org/10.1007/978-3-319-76941-7_13.

[6] Leonhardt J, Anand A, Khosla M. Boilerplate removal using a neural sequence labeling model. Companion Proc The Web Conf 2020 (WWW '20), 2020, p. 226–9. https://doi.org/10.1145/3366424.3383547.

[7] Liu M, Peng J, Ning W, Chu P, Qiu J, Ma R, et al. Dripper: token-efficient main HTML extraction with a lightweight LM. arXiv:2511.23119, v3, 18 August 2026. https://doi.org/10.48550/arXiv.2511.23119.

[8] Wang F, Shi Z, Wang B, Wang N, Xiao H. ReaderLM-v2: small language model for HTML to Markdown and JSON. arXiv:2503.01151, 2025. https://doi.org/10.48550/arXiv.2503.01151.

[9] Pomikálek J. Removing boilerplate and duplicate content from web corpora [PhD thesis]. Brno: Masaryk University, Faculty of Informatics; 2011. Software: jusText, https://github.com/miso-belica/jusText [accessed 20 November 2026].

[10] Baburov Y, et al. python-readability (readability-lxml), version 0.9. GitHub, https://github.com/buriy/python-readability [accessed 20 November 2026].

[11] Barbaresi A. Trafilatura: a web scraping library and command-line tool for text discovery and extraction. Proc ACL-IJCNLP 2021: System Demonstrations, 2021, p. 122–31. https://doi.org/10.18653/v1/2021.acl-demo.15.

[12] Bevendorff J, Gupta S, Kiesel J, Stein B. An empirical comparison of web content extraction algorithms. Proc 46th Int ACM SIGIR Conf, 2023, p. 2594–603. https://doi.org/10.1145/3539618.3591920.

[13] Foley M. rs-trafilatura: web content extraction in Rust with page-type classification, version 0.1.1. GitHub, https://github.com/Murrough-Foley/rs-trafilatura [accessed 20 November 2026].

[14] Microsoft. MarkItDown, version 0.1.7. GitHub, https://github.com/microsoft/markitdown [accessed 20 November 2026].

[15] Crawl4AI. GitHub, https://github.com/unclecode/crawl4ai [accessed 20 November 2026].

[16] Tan J, Dou Z, Wang W, Wang M, Chen W, Wen J-R. HtmlRAG: HTML is better than plain text for modeling retrieved knowledge in RAG systems. Proc ACM Web Conf 2025 (WWW '25), 2025, p. 1733–46. https://doi.org/10.1145/3696410.3714546.

[17] BoilerPy3, version 1.0.7 (Python port of Boilerpipe). GitHub, https://github.com/jmriebold/BoilerPy3 [accessed 20 November 2026].

[18] Weinberger K, Dasgupta A, Langford J, Smola A, Attenberg J. Feature hashing for large scale multitask learning. Proc 26th Int Conf Machine Learning (ICML), 2009, p. 1113–20. https://doi.org/10.1145/1553374.1553516.

[19] Peddapudi BC. ChromeRAG, version 0.1.5. Zenodo, 2026. https://doi.org/[ZENODO-DOI-0.1.5] (all versions: https://doi.org/10.5281/zenodo.22970289). Source: https://github.com/pedapudibhargav/ChromeRAG.

[20] Bar-Yossef Z, Rajagopalan S. Template detection via data mining and its applications. Proc 11th Int World Wide Web Conf (WWW), 2002, p. 580–91. https://doi.org/10.1145/511446.511522.

[21] Yi L, Liu B, Li X. Eliminating noisy information in web pages for data mining. Proc 9th ACM SIGKDD Int Conf Knowledge Discovery and Data Mining, 2003, p. 296–305. https://doi.org/10.1145/956750.956785.

[22] Yang X, Sun K, Xin H, Sun Y, Bhalla N, Chen X, et al. CRAG – Comprehensive RAG benchmark. Advances in Neural Information Processing Systems 37 (NeurIPS 2024), Datasets and Benchmarks Track, 2024. arXiv:2406.04744. https://doi.org/10.48550/arXiv.2406.04744.
