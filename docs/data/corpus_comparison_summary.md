# ChromeRAG Corpus Comparison (277 fetched / 373 listed)

Corpus URLs listed: **373**  
Pages fetched/available: **277**  
Scoreable (input DOM has ≥ 50 main-content anchors): **250**  
Thin / excluded from means: **27**

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
| `chromerag_coverage` | 250 | 0.691 | 0.007 | 0.791 | 3393 |
| `chromerag` | 250 | 0.667 | 0.006 | 0.774 | 3319 |
| `trafilatura` | 250 | 0.640 | 0.012 | 0.740 | 2445 |
| `markitdown` | 250 | 0.692 | 0.253 | 0.694 | 8766 |
| `markdownify` | 250 | 0.692 | 0.254 | 0.694 | 8728 |
| `html2text` | 250 | 0.676 | 0.270 | 0.670 | 8617 |
| `chromerag_precision` | 250 | 0.525 | 0.007 | 0.651 | 2871 |
| `readability` | 250 | 0.450 | 0.013 | 0.531 | 2030 |
| `beautifulsoup_text` | 250 | 0.815 | 0.826 | 0.241 | 4407 |

## All fetched pages (no cohort filter, n=277)

| Method | Pages | Recall ↑ | Noise ret ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 277 | 0.659 | 0.007 | 0.752 |
| `chromerag` | 277 | 0.638 | 0.007 | 0.736 |
| `trafilatura` | 277 | 0.610 | 0.024 | 0.698 |
| `markitdown` | 277 | 0.661 | 0.244 | 0.661 |
| `markdownify` | 277 | 0.661 | 0.245 | 0.661 |
| `html2text` | 277 | 0.646 | 0.260 | 0.639 |
| `chromerag_precision` | 277 | 0.503 | 0.007 | 0.620 |
| `readability` | 277 | 0.423 | 0.016 | 0.499 |
| `beautifulsoup_text` | 277 | 0.775 | 0.797 | 0.232 |

## Paired bootstrap (scoreable pages, 95% CI of mean difference)

| Comparison | Metric | Mean diff | 95% CI |
|---|---|---:|---:|
| `chromerag_coverage` − `trafilatura` | f_balanced | +0.051 | [+0.025, +0.081] |
| `chromerag_coverage` − `trafilatura` | content_recall | +0.051 | [+0.022, +0.079] |
| `chromerag_coverage` − `trafilatura` | noise_retention | -0.005 | [-0.014, +0.004] |
| `chromerag` − `trafilatura` | f_balanced | +0.034 | [+0.007, +0.064] |
| `chromerag` − `trafilatura` | content_recall | +0.027 | [-0.002, +0.055] |
| `chromerag` − `trafilatura` | noise_retention | -0.005 | [-0.015, +0.003] |
| `chromerag_coverage` − `markitdown` | f_balanced | +0.097 | [+0.072, +0.120] |
| `chromerag_coverage` − `markitdown` | content_recall | -0.001 | [-0.023, +0.020] |
| `chromerag_coverage` − `markitdown` | noise_retention | -0.246 | [-0.269, -0.222] |

## By page category (ChromeRAG vs Trafilatura vs MarkItDown)

### `api_docs`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 6 | 0.778 | 0.007 | 0.867 |
| `chromerag` | 6 | 0.737 | 0.007 | 0.840 |
| `trafilatura` | 6 | 0.607 | 0.002 | 0.702 |
| `markitdown` | 6 | 0.706 | 0.277 | 0.687 |

### `api_docs_jsonld`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag` | 1 | 0.739 | 0.000 | 0.850 |
| `chromerag_coverage` | 1 | 0.739 | 0.000 | 0.850 |
| `trafilatura` | 1 | 0.728 | 0.000 | 0.843 |
| `markitdown` | 1 | 0.707 | 0.547 | 0.552 |

### `article`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 8 | 0.793 | 0.021 | 0.872 |
| `chromerag` | 8 | 0.743 | 0.021 | 0.837 |
| `trafilatura` | 8 | 0.718 | 0.003 | 0.812 |
| `markitdown` | 8 | 0.708 | 0.275 | 0.705 |

### `cloud`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 7 | 0.687 | 0.000 | 0.803 |
| `chromerag` | 7 | 0.683 | 0.000 | 0.800 |
| `markitdown` | 7 | 0.811 | 0.273 | 0.766 |
| `trafilatura` | 7 | 0.584 | 0.000 | 0.702 |

### `cloud_docs`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `trafilatura` | 1 | 0.909 | 0.000 | 0.952 |
| `chromerag_coverage` | 1 | 0.894 | 0.000 | 0.944 |
| `chromerag` | 1 | 0.870 | 0.000 | 0.930 |
| `markitdown` | 1 | 0.864 | 0.516 | 0.621 |

### `docs`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 212 | 0.682 | 0.007 | 0.783 |
| `chromerag` | 212 | 0.659 | 0.007 | 0.765 |
| `trafilatura` | 212 | 0.641 | 0.009 | 0.742 |
| `markitdown` | 212 | 0.684 | 0.251 | 0.691 |

### `hub`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 2 | 0.690 | 0.000 | 0.806 |
| `chromerag` | 2 | 0.670 | 0.000 | 0.794 |
| `markitdown` | 2 | 0.551 | 0.058 | 0.693 |
| `trafilatura` | 2 | 0.433 | 0.000 | 0.519 |

### `marketing`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 8 | 0.698 | 0.000 | 0.816 |
| `chromerag` | 8 | 0.685 | 0.000 | 0.807 |
| `markitdown` | 8 | 0.724 | 0.306 | 0.672 |
| `trafilatura` | 8 | 0.588 | 0.129 | 0.644 |

### `pricing`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 5 | 0.719 | 0.000 | 0.821 |
| `markitdown` | 5 | 0.797 | 0.126 | 0.817 |
| `chromerag` | 5 | 0.713 | 0.000 | 0.816 |
| `trafilatura` | 5 | 0.709 | 0.000 | 0.805 |

