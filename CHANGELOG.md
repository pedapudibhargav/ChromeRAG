# Changelog

All notable changes to ChromeRAG. Versions follow [Semantic Versioning](https://semver.org/).

## 0.1.5 — 2026-11-20

Strict-retrain and validation release. Code frozen at tag `freeze-0.1.5` before any held-out run; the results cited by
the SoftwareX revision are in `evaluations/2026-11-final/`.

### Changed
- **Strict retrain.** `assets/lbc_stage1.npz` (152,432 bytes) is retrained on a strict subset of the WCXB development
  folder: the 139 files that duplicate test pages and the 96 pages whose registrable domain (Public Suffix List) occurs
  in the test split are removed, plus a fixed 0.8 Jaccard near-duplicate guard against test reference text; 1,238
  pages remain. No test page, test domain, test label or test score is used. A test asserts that no training domain is
  a test domain; `poc/rebuild_strict.sh` rebuilds the model byte for byte.
- Cross-validation folds and site-level bootstrap group pages by registrable domain (`poc/psl.py`), not hostname.
- **Components dropped after the ablation** (five folds grouped by domain on the 1,238 strict pages; a component was
  dropped when removing it neither lowered F1 nor raised the without-snippet rate):
  - five Trafilatura-derived rule groups: `tf.share` (`sociable`, `viral`), `tf.related` (`teaser`, `popular`),
    `tf.newsletter.block`, `tf.ads` (`outbrain`, `taboola`), `tf.tools.print`; 8 Trafilatura-derived rules remain,
    13 YAML rules in all;
  - the 15 documentation-framework YAML rules (`docs_generators.yaml`); the last ablation run that still included
    them is commit `7ca7e9e`;
  - the pager and related-post detectors, now off by default (`chrome_drop_pager=False`,
    `chrome_drop_related=False`).
  Structure rules and table rescue were kept as disclosed exceptions (removing them lost content on some pages); a
  stacked second-stage model was not shipped (ten times the file size for +0.004 F1).
- Pinned the `[train]` extra to scikit-learn 1.9.x (training environment used 1.9.1).

### Added
- **Switches for every stage** (`PipelineConfig`): `enable_generic_chrome`, `enable_chrome_prune`,
  `enable_trafilatura_rules`, `enable_lbc_structure_rules`, `enable_lbc_stage2`, `lbc_rescue_tables`,
  `lbc_rich_collapsed_retry`; existing `enable_lbc`, `enable_rules` and the per-detector `chrome_*` flags unchanged.
- **Table rescue.** Data tables under a kept section heading are kept even when the classifier scores them low (for
  example plan and price tables); `diagnostics["lbc"]["tables_rescued"]` counts them.
- **Empty-output rescue.** Main content hidden by CSS (`visibility:hidden`, off-canvas wrappers) is kept when it holds
  most of the page text, while hidden cookie modals, mega menus and off-canvas navigation stay removed; collapsed
  outputs are retried in coverage mode, and broken list shells around `<main>` are walked.
- **Collapse signal.** Besides the old word-count test, a collapsed extraction is now also detected from a low share
  of kept blocks, a low per-page F1 estimate, or two high-scoring content regions with little output; such pages are
  retried in coverage mode (`collapse.py`, switch `lbc_rich_collapsed_retry`). The idea of checking richer thin-output signals
  comes from a design described for rs-trafilatura; it was implemented independently.
- **CI workflow** `.github/workflows/ci.yml`: `ruff check .` and `pytest -q` on Linux, macOS and Windows with
  Python 3.11 and 3.13 on every push and pull request; cross-platform test fixes (URL path keys, LF line endings in
  golden files).
- **Evaluation kit** `evaluators/`: an offline, standard-library blind rating app (outputs labelled A, B, C in random
  order, difference highlighting, practice items with notes, repeats), bundle builder, part splitter, pseudonymizer
  and an analyzer that applies the pre-registered careless-rating checks.
- **Held-out ledger**: `poc/held_out_ledger.py`, `evaluations/2026-10-v0.1.3/HELD_OUT_LEDGER.csv` (every v0.1.3 and
  v0.1.4 run on a held-out or later-held-out set) and `evaluations/2026-11-final/results/held_out_runs.jsonl`.
- Evaluation harnesses for the revision: `poc/strict_split.py`, `poc/run_strict_dev_cv.py`, `poc/ablation_cv.py`,
  `poc/update_strict_manifest.py`, `poc/final_wcxb.py`, `poc/revision_rows.py` (raw and stripped output, subsets,
  page types, freeze-0.1.3 code with the 0.1.5 model, jusText, BoilerPy3, speed), `poc/crag_answer_eval.py`,
  `poc/final_page_judge.py`, `poc/final_page_length_analysis.py`, and the pre-registered human rating analysis
  `poc/human_set_analysis.py` with `poc/human_set_score_diff.py`, `poc/human_set_ai_by_forum.py` and
  `poc/gen_supplement.py`.

### Fixed
- Emphasis: whitespace-only emphasis keeps word separation; adjacent bold tags no longer glue markers; literal
  asterisks in `pre` and inline code are not broken.
- Word breaks: `<br>`-like break spans separate sentences that were joined.
- A duplicate page `h1` is written once.
- Tables: empty columns are omitted, spacer rows no longer block a pipe table, a blank header row no longer emits a
  separator-only table, a pipe table inside a list keeps its header above the separator, large tables keep every row
  (a single warning when a cap applies).
- Term lists (`<dl>`) keep all terms and definitions, including consecutive `<dt>` and paragraph `<dd>`; figures that
  wrap content keep the content; captions are kept.
- Warnings: the JavaScript-shell warning is cleared when the body has prose; the empty-body warning counts body words,
  not front-matter tokens.
- Rules never drop `html`, `body`, `main` or the content root.
- Crash and time safety: deep emphasis and list nesting and lone surrogates no longer raise; pathological inputs
  finish in under two seconds.
- An article header inside a card river is no longer pruned as site chrome.

### Results (evaluations/2026-11-final)
- WCXB test split, 511 pages: word F1 0.884 (balanced, front matter removed) against 0.860 for Trafilatura 2.2.0,
  +0.024 [+0.008, +0.042]; raw default output 0.853. The test split was consulted during earlier development.
- Human raters on 75 new pages: net +0.23 [+0.01, +0.42] against Trafilatura; CRAG split 1: no measurable difference
  in answer accuracy (+0.008 [−0.040, +0.054]) from an index about 17% smaller.
- Median time per page about 40 ms (Trafilatura about 14 ms) on the WCXB test pages, one process on a loaded machine.
- The v0.1.4 results below (0.907 on 372 pages, 52 ms, LLM-judge panels) are superseded.

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
