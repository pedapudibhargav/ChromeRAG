# Baseline evaluation — ChromeRAG 0.1.2 (September 2026)

Frozen results for ChromeRAG **0.1.2** (plus the offline token-estimate fix, which does not
change any output), recorded before any further extraction changes so later versions can be
compared against it with the same protocol.

## Corpora

| Corpus | Pages | Selection |
|---|---|---|
| Documentation benchmark | 242 scoreable of 268 fetched (367 URLs) | `poc/corpus_urls.json` |
| Landing pages | 362 scoreable of 395 fetched (397 URLs), 88 companies, 10 sectors | `poc/landing_companies.json` → `poc/landing_urls.json` (homepage, pricing, product pages from each homepage's own links) |

## Protocols

- **Anchor metric** (`poc/run_corpus_comparison.py`, `poc/run_landing_eval.py`): content =
  5-grams from `<main>`/`<article>`, chrome = 5-grams from nav/header/footer/aside/cookie
  containers; recall, noise retention, F_bal; paired bootstrap, 2,000 resamples.
- **Retrieval** (`poc/run_retrieval_eval.py [--corpus landing] --dense`): ~200-word chunks;
  known-item queries (titles, headings, passages) from the input HTML; BM25 and
  `text-embedding-3-small`; hit@5 and share of chrome in the top-5 context.
- **LLM judge** (`poc/run_llm_judge.py`): `gpt-5.6-luna`, reasoning effort low, blind pairwise
  (A/B randomized, 20% re-judged swapped), 150 landing + 100 documentation pages, seed 7.
  `llm_judge_report.json` judges the Markdown body (front-matter removed);
  `llm_judge_report_with_front_matter.json` is the first run on raw output.

## Results (ChromeRAG coverage mode)

| | vs MarkItDown | vs Trafilatura |
|---|---|---|
| F_bal, documentation (242) | 0.788 vs 0.696, better | 0.788 vs 0.739, better |
| F_bal, landing (362) | 0.785 vs 0.716, better | 0.785 vs 0.659, better |
| BM25 hit@5, documentation | 0.949 vs 0.964, tie | 0.949 vs 0.922, better |
| BM25 hit@5, landing | 0.900 vs 0.926, **worse** | 0.900 vs 0.816, better |
| Dense hit@5, documentation / landing | tie / tie | tie / tie |
| Chrome in retrieved context | always lowest of the three | always lowest of the three |
| LLM judge win rate (250 pages) | **73% vs 26%, better** | **42% vs 57%, worse** |

**Main finding.** The anchor metric counts only chrome inside navigation, header, footer and
sidebar elements. Chrome placed inside the main content (calls to action, promotional and
"related resources" blocks, feedback widgets) counts as content. The LLM judge sees that
chrome, rates ChromeRAG's output as less clean than Trafilatura's (chrome-free score 3.72 vs
4.52 on a 1–5 scale; content 3.70 vs 3.84), and prefers Trafilatura. ChromeRAG keeps more
anchored content and fails less often (landing pages with recall < 0.2: 5 vs 23).

Total OpenAI cost of this study: see `openai_spend.json` (about USD 1.14).
