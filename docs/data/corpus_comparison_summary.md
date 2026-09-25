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
| `chromerag_coverage` | 242 | 0.688 | 0.007 | 0.788 | 3457 |
| `chromerag` | 242 | 0.665 | 0.006 | 0.771 | 3383 |
| `trafilatura` | 242 | 0.640 | 0.012 | 0.739 | 2486 |
| `markitdown` | 242 | 0.691 | 0.250 | 0.696 | 8873 |
| `markdownify` | 242 | 0.691 | 0.251 | 0.695 | 8833 |
| `html2text` | 242 | 0.676 | 0.267 | 0.672 | 8715 |
| `chromerag_precision` | 242 | 0.525 | 0.007 | 0.652 | 2928 |
| `readability` | 242 | 0.449 | 0.013 | 0.531 | 2064 |
| `beautifulsoup_text` | 242 | 0.815 | 0.824 | 0.243 | 4472 |

## All fetched pages (no cohort filter, n=268)

| Method | Pages | Recall ↑ | Noise ret ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 268 | 0.654 | 0.007 | 0.747 |
| `chromerag` | 268 | 0.633 | 0.007 | 0.731 |
| `trafilatura` | 268 | 0.607 | 0.024 | 0.696 |
| `markitdown` | 268 | 0.658 | 0.240 | 0.661 |
| `markdownify` | 268 | 0.658 | 0.241 | 0.661 |
| `html2text` | 268 | 0.644 | 0.256 | 0.639 |
| `chromerag_precision` | 268 | 0.501 | 0.007 | 0.619 |
| `readability` | 268 | 0.420 | 0.017 | 0.495 |
| `beautifulsoup_text` | 268 | 0.773 | 0.793 | 0.233 |

## Paired bootstrap (scoreable pages, 95% CI of mean difference)

| Comparison | Metric | Mean diff | 95% CI |
|---|---|---:|---:|
| `chromerag_coverage` − `trafilatura` | f_balanced | +0.049 | [+0.021, +0.079] |
| `chromerag_coverage` − `trafilatura` | content_recall | +0.048 | [+0.021, +0.075] |
| `chromerag_coverage` − `trafilatura` | noise_retention | -0.005 | [-0.014, +0.003] |
| `chromerag` − `trafilatura` | f_balanced | +0.032 | [+0.004, +0.061] |
| `chromerag` − `trafilatura` | content_recall | +0.025 | [-0.005, +0.054] |
| `chromerag` − `trafilatura` | noise_retention | -0.006 | [-0.015, +0.003] |
| `chromerag_coverage` − `markitdown` | f_balanced | +0.093 | [+0.069, +0.117] |
| `chromerag_coverage` − `markitdown` | content_recall | -0.003 | [-0.025, +0.017] |
| `chromerag_coverage` − `markitdown` | noise_retention | -0.243 | [-0.266, -0.220] |

## By page category (ChromeRAG vs Trafilatura vs MarkItDown)

### `api_docs`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 4 | 0.710 | 0.000 | 0.827 |
| `chromerag` | 4 | 0.668 | 0.000 | 0.798 |
| `markitdown` | 4 | 0.622 | 0.182 | 0.699 |
| `trafilatura` | 4 | 0.448 | 0.000 | 0.573 |

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

### `docs`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 208 | 0.682 | 0.007 | 0.782 |
| `chromerag` | 208 | 0.659 | 0.007 | 0.764 |
| `trafilatura` | 208 | 0.645 | 0.009 | 0.745 |
| `markitdown` | 208 | 0.685 | 0.252 | 0.691 |

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

