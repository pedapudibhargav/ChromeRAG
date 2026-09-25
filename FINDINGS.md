# Benchmark findings — ChromeRAG

**Package:** `chromerag` 0.1.2 · results in `docs/data/corpus_comparison_summary.md`

## Evaluation design

| Item | Value |
|------|-------|
| Corpus URLs listed | 367 unique URLs in `poc/corpus_urls.json` |
| Pages fetched | 268 unique pages (plain HTTP, no JavaScript rendering; each final URL scored once) |
| Scoreable pages | 242 (input DOM has ≥ 50 main-content 5-gram anchors; tool-independent) |
| Baselines | Trafilatura, Readability, MarkItDown, markdownify, html2text, BeautifulSoup |
| Primary metrics | content_recall, noise_retention, f_balanced |
| Uncertainty | paired bootstrap 95% CIs (2,000 resamples) |

## Main results (242 scoreable pages)

- ChromeRAG coverage Fbal 0.788 vs Trafilatura 0.739 (+0.049, CI [+0.021, +0.079]); the gain is
  recall — noise retention does not differ significantly from Trafilatura.
- Vs MarkItDown: equal recall (−0.003, CI [−0.025, 0.017]) with far less chrome
  (noise −0.243, CI [−0.266, −0.220]); median output 820 vs 3,436 tokens.
- Page-level wins vs Trafilatura are balanced (103 vs 109, 30 ties with |ΔFbal| ≤ 0.01); the mean gap comes from
  Trafilatura losing most content (recall < 0.2) on 25 pages vs 13 for ChromeRAG.
- All 268 fetched pages (no filter): 0.747 vs 0.696 vs 0.661.

## Honesty notes

- The benchmark runs single-page extraction only; no STCE site model is applied.
- DVDF uses a lexical feature-hashing embedding, not a neural sentence encoder.
- Thin pages (26): 7 JS shells, 1 other thin, 18 with too few landmark anchors
  (`python scripts/revalidate_corpus.py`).
- v0.1.1 fixed a pruning bug (class tokens such as `has-sidebar` deleted whole article bodies);
  22 pages improved, none regressed, baselines unchanged.
- v0.1.2 scores each final URL once: 8 pages had been fetched under two ids (e.g. `stripe-payments`
  and `stripe-docs-payments`). Removing them changed every published mean by at most 0.005.
- v0.1.2 hardened STCE after running it on real sites (benchmark site groups, then a crawl of up to
  15 pages per documentation site): a CSS-in-JS or utility class shared by chrome and content
  deleted articles, code samples and link lists; a URL fetched twice or a page published for
  several versions made content look like template. Matches must now be near their learned size,
  must not wrap `<main>` or most of the page, and must carry the learned text or explicit chrome
  markup; learned blocks must repeat their text; duplicate and near-duplicate pages count once.
- Result (`python -m poc.run_stce_eval [--raw data/stce_crawl]`): benchmark sites recall
  0.714 → 0.714; crawl (125 sites, 1,727 scored pages) Fbal 0.851 → 0.852, recall 0.770 → 0.769,
  site-repeated text 3.1% → 3.0% (Trafilatura 2.1%, MarkItDown 34.9%). The 17 pages losing more
  than 0.05 recall are on three sites that place feedback widgets or promotions inside `<main>`.
