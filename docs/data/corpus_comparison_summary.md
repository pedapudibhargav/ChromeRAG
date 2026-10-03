# ChromeRAG Corpus Comparison (268 fetched / 367 listed)

Corpus URLs listed: **367**  
Pages fetched/available: **268**  
Scoreable (input DOM has ≥ 50 main-content anchors): **242**  
Thin / excluded from means: **26**

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
| `chromerag_coverage` | 242 | 0.696 | 0.009 | 0.797 | 2443 |
| `chromerag` | 242 | 0.653 | 0.007 | 0.765 | 2091 |
| `trafilatura` | 242 | 0.640 | 0.012 | 0.739 | 2487 |
| `chromerag_precision` | 242 | 0.593 | 0.007 | 0.711 | 1743 |
| `markitdown` | 242 | 0.691 | 0.250 | 0.696 | 8886 |
| `markdownify` | 242 | 0.691 | 0.251 | 0.695 | 8846 |
| `html2text` | 242 | 0.676 | 0.267 | 0.672 | 8729 |
| `readability` | 242 | 0.449 | 0.013 | 0.531 | 2067 |
| `beautifulsoup_text` | 242 | 0.815 | 0.823 | 0.244 | 4476 |

## All fetched pages (no cohort filter, n=268)

| Method | Pages | Recall ↑ | Noise ret ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 268 | 0.660 | 0.012 | 0.755 |
| `chromerag` | 268 | 0.614 | 0.011 | 0.718 |
| `trafilatura` | 268 | 0.607 | 0.024 | 0.696 |
| `chromerag_precision` | 268 | 0.558 | 0.011 | 0.668 |
| `markitdown` | 268 | 0.658 | 0.240 | 0.661 |
| `markdownify` | 268 | 0.658 | 0.241 | 0.661 |
| `html2text` | 268 | 0.644 | 0.256 | 0.640 |
| `readability` | 268 | 0.420 | 0.017 | 0.495 |
| `beautifulsoup_text` | 268 | 0.773 | 0.793 | 0.234 |

## Paired bootstrap (scoreable pages, 95% CI of mean difference)

| Comparison | Metric | Mean diff | 95% CI |
|---|---|---:|---:|
| `chromerag_coverage` − `trafilatura` | f_balanced | +0.058 | [+0.034, +0.085] |
| `chromerag_coverage` − `trafilatura` | content_recall | +0.056 | [+0.029, +0.082] |
| `chromerag_coverage` − `trafilatura` | noise_retention | -0.004 | [-0.013, +0.004] |
| `chromerag` − `trafilatura` | f_balanced | +0.025 | [+0.002, +0.050] |
| `chromerag` − `trafilatura` | content_recall | +0.013 | [-0.011, +0.037] |
| `chromerag` − `trafilatura` | noise_retention | -0.005 | [-0.014, +0.002] |
| `chromerag_coverage` − `markitdown` | f_balanced | +0.102 | [+0.080, +0.124] |
| `chromerag_coverage` − `markitdown` | content_recall | +0.005 | [-0.017, +0.027] |
| `chromerag_coverage` − `markitdown` | noise_retention | -0.241 | [-0.264, -0.219] |

## By page category (ChromeRAG vs Trafilatura vs MarkItDown)

### `api_docs`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `markitdown` | 4 | 0.622 | 0.182 | 0.699 |
| `chromerag_coverage` | 4 | 0.529 | 0.000 | 0.667 |
| `chromerag` | 4 | 0.502 | 0.000 | 0.642 |
| `trafilatura` | 4 | 0.448 | 0.000 | 0.573 |

### `article`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `trafilatura` | 8 | 0.715 | 0.003 | 0.809 |
| `chromerag_coverage` | 8 | 0.668 | 0.005 | 0.782 |
| `chromerag` | 8 | 0.581 | 0.005 | 0.723 |
| `markitdown` | 8 | 0.705 | 0.275 | 0.704 |

### `cloud`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `markitdown` | 7 | 0.811 | 0.273 | 0.766 |
| `chromerag_coverage` | 7 | 0.597 | 0.000 | 0.732 |
| `chromerag` | 7 | 0.571 | 0.000 | 0.713 |
| `trafilatura` | 7 | 0.584 | 0.000 | 0.702 |

### `docs`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 208 | 0.704 | 0.010 | 0.803 |
| `chromerag` | 208 | 0.663 | 0.008 | 0.772 |
| `trafilatura` | 208 | 0.645 | 0.009 | 0.745 |
| `markitdown` | 208 | 0.685 | 0.252 | 0.691 |

### `hub`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `markitdown` | 2 | 0.556 | 0.058 | 0.697 |
| `chromerag_coverage` | 2 | 0.496 | 0.000 | 0.600 |
| `chromerag` | 2 | 0.414 | 0.000 | 0.531 |
| `trafilatura` | 2 | 0.433 | 0.000 | 0.519 |

### `marketing`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 8 | 0.689 | 0.000 | 0.809 |
| `chromerag` | 8 | 0.616 | 0.000 | 0.750 |
| `markitdown` | 8 | 0.725 | 0.323 | 0.668 |
| `trafilatura` | 8 | 0.592 | 0.128 | 0.647 |

### `pricing`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 5 | 0.760 | 0.000 | 0.844 |
| `markitdown` | 5 | 0.797 | 0.126 | 0.817 |
| `chromerag` | 5 | 0.724 | 0.000 | 0.815 |
| `trafilatura` | 5 | 0.709 | 0.000 | 0.805 |

