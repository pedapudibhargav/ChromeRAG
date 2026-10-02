# ChromeRAG Corpus Comparison (185 fetched / 185 listed)

Corpus URLs listed: **185**  
Pages fetched/available: **185**  
Scoreable (input DOM has ≥ 50 main-content anchors): **177**  
Thin / excluded from means: **8**

> The scoreable cohort is defined from the input HTML only (main-content 5-gram anchors), never from any extractor's output, so every tool is averaged over the same tool-independent page set. Thin pages are mostly unrendered JS shells or empty landmarks; callers must render those first. Means over all fetched pages are reported below as well.

## Baselines

ChromeRAG (balanced / coverage / precision) vs Trafilatura, Readability, MarkItDown, markdownify, html2text, BeautifulSoup text.

## Metrics

- **Recall (content_recall)** — fraction of main-content text anchors kept. Higher = fewer lost relevant chunks.
- **Noise ret (noise_retention)** — fraction of nav/footer chrome anchors kept. Lower = cleaner vectors.
- **Fbal (f_balanced)** — harmonic-style score balancing high recall and low noise.

## Leaderboard (scoreable pages)

| Method | Pages | Recall ↑ | Noise ret ↓ | Fbal ↑ | Avg tokens |
|---|---:|---:|---:|---:|---:|
| `chromerag_coverage` | 177 | 0.635 | 0.001 | 0.759 | 1579 |
| `html2text` | 177 | 0.731 | 0.220 | 0.740 | 7553 |
| `markdownify` | 177 | 0.739 | 0.263 | 0.724 | 7416 |
| `markitdown` | 177 | 0.739 | 0.263 | 0.723 | 6645 |
| `chromerag` | 177 | 0.582 | 0.001 | 0.717 | 1398 |
| `trafilatura` | 177 | 0.546 | 0.008 | 0.680 | 1246 |
| `chromerag_precision` | 177 | 0.483 | 0.001 | 0.628 | 1114 |
| `readability` | 177 | 0.410 | 0.004 | 0.512 | 890 |
| `beautifulsoup_text` | 177 | 0.803 | 0.881 | 0.167 | 3029 |

## All fetched pages (no cohort filter, n=185)

| Method | Pages | Recall ↑ | Noise ret ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `html2text` | 185 | 0.742 | 0.214 | 0.749 |
| `chromerag_coverage` | 185 | 0.629 | 0.002 | 0.748 |
| `markdownify` | 185 | 0.751 | 0.257 | 0.733 |
| `markitdown` | 185 | 0.750 | 0.257 | 0.732 |
| `chromerag` | 185 | 0.579 | 0.002 | 0.707 |
| `trafilatura` | 185 | 0.561 | 0.013 | 0.684 |
| `chromerag_precision` | 185 | 0.478 | 0.002 | 0.617 |
| `readability` | 185 | 0.425 | 0.003 | 0.522 |
| `beautifulsoup_text` | 185 | 0.812 | 0.874 | 0.175 |

## Paired bootstrap (scoreable pages, 95% CI of mean difference)

| Comparison | Metric | Mean diff | 95% CI |
|---|---|---:|---:|
| `chromerag_coverage` − `trafilatura` | f_balanced | +0.079 | [+0.050, +0.107] |
| `chromerag_coverage` − `trafilatura` | content_recall | +0.089 | [+0.058, +0.119] |
| `chromerag_coverage` − `trafilatura` | noise_retention | -0.007 | [-0.019, +0.000] |
| `chromerag` − `trafilatura` | f_balanced | +0.036 | [+0.007, +0.064] |
| `chromerag` − `trafilatura` | content_recall | +0.036 | [+0.004, +0.067] |
| `chromerag` − `trafilatura` | noise_retention | -0.007 | [-0.018, -0.000] |
| `chromerag_coverage` − `markitdown` | f_balanced | +0.036 | [+0.009, +0.063] |
| `chromerag_coverage` − `markitdown` | content_recall | -0.104 | [-0.130, -0.079] |
| `chromerag_coverage` − `markitdown` | noise_retention | -0.261 | [-0.286, -0.238] |

## By page category (ChromeRAG vs Trafilatura vs MarkItDown)

### `homepage`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 41 | 0.607 | 0.001 | 0.739 |
| `chromerag` | 41 | 0.563 | 0.001 | 0.705 |
| `markitdown` | 41 | 0.681 | 0.244 | 0.703 |
| `trafilatura` | 41 | 0.433 | 0.007 | 0.572 |

### `pricing`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `markitdown` | 30 | 0.724 | 0.275 | 0.705 |
| `chromerag_coverage` | 30 | 0.574 | 0.000 | 0.701 |
| `trafilatura` | 30 | 0.540 | 0.004 | 0.668 |
| `chromerag` | 30 | 0.489 | 0.000 | 0.624 |

### `product`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 106 | 0.663 | 0.002 | 0.783 |
| `chromerag` | 106 | 0.616 | 0.002 | 0.747 |
| `markitdown` | 106 | 0.765 | 0.266 | 0.736 |
| `trafilatura` | 106 | 0.592 | 0.010 | 0.726 |

