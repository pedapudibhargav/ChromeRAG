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
| `chromerag_coverage` | 242 | 0.739 | 0.010 | 0.833 | 2573 |
| `chromerag` | 242 | 0.688 | 0.004 | 0.798 | 2178 |
| `trafilatura` | 242 | 0.640 | 0.012 | 0.739 | 2487 |
| `chromerag_precision` | 242 | 0.606 | 0.003 | 0.727 | 1781 |
| `markitdown` | 242 | 0.691 | 0.250 | 0.696 | 8886 |
| `markdownify` | 242 | 0.691 | 0.251 | 0.695 | 8846 |
| `html2text` | 242 | 0.676 | 0.267 | 0.672 | 8729 |
| `readability` | 242 | 0.449 | 0.013 | 0.531 | 2067 |
| `beautifulsoup_text` | 242 | 0.815 | 0.823 | 0.244 | 4476 |

## All fetched pages (no cohort filter, n=268)

| Method | Pages | Recall ↑ | Noise ret ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 268 | 0.702 | 0.013 | 0.790 |
| `chromerag` | 268 | 0.652 | 0.007 | 0.755 |
| `trafilatura` | 268 | 0.607 | 0.024 | 0.696 |
| `chromerag_precision` | 268 | 0.569 | 0.007 | 0.682 |
| `markitdown` | 268 | 0.658 | 0.240 | 0.661 |
| `markdownify` | 268 | 0.658 | 0.241 | 0.661 |
| `html2text` | 268 | 0.644 | 0.256 | 0.640 |
| `readability` | 268 | 0.420 | 0.017 | 0.495 |
| `beautifulsoup_text` | 268 | 0.773 | 0.793 | 0.234 |

## Paired bootstrap (scoreable pages, 95% CI of mean difference)

| Comparison | Metric | Mean diff | 95% CI |
|---|---|---:|---:|
| `chromerag_coverage` − `trafilatura` | f_balanced | +0.094 | [+0.066, +0.122] |
| `chromerag_coverage` − `trafilatura` | content_recall | +0.099 | [+0.072, +0.127] |
| `chromerag_coverage` − `trafilatura` | noise_retention | -0.002 | [-0.013, +0.009] |
| `chromerag` − `trafilatura` | f_balanced | +0.059 | [+0.034, +0.085] |
| `chromerag` − `trafilatura` | content_recall | +0.048 | [+0.022, +0.074] |
| `chromerag` − `trafilatura` | noise_retention | -0.008 | [-0.018, -0.001] |
| `chromerag_coverage` − `markitdown` | f_balanced | +0.137 | [+0.117, +0.159] |
| `chromerag_coverage` − `markitdown` | content_recall | +0.048 | [+0.028, +0.070] |
| `chromerag_coverage` − `markitdown` | noise_retention | -0.240 | [-0.264, -0.216] |

## By page category (ChromeRAG vs Trafilatura vs MarkItDown)

### `api_docs`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 4 | 0.689 | 0.000 | 0.810 |
| `chromerag` | 4 | 0.604 | 0.000 | 0.741 |
| `markitdown` | 4 | 0.622 | 0.182 | 0.699 |
| `trafilatura` | 4 | 0.448 | 0.000 | 0.573 |

### `article`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `trafilatura` | 8 | 0.715 | 0.003 | 0.809 |
| `chromerag_coverage` | 8 | 0.700 | 0.002 | 0.805 |
| `chromerag` | 8 | 0.634 | 0.002 | 0.759 |
| `markitdown` | 8 | 0.705 | 0.275 | 0.704 |

### `cloud`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 7 | 0.768 | 0.000 | 0.868 |
| `chromerag` | 7 | 0.747 | 0.000 | 0.854 |
| `markitdown` | 7 | 0.811 | 0.273 | 0.766 |
| `trafilatura` | 7 | 0.584 | 0.000 | 0.702 |

### `docs`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 208 | 0.744 | 0.010 | 0.836 |
| `chromerag` | 208 | 0.694 | 0.004 | 0.802 |
| `trafilatura` | 208 | 0.645 | 0.009 | 0.745 |
| `markitdown` | 208 | 0.685 | 0.252 | 0.691 |

### `hub`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `markitdown` | 2 | 0.556 | 0.058 | 0.697 |
| `chromerag_coverage` | 2 | 0.536 | 0.177 | 0.631 |
| `chromerag` | 2 | 0.425 | 0.000 | 0.535 |
| `trafilatura` | 2 | 0.433 | 0.000 | 0.519 |

### `marketing`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 8 | 0.707 | 0.000 | 0.820 |
| `chromerag` | 8 | 0.639 | 0.000 | 0.765 |
| `markitdown` | 8 | 0.725 | 0.323 | 0.668 |
| `trafilatura` | 8 | 0.592 | 0.128 | 0.647 |

### `pricing`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 5 | 0.746 | 0.001 | 0.835 |
| `markitdown` | 5 | 0.797 | 0.126 | 0.817 |
| `chromerag` | 5 | 0.709 | 0.001 | 0.805 |
| `trafilatura` | 5 | 0.709 | 0.000 | 0.805 |

