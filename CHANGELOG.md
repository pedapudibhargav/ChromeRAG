# Changelog

All notable changes to ChromeRAG. Versions follow [Semantic Versioning](https://semver.org/).

## 0.1.4 — 2026-10-03

Output-quality release: better structure, much less leftover chrome, heading-aware chunks. The learned model file is unchanged.

### Added
- **Chunks for vector databases.** `result.chunks()` (and `chromerag extract --chunks`, JSON lines) splits the Markdown into
  heading-aware chunks with a heading path and `embed_text`; code blocks and tables are never cut. Prepending the heading path raised
  dense MRR from 0.853 to 0.913 on 400 held-out questions.
- **Markdown tables.** Rectangular tables are written as GitHub pipe tables (`PipelineConfig(table_format="linearized")` or
  `--table-format linearized` restores key-value rows).
- **Generic chrome detectors** (`generic_chrome.py`): in-page tables of contents, pagers, comment sections of articles, related-post
  blocks, call-to-action buttons, share strips, newsletter blocks, author boxes, template placeholders, footer-like page tails and
  attribute residue; one flag per detector (`chrome_drop_*`, `chrome_trim_tail`).
- **16 rules adapted from Trafilatura's discard patterns** (`rules/trafilatura_inspired.yaml`, Apache-2.0, credited in `NOTICE`),
  15 documentation-framework rules (Docusaurus, MkDocs, Starlight, VitePress, Mintlify, Cloudflare, Grafana, DigitalOcean), and two
  density passes (`trafilatura_link_blocks`, `trafilatura_micro`).
- Evaluation: frozen fresh-page seed lists (`poc/extra_seeds*.json`, `poc/extra_corpus.py`), blinded judge builder and aggregator
  (`poc/claude_judge_build.py`, `poc/claude_judge_aggregate.py`), a GPT judge (`poc/gpt_judge_batches.py`), a heading-context retrieval study
  (`poc/heading_context_eval.py`), `--no-lbc`, `MANIFEST.in`, NOTICE in the wheel, `load_split(..., drop_leaked=True)`.

### Changed
- The page title (`h1`), a heading above kept content and the lead paragraph under the title are kept whatever the classifier says.
- Code blocks keep their lines; ordered lists keep their numbers and nested lists their nesting.
- The `<header>` of an `<article>` that holds the page `h1` is content, not chrome.
- Median extraction time is about 52 ms per page on 200 stored pages (0.1.3: about 36 ms), the cost of the new rules; a page nested 20,000 levels deep takes about 2 s.
- Word-level F1 on the 372 WCXB test pages absent from the development folder: 0.907 (0.903 in 0.1.3); blinded judges on 328 fresh pages
  prefer the output to Trafilatura's (net +0.41 Claude, +0.19 GPT, +0.45 Gemini).

### Fixed
- Pages whose layout wrapped everything in custom elements (`<app-root>`, `<awsdocs-view>`) were written as one text blob; the Markdown writer now keeps
  their blocks.
- A `<table>` without rows no longer raises `IndexError`.
- Pages nested thousands of levels deep no longer raise `RecursionError` (explicit stack in the block finder) and no longer take quadratic
  time in the Markdown writer.
- `chromerag batch` records an error for a page that fails and carries on; it exits with code 1 at the end.
- `learn`/`batch` no longer slow down quadratically on unclosed `<script>` tags.
- Files and bytes are decoded with the declared encoding (`<meta charset>`, byte-order mark, detection); `extract()` accepts bytes.
- The retrain commands agree on one path; `pip install "chromerag[train]"` pins scikit-learn; README documents WCXB.

## 0.1.3 — 2026-10-02

### Added
- **Learned block filter.** Each text block is scored by gradient-boosted trees (150 KB model file,
  NumPy-only inference); the threshold depends on the content priority. On pages from sites the model
  never saw (WCXB dev, 5-fold site-grouped cross-validation) word-level F1 is 0.85 against 0.82 for
  Trafilatura, 0.70 for Readability and 0.51 for MarkItDown; on the 511 held-out WCXB test pages it is 0.902
  against 0.860, 0.763 and 0.540.
- LlamaIndex reader (`chromerag.integrations.llamaindex.ChromeRAGReader`), next to the LangChain loader.
- YAML rule index (`src/chromerag/rules/`) with evidence and a fixture per rule; `--explain` shows which
  rule removed what.
- Per-call configuration; hidden nodes and skip links are removed; content-root ladder.
- Training and analysis tools: `poc/lbc_data.py`, `poc/train_lbc.py`, `poc/wcxb_diag.py`,
  `poc/wcxb_cv_report.py`, `poc/learn_tokens.py`, `poc/bench_speed.py`, `poc/golden.py`.

- `diagnostics["lbc"]` with the model's expected precision, recall and F1; a warning below expected F1 0.70.
- Text between block elements is wrapped into blocks so it is no longer lost.

### Changed
- Markdown follows document order (it was written breadth-first before).
- Link targets are not written by default; use `include_links=True` or `--links`.
- Repeated blocks are written once.
- Layout tables are unwrapped instead of being linearised (nested layout tables used to repeat text).
- A page-wide `<form>`, an unclosed `<button>` or a large `<noscript>` keeps its content.
- Median extraction time is about 36 ms per page on 200 stored pages (0.1.2: about 78 ms).

### Fixed
- Crash on a decomposed anchor in skip-link removal.
- Content after a stray `</html>` is no longer lost.
- The inferred page type no longer leaks from one `extract()` call to the next.

## 0.1.2 — 2026-09-24
Safe site-template learning, retrieval and crawl evaluations, one-page results site, PyPI smoke test.

## 0.1.1
First public release.
