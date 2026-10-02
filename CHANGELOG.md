# Changelog

All notable changes to ChromeRAG. Versions follow [Semantic Versioning](https://semver.org/).

## Unreleased (0.1.3)

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
- Docker: `Dockerfile.apt` for networks where PyPI is blocked.

- `diagnostics["lbc"]` with the model's expected precision, recall and F1; a warning below expected F1 0.70.
- Text between block elements is wrapped into blocks so it is no longer lost.

### Changed
- Markdown follows document order (it was written breadth-first before).
- Link targets are not written by default; use `include_links=True` or `--links`.
- Repeated blocks are written once.
- Layout tables are unwrapped instead of being linearised (nested layout tables used to repeat text).
- A page-wide `<form>`, an unclosed `<button>` or a large `<noscript>` keeps its content.
- Median extraction time is about 29 ms per page (0.1.2: about 75 ms).

### Fixed
- Crash on a decomposed anchor in skip-link removal.
- Content after a stray `</html>` is no longer lost.
- The inferred page type no longer leaks from one `extract()` call to the next.

## 0.1.2 — 2026-09-24
Safe site-template learning, retrieval and crawl evaluations, one-page results site, PyPI smoke test.

## 0.1.1
First public release.
