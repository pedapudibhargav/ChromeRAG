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
| `chromerag_coverage` | 177 | 0.616 | 0.002 | 0.741 | 1469 |
| `html2text` | 177 | 0.731 | 0.220 | 0.740 | 7553 |
| `markdownify` | 177 | 0.739 | 0.263 | 0.724 | 7416 |
| `markitdown` | 177 | 0.739 | 0.263 | 0.723 | 6645 |
| `chromerag` | 177 | 0.571 | 0.002 | 0.704 | 1327 |
| `trafilatura` | 177 | 0.546 | 0.008 | 0.680 | 1246 |
| `chromerag_precision` | 177 | 0.488 | 0.002 | 0.632 | 1085 |
| `readability` | 177 | 0.410 | 0.004 | 0.512 | 890 |
| `beautifulsoup_text` | 177 | 0.803 | 0.881 | 0.167 | 3029 |

## All fetched pages (no cohort filter, n=185)

| Method | Pages | Recall ↑ | Noise ret ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `html2text` | 185 | 0.742 | 0.214 | 0.749 |
| `markdownify` | 185 | 0.751 | 0.257 | 0.733 |
| `markitdown` | 185 | 0.750 | 0.257 | 0.732 |
| `chromerag_coverage` | 185 | 0.611 | 0.002 | 0.731 |
| `chromerag` | 185 | 0.568 | 0.002 | 0.696 |
| `trafilatura` | 185 | 0.561 | 0.013 | 0.684 |
| `chromerag_precision` | 185 | 0.489 | 0.002 | 0.627 |
| `readability` | 185 | 0.425 | 0.003 | 0.522 |
| `beautifulsoup_text` | 185 | 0.812 | 0.874 | 0.175 |

## Paired bootstrap (scoreable pages, 95% CI of mean difference)

| Comparison | Metric | Mean diff | 95% CI |
|---|---|---:|---:|
| `chromerag_coverage` − `trafilatura` | f_balanced | +0.061 | [+0.032, +0.090] |
| `chromerag_coverage` − `trafilatura` | content_recall | +0.070 | [+0.038, +0.099] |
| `chromerag_coverage` − `trafilatura` | noise_retention | -0.006 | [-0.019, +0.001] |
| `chromerag` − `trafilatura` | f_balanced | +0.024 | [-0.006, +0.052] |
| `chromerag` − `trafilatura` | content_recall | +0.024 | [-0.007, +0.054] |
| `chromerag` − `trafilatura` | noise_retention | -0.006 | [-0.017, +0.001] |
| `chromerag_coverage` − `markitdown` | f_balanced | +0.018 | [-0.011, +0.047] |
| `chromerag_coverage` − `markitdown` | content_recall | -0.123 | [-0.150, -0.097] |
| `chromerag_coverage` − `markitdown` | noise_retention | -0.261 | [-0.285, -0.238] |

## By page category (ChromeRAG vs Trafilatura vs MarkItDown)

### `homepage`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 41 | 0.575 | 0.002 | 0.709 |
| `markitdown` | 41 | 0.681 | 0.244 | 0.703 |
| `chromerag` | 41 | 0.540 | 0.002 | 0.680 |
| `trafilatura` | 41 | 0.433 | 0.007 | 0.572 |

### `pricing`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `markitdown` | 30 | 0.724 | 0.275 | 0.705 |
| `chromerag_coverage` | 30 | 0.569 | 0.000 | 0.697 |
| `trafilatura` | 30 | 0.540 | 0.004 | 0.668 |
| `chromerag` | 30 | 0.493 | 0.000 | 0.628 |

### `product`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 106 | 0.645 | 0.003 | 0.766 |
| `markitdown` | 106 | 0.765 | 0.266 | 0.736 |
| `chromerag` | 106 | 0.604 | 0.003 | 0.736 |
| `trafilatura` | 106 | 0.592 | 0.010 | 0.726 |

