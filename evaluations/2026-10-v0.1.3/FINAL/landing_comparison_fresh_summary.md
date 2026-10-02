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
| `chromerag_coverage` | 178 | 0.662 | 0.000 | 0.780 | 1522 |
| `chromerag` | 178 | 0.617 | 0.000 | 0.744 | 1349 |
| `html2text` | 178 | 0.734 | 0.221 | 0.744 | 9335 |
| `markdownify` | 178 | 0.744 | 0.233 | 0.743 | 9344 |
| `markitdown` | 178 | 0.744 | 0.238 | 0.741 | 6569 |
| `chromerag_precision` | 178 | 0.523 | 0.000 | 0.667 | 1169 |
| `trafilatura` | 178 | 0.518 | 0.015 | 0.649 | 1262 |
| `readability` | 178 | 0.458 | 0.003 | 0.567 | 968 |
| `beautifulsoup_text` | 178 | 0.802 | 0.843 | 0.197 | 2958 |

## All fetched pages (no cohort filter, n=194)

| Method | Pages | Recall ↑ | Noise ret ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 194 | 0.627 | 0.004 | 0.737 |
| `chromerag` | 194 | 0.585 | 0.000 | 0.704 |
| `html2text` | 194 | 0.695 | 0.222 | 0.702 |
| `markdownify` | 194 | 0.704 | 0.233 | 0.701 |
| `markitdown` | 194 | 0.704 | 0.238 | 0.699 |
| `chromerag_precision` | 194 | 0.500 | 0.003 | 0.634 |
| `trafilatura` | 194 | 0.491 | 0.014 | 0.612 |
| `readability` | 194 | 0.429 | 0.003 | 0.532 |
| `beautifulsoup_text` | 194 | 0.757 | 0.841 | 0.194 |

## Paired bootstrap (scoreable pages, 95% CI of mean difference)

| Comparison | Metric | Mean diff | 95% CI |
|---|---|---:|---:|
| `chromerag_coverage` − `trafilatura` | f_balanced | +0.131 | [+0.102, +0.161] |
| `chromerag_coverage` − `trafilatura` | content_recall | +0.144 | [+0.113, +0.173] |
| `chromerag_coverage` − `trafilatura` | noise_retention | -0.015 | [-0.028, -0.005] |
| `chromerag` − `trafilatura` | f_balanced | +0.095 | [+0.068, +0.126] |
| `chromerag` − `trafilatura` | content_recall | +0.098 | [+0.068, +0.128] |
| `chromerag` − `trafilatura` | noise_retention | -0.015 | [-0.028, -0.005] |
| `chromerag_coverage` − `markitdown` | f_balanced | +0.039 | [+0.015, +0.061] |
| `chromerag_coverage` − `markitdown` | content_recall | -0.082 | [-0.105, -0.060] |
| `chromerag_coverage` − `markitdown` | noise_retention | -0.238 | [-0.258, -0.217] |

## By page category (ChromeRAG vs Trafilatura vs MarkItDown)

### `homepage`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 41 | 0.624 | 0.001 | 0.750 |
| `chromerag` | 41 | 0.569 | 0.001 | 0.708 |
| `markitdown` | 41 | 0.694 | 0.252 | 0.706 |
| `trafilatura` | 41 | 0.378 | 0.027 | 0.505 |

### `pricing`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `markitdown` | 22 | 0.729 | 0.218 | 0.744 |
| `chromerag_coverage` | 22 | 0.605 | 0.000 | 0.732 |
| `chromerag` | 22 | 0.546 | 0.000 | 0.678 |
| `trafilatura` | 22 | 0.554 | 0.021 | 0.677 |

### `product`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 115 | 0.687 | 0.000 | 0.800 |
| `chromerag` | 115 | 0.647 | 0.000 | 0.769 |
| `markitdown` | 115 | 0.765 | 0.237 | 0.752 |
| `trafilatura` | 115 | 0.561 | 0.010 | 0.695 |

