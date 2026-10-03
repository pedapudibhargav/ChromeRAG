# ChromeRAG Corpus Comparison (194 fetched / 196 listed)

Corpus URLs listed: **196**  
Pages fetched/available: **194**  
Scoreable (input DOM has ≥ 50 main-content anchors): **178**  
Thin / excluded from means: **16**

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
| `html2text` | 178 | 0.734 | 0.221 | 0.744 | 9335 |
| `markdownify` | 178 | 0.744 | 0.233 | 0.743 | 9344 |
| `markitdown` | 178 | 0.744 | 0.238 | 0.741 | 6569 |
| `chromerag_coverage` | 178 | 0.615 | 0.004 | 0.735 | 1403 |
| `chromerag` | 178 | 0.581 | 0.004 | 0.708 | 1294 |
| `trafilatura` | 178 | 0.518 | 0.015 | 0.649 | 1262 |
| `chromerag_precision` | 178 | 0.501 | 0.003 | 0.643 | 1127 |
| `readability` | 178 | 0.458 | 0.003 | 0.567 | 968 |
| `beautifulsoup_text` | 178 | 0.802 | 0.843 | 0.197 | 2958 |

## All fetched pages (no cohort filter, n=194)

| Method | Pages | Recall ↑ | Noise ret ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `html2text` | 194 | 0.695 | 0.222 | 0.702 |
| `markdownify` | 194 | 0.704 | 0.233 | 0.701 |
| `markitdown` | 194 | 0.704 | 0.238 | 0.699 |
| `chromerag_coverage` | 194 | 0.579 | 0.004 | 0.691 |
| `chromerag` | 194 | 0.548 | 0.004 | 0.666 |
| `trafilatura` | 194 | 0.491 | 0.014 | 0.612 |
| `chromerag_precision` | 194 | 0.475 | 0.004 | 0.606 |
| `readability` | 194 | 0.429 | 0.003 | 0.532 |
| `beautifulsoup_text` | 194 | 0.757 | 0.841 | 0.194 |

## Paired bootstrap (scoreable pages, 95% CI of mean difference)

| Comparison | Metric | Mean diff | 95% CI |
|---|---|---:|---:|
| `chromerag_coverage` − `trafilatura` | f_balanced | +0.086 | [+0.054, +0.119] |
| `chromerag_coverage` − `trafilatura` | content_recall | +0.097 | [+0.066, +0.126] |
| `chromerag_coverage` − `trafilatura` | noise_retention | -0.011 | [-0.025, -0.002] |
| `chromerag` − `trafilatura` | f_balanced | +0.059 | [+0.030, +0.091] |
| `chromerag` − `trafilatura` | content_recall | +0.063 | [+0.030, +0.092] |
| `chromerag` − `trafilatura` | noise_retention | -0.012 | [-0.025, -0.002] |
| `chromerag_coverage` − `markitdown` | f_balanced | -0.005 | [-0.034, +0.021] |
| `chromerag_coverage` − `markitdown` | content_recall | -0.129 | [-0.156, -0.105] |
| `chromerag_coverage` − `markitdown` | noise_retention | -0.234 | [-0.255, -0.213] |

## By page category (ChromeRAG vs Trafilatura vs MarkItDown)

### `homepage`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `markitdown` | 41 | 0.694 | 0.252 | 0.706 |
| `chromerag_coverage` | 41 | 0.552 | 0.006 | 0.684 |
| `chromerag` | 41 | 0.515 | 0.005 | 0.654 |
| `trafilatura` | 41 | 0.378 | 0.027 | 0.505 |

### `pricing`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `markitdown` | 22 | 0.729 | 0.218 | 0.744 |
| `chromerag_coverage` | 22 | 0.601 | 0.003 | 0.728 |
| `chromerag` | 22 | 0.552 | 0.003 | 0.685 |
| `trafilatura` | 22 | 0.554 | 0.021 | 0.677 |

### `product`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 115 | 0.640 | 0.003 | 0.755 |
| `markitdown` | 115 | 0.765 | 0.237 | 0.752 |
| `chromerag` | 115 | 0.609 | 0.003 | 0.731 |
| `trafilatura` | 115 | 0.561 | 0.010 | 0.695 |

