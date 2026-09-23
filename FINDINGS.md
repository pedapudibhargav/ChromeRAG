# Benchmark findings — ChromeRAG

**Package:** `chromerag` 0.1.1 · results in `docs/data/corpus_comparison_summary.md`

## Evaluation design

| Item | Value |
|------|-------|
| Corpus URLs listed | 373 in `poc/corpus_urls.json` |
| Pages fetched | 277 (plain HTTP, no JavaScript rendering) |
| Scoreable pages | 250 (input DOM has ≥ 50 main-content 5-gram anchors; tool-independent) |
| Baselines | Trafilatura, Readability, MarkItDown, markdownify, html2text, BeautifulSoup |
| Primary metrics | content_recall, noise_retention, f_balanced |
| Uncertainty | paired bootstrap 95% CIs (2,000 resamples) |

## Main results (250 scoreable pages)

- ChromeRAG coverage Fbal 0.791 vs Trafilatura 0.740 (+0.051, CI [+0.025, +0.081]); the gain is
  recall — noise retention does not differ significantly from Trafilatura.
- Vs MarkItDown: equal recall (−0.001, CI [−0.023, 0.020]) with far less chrome
  (noise −0.246, CI [−0.269, −0.222]); median output 825 vs 3,505 tokens.
- Page-level wins vs Trafilatura are balanced (106 vs 111, 33 ties); the mean gap comes from
  Trafilatura losing most content (recall < 0.2) on 26 pages vs 13 for ChromeRAG.
- All 277 fetched pages (no filter): 0.752 vs 0.698 vs 0.661.

## Honesty notes

- The benchmark runs single-page extraction only; no STCE site model is applied.
- DVDF uses a lexical feature-hashing embedding, not a neural sentence encoder.
- Thin pages (27): 7 JS shells, 1 other thin, 19 with too few landmark anchors
  (`python scripts/revalidate_corpus.py`).
- v0.1.1 fixed a pruning bug (class tokens such as `has-sidebar` deleted whole article bodies);
  22 pages improved, none regressed, baselines unchanged.
