# ChromeRAG: Ingest-Time Elimination of Site Template Noise for Enterprise Web RAG

**Target journal:** Elsevier *SoftwareX* (Original Software Publication)  
**Package:** `chromerag`  
**Draft status:** Content draft for paste into the **official SoftwareX Word/LaTeX template** (mandatory; do not alter template styles). Do not submit this Markdown file as-is.

**Authors:** Bhargava Chary Peddapudi (Independent Researcher; ORCID: https://orcid.org/0009-0002-8523-8415)  
**Corresponding email:** pedapudibhargav@gmail.com

---

## Highlights

- ChromeRAG turns scraped HTML into RAG-ready Markdown with site-chrome removal.
- STCE learns recurring nav/footer chrome across a corporate domain before extract.
- On 238 scoreable pages, coverage mode reaches Fbal 0.800 vs Trafilatura 0.752.
- Thin JS shells warn the caller: render with Playwright first, then extract.
- MIT CLI + static Compare Lab; deterministic Recall / Noise / Fbal benchmarks.

---

## Abstract (~100 words)

Enterprise retrieval-augmented generation (RAG) pipelines often index scraped HTML whose navigation chrome, marketing banners, and footers pollute the vector space. Existing extractors such as Trafilatura and Readability are strong on news-like pages but under-serve SaaS documentation and pricing surfaces. **ChromeRAG** (`chromerag`) is a CPU-first Python toolkit that converts HTML to RAG-ready Markdown using site-template chrome elimination (STCE), optional density/vector noise pruning (DVDF), Schema.org front-matter fusion, and table key-value linearization. On a public corpus (373 URLs listed; 277 fetched; 238 scoreable), ChromeRAG coverage mode reaches Fbal 0.800 versus Trafilatura 0.752 and MarkItDown 0.695. Thin or JavaScript-shell inputs emit operator warnings so callers can verify their fetch/render pipeline rather than silently averaging empty pages into leaderboard means. The software is MIT-licensed with a CLI, static Compare Lab, and reproducible benchmark scripts.

**Keywords:** RAG; HTML extraction; boilerplate removal; vector pollution; Markdown; enterprise search

---

## Code metadata (Table 1 — SoftwareX OSP template v6)

| Nr | Code metadata description | Please fill in this column |
|----|---------------------------|----------------------------|
| C1 | Current code version | 0.1.0 |
| C2 | Permanent link to code/repository used for this code version | https://github.com/pedapudibhargav/ChromeRAG/tree/v0.1.0 |
| C3 | Legal Code License | MIT |
| C4 | Code versioning system used | git |
| C5 | Software code languages, tools, and services used | Python ≥3.11, BeautifulSoup4, lxml, Pydantic, optional ONNX Runtime |
| C6 | Compilation requirements, operating environments & dependencies | macOS/Linux/Windows; `pip install -e .` from GitHub clone; optional `[dvdf]`, `[fetch]`, `[baselines]`, `[ui]` |
| C7 | If available Link to developer documentation/manual | https://pedapudibhargav.github.io/ChromeRAG/ + repo `README.md` |
| C8 | Support email for questions | pedapudibhargav@gmail.com |

Filled Word file: `papers/softwarex/ChromeRAG_SoftwareX_OSP.docx` (from official OSP template).

---

## 1. Motivation and significance

Modern enterprise assistants retrieve over documentation hubs, knowledge bases, and marketing sites. When those pages are ingested with generic HTML→text converters, shared chrome (nav, footer, CTAs, cookie banners) is embedded repeatedly. The result is **vector pollution**: near-duplicate chrome chunks compete with factual content at query time.

Prior extractors optimize for news article main-content (Trafilatura, Readability) or general Markdown conversion (MarkItDown, markdownify). They do not jointly provide: (i) learn-then-extract site chrome models across a corporate domain, (ii) Schema.org JSON-LD injected as YAML front-matter for chunk context, and (iii) pricing/spec table linearization for RAG. ChromeRAG targets that gap as **ingest-time, query-agnostic** software—orthogonal to query-time HtmlRAG pruning.

Scientific and engineering discovery increasingly depends on assistants grounded in organizational web corpora. A reusable, CPU-first ingest component that reduces chrome pollution improves retrieval faithfulness without requiring GPU extractors or query-time HTML pruning. SoftwareX is an appropriate venue because the contribution is a citable, inspectable toolkit with a clear scope boundary and reproducible evaluation scripts.

---

## 2. Software description

### 2.1 Software architecture

```
HTML string
  → input-quality check (warn on thin / JS shells)
  → schema harvest (JSON-LD / Microdata) BEFORE script strip
  → deterministic clean + optional STCE (learned site chrome)
  → density / DVDF leaf prune (optional ONNX MiniLM)
  → heading-safe Markdown + YAML front-matter
  → optional table key-value linearization
```

**Scope boundary:** ChromeRAG owns HTML→Markdown. Fetching, Playwright rendering, crawl concurrency, and rate limits belong to the caller (or the `poc/` harness). When the input looks like an unrendered SPA shell, ChromeRAG still returns Markdown but prints `WARNING:` lines (and optional `--fail-on-thin`) so operators can fix the upstream pipeline.

### 2.2 Software functionalities

| Feature | CLI / API | Notes |
|---------|-----------|-------|
| Extract | `chromerag extract page.html -o out.md` | `--priority {precision,coverage,balanced}` |
| Input warnings | stderr + `result.warnings` | JS shell / thin HTML detection |
| Learn chrome | `chromerag learn data/raw -o site.json` | STCE model from multi-page corpus |
| Batch | `chromerag batch data/raw -o data/outputs --chrome-model site.json` | Flags thin pages in summary |
| DVDF | optional `[dvdf]` extra | ONNX MiniLM noise-anchor cosine prune |
| Compare Lab | `docs/` static site | GitHub Pages–safe relative routing |

### 2.3 Sample code snippets

```bash
pip install -e ".[dvdf,baselines]"
chromerag learn data/raw -o data/chrome_models/site.json --min-pages 3
chromerag batch data/raw -o data/outputs --chrome-model data/chrome_models/site.json --priority coverage
python -m poc.run_corpus_comparison --no-fetch
```

```python
from chromerag import ChromeRAG, PipelineConfig, ContentPriority

result = ChromeRAG(
    config=PipelineConfig.from_priority(ContentPriority.BALANCED)
).extract(html, url="https://example.com/docs")
md, meta = result.markdown, result.front_matter
for warning in result.warnings:
    print("WARNING:", warning)  # e.g. caller must Playwright-render first
```

---

## 3. Illustrative examples

### 3.1 Multi-tool corpus comparison

On **238 scoreable** pages (from 277 fetched; 373 URLs listed; docs / pricing / marketing / wiki / hub / news / article / cloud):

| Method | Recall ↑ | Noise ret ↓ | Fbal ↑ |
|--------|--------:|------------:|-------:|
| chromerag_coverage | 0.701 | 0.005 | **0.800** |
| chromerag (balanced) | 0.678 | 0.005 | 0.783 |
| trafilatura | 0.662 | 0.019 | 0.752 |
| markitdown | 0.702 | 0.261 | 0.695 |
| readability | 0.456 | 0.016 | 0.535 |

**Metrics:** content/chrome 5-gram anchors from `main`/`article` vs `nav`/`footer`/`header`. Full tables + per-category breakdown: `docs/data/corpus_comparison_summary.md`.

**Fig. 1** plots Fbal for the primary methods; **Fig. 2** content recall; **Fig. 3** noise retention (ChromeRAG ≈0.005 vs MarkItDown ≈0.26); **Fig. 4** shows the corpus honesty gate (listed → fetched → scoreable / thin). SVG sources: `papers/softwarex/figures/`.

### 3.2 Priority knobs and input-quality warnings

`--priority precision` trades recall for lower noise; `coverage` keeps more content tokens for recall-sensitive RAG; `balanced` is the default enterprise compromise. Passing a near-empty `<div id="root">` shell prints a stderr warning that the caller must render first—reviewers should trust that disclosure more than a table that silently averages those failures.

---

## 4. Impact

ChromeRAG is intended for practitioners who build corporate RAG corpora from HTML and need reproducible, CPU-first chrome removal without GPU extractors. Expected impact pathways:

1. **Reusable ingest component** in RAG stacks (LangChain/LlamaIndex custom loaders, Airflow/Prefect jobs).
2. **Benchmark baseline** for HTML→Markdown quality using recall / noise retention / Fbal rather than token count alone.
3. **Teaching / demos** via the static Compare Lab (`docs/`).
4. **Pipeline debugging:** input-quality warnings make fetch/render bugs visible before vectors are indexed.

### 4.1 Limitations (stated for reviewers)

SoftwareX values usable, honestly scoped tools. We therefore state where ChromeRAG does **not** claim SOTA and how evaluation avoids over-claiming.

**JavaScript-rendered empty shells.** Many modern docs/marketing sites ship an almost empty HTML shell and fill content in the browser. ChromeRAG is HTML-in / Markdown-out: it does **not** run Playwright or a headless browser. On such pages the extracted Markdown is thin or empty by design, and the API/CLI emits an explicit warning. Callers that need those pages must render first (Playwright, Puppeteer, or a crawl pipeline) and then pass the rendered HTML to ChromeRAG. Claiming high quality on unrendered shells would be fake performance.

**Scoreable-page filter in the corpus benchmark.** Of 277 fetched pages in the latest run, **238** were marked *scoreable* and **39** *thin*. A page is scoreable only if ChromeRAG `content_recall ≥ 0.05` against DOM-derived main-content anchors. Thin pages are excluded from the leaderboard averages so that empty shells and near-zero-content pages do not drag every tool’s mean toward zero and create a false “everyone fails equally” story. Revalidation classifies the 39 thin pages as approximately **7** JS-shell-like inputs, **1** other thin DOM, and **31** pages with visible text that still fail the recall gate (e.g. unusual layout / weak `main` anchors)—so the gate is a **corpus hygiene filter**, not a claim that every excluded page is a SPA shell. The filter uses ChromeRAG’s recall only as that hygiene gate; Trafilatura / MarkItDown / others are still scored on the same scoreable set. We report listed / fetched / scoreable / thin counts in the paper and on the Results site. Input-quality warnings still fire on JS shells even when a page remains in the scoreable set.

**Heuristic anchors, not human gold.** Content vs chrome anchors come from structural HTML (`main`/`article` vs `nav`/`footer`/`header`), not hand-labeled spans. This keeps comparisons extractor-independent but is an approximation. Optional LLM 1–5 judging on a stratified sample is secondary corroboration only.

**DVDF dependency.** Optional vector density filtering needs ONNX Runtime + MiniLM weights. The default CPU cascade can run with DVDF disabled.

**Not a multi-format converter.** Unlike MarkItDown, ChromeRAG does not convert PDF/Office/audio. Scope is intentional: web HTML chrome for RAG ingest.

---

## 5. Conclusions

ChromeRAG packages ingest-time chrome elimination, optional vector density pruning, schema front-matter, table linearization, and input-quality warnings into a MIT-licensed Python CLI. On 238 scoreable public pages, coverage mode reaches Fbal 0.800 vs Trafilatura 0.752 and MarkItDown 0.695, mainly by cutting chrome retention (~0.005 vs ~0.26). Future work includes page-type adaptive profiles and Chrome Centroid Drift metrics. PyPI publication is intentionally deferred until the GitHub package and SoftwareX archive are stable.

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

During the preparation of this work, the author(s) used Cursor (Grok-assisted coding agent) in order to draft software documentation structure, organize related-work notes, and polish manuscript wording. After using this tool/service, the author(s) reviewed and edited the content as needed and take(s) full responsibility for the content of the published article. AI tools used inside the research software (optional ONNX MiniLM for DVDF) are described in Methods / Software description and are not manuscript-writing tools. No generative AI was used to create SoftwareX figures; charts are produced from corpus JSON via `scripts/generate_softwarex_figures.py`.

---

## References

1. A. Barbaresi, “Trafilatura: A Web Scraping Library and Command-Line Tool for Text Discovery and Extraction,” in *Proc. ACL-IJCNLP 2021 System Demonstrations*, 2021, pp. 122–131. doi: [10.18653/v1/2021.acl-demo.15](https://doi.org/10.18653/v1/2021.acl-demo.15).
2. J. Alarte, J. Silva, and S. Tamarit, “What Web Template Extractor Should I Use? A Benchmarking and Comparison for Five Template Extractors,” *ACM Trans. Web*, vol. 13, no. 2, Art. 9, 2019. doi: [10.1145/3316810](https://doi.org/10.1145/3316810).
3. J. Tan, Z. Dou, W. Wang, M. Wang, W. Chen, and J.-R. Wen, “HtmlRAG: HTML is Better Than Plain Text for Modeling Retrieved Knowledge in RAG Systems,” in *Proc. ACM Web Conf. (WWW ’25)*, 2025. doi: [10.1145/3696410.3714546](https://doi.org/10.1145/3696410.3714546).
4. B. C. Peddapudi, *ChromeRAG*, version 0.1.0, GitHub, 2026. [Online]. Available: https://github.com/pedapudibhargav/ChromeRAG/tree/v0.1.0
5. Microsoft, *MarkItDown*: Python tool for converting files and office documents to Markdown, GitHub. [Online]. Available: https://github.com/microsoft/markitdown

---

## Paste checklist before Editorial Manager

- [x] Official SoftwareX **Word** manuscript: `ChromeRAG_SoftwareX_OSP.docx` (figures embedded)
- [ ] Article type: **Original Software Publication** (not Software Update)
- [x] Public **GitHub** with `README.md` + `LICENSE.txt`
- [x] C2 = `https://github.com/pedapudibhargav/ChromeRAG/tree/v0.1.0`
- [x] Highlights file ready: `HIGHLIGHTS.md` (paste into EM)
- [x] Competing-interests Word: `COMPETING_INTERESTS_DECLARATION.docx` (or Elsevier tool output)
- [ ] Open `.docx` in Word once → spell-check → do not change styles
- [ ] Optional 60–90s screencast (see `SCREENCAST.md`)
- [ ] Submit at https://www.editorialmanager.com/softx
- [ ] APC **only after acceptance** (not at submit)