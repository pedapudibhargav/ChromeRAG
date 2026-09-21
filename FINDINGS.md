# POC Findings — ChromeRAG

Date: 2026-09-20  
**Package:** `chromerag` (install from source: `pip install -e .`)

## Evaluation design

| Item | Value |
|------|-------|
| Corpus URLs listed | 373 in `poc/corpus_urls.json` |
| Pages fetched | 277 |
| Scoreable pages | 238 (ChromeRAG recall ≥ 0.05) |
| Page types | docs, pricing, marketing, wiki, hub, news, article, cloud |
| Baselines | Trafilatura, Readability, MarkItDown, markdownify, html2text, BeautifulSoup |
| Primary metrics | content_recall, noise_retention, f_balanced |
| Secondary | optional LLM 1–5 rubric (`poc/run_llm_eval.py`) |

## Leaderboard (latest)

See `docs/data/corpus_comparison_summary.md` and the Results page on GitHub Pages.

## Notes

- Empty JS shells are excluded via the scoreable filter (not a ChromeRAG failure mode we claim to solve without a renderer).
- MarkItDown matches markdownify-like recall but retains far more chrome (higher noise_retention) — ChromeRAG’s edge is noise strip for RAG vectors.
- `chromerag extract` / `batch` emit `WARNING:` on thin / JS-shell HTML; `--fail-on-thin` exits 3.

## Evaluation honesty

- **JS shells:** ChromeRAG does not render JavaScript; thin extracts are expected without a caller-side browser. Callers must Playwright-render first.
- **Scoreable filter:** 373 listed → 277 fetched → 238 scoreable → 39 thin (recall gate ≥ 0.05). Of the 39 thin: ~7 JS-shell-like, ~31 visible-but-unscoreable, ~1 other thin (`scripts/revalidate_corpus.py`). Leaderboard means use the scoreable set only.
- Revalidate: `python scripts/revalidate_corpus.py`
- See `docs/limitations.html` and draft §4.1.
