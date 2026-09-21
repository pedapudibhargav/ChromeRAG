# ChromeRAG Corpus Comparison (277 fetched / 373 listed)

Corpus URLs listed: **373**  
Pages fetched/available: **277**  
Scoreable (ChromeRAG recall ≥ 0.05): **238**  
Thin / excluded from means: **39**

> Thin pages (often unrendered JS shells or failed content regions) are excluded from leaderboard *averages* so empty shells are not silently averaged into SOTA claims. Callers must Playwright-render first, then pass HTML to ChromeRAG. All baselines are still scored on the same scoreable set.

## Baselines

ChromeRAG (balanced / coverage / precision) vs Trafilatura, Readability, MarkItDown, markdownify, html2text, BeautifulSoup text.

## Metrics

- **Recall (content_recall)** — fraction of main-content text anchors kept. Higher = fewer lost relevant chunks.
- **Noise ret (noise_retention)** — fraction of nav/footer chrome anchors kept. Lower = cleaner vectors.
- **Fbal (f_balanced)** — harmonic-style score balancing high recall and low noise.

## Leaderboard (scoreable pages)

| Method | Pages | Recall ↑ | Noise ret ↓ | Fbal ↑ | Avg tokens |
|---|---:|---:|---:|---:|---:|
| `chromerag_coverage` | 238 | 0.701 | 0.005 | 0.800 | 3526 |
| `chromerag` | 238 | 0.678 | 0.005 | 0.783 | 3451 |
| `trafilatura` | 238 | 0.662 | 0.019 | 0.752 | 2558 |
| `markitdown` | 238 | 0.702 | 0.261 | 0.695 | 9366 |
| `markdownify` | 238 | 0.702 | 0.263 | 0.695 | 9320 |
| `chromerag_precision` | 238 | 0.550 | 0.005 | 0.676 | 2993 |
| `html2text` | 238 | 0.694 | 0.282 | 0.675 | 9199 |
| `readability` | 238 | 0.456 | 0.016 | 0.535 | 2113 |
| `beautifulsoup_text` | 238 | 0.823 | 0.830 | 0.240 | 4622 |

## By page category (ChromeRAG vs Trafilatura vs MarkItDown)

### `api_docs`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 4 | 0.788 | 0.011 | 0.869 |
| `trafilatura` | 4 | 0.788 | 0.003 | 0.867 |
| `chromerag` | 4 | 0.746 | 0.011 | 0.843 |
| `markitdown` | 4 | 0.785 | 0.341 | 0.697 |

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
| `chromerag_coverage` | 2 | 0.947 | 0.000 | 0.972 |
| `chromerag` | 2 | 0.935 | 0.000 | 0.965 |
| `trafilatura` | 2 | 0.954 | 0.133 | 0.900 |
| `markitdown` | 2 | 0.932 | 0.482 | 0.666 |

### `docs`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 201 | 0.693 | 0.005 | 0.793 |
| `chromerag` | 201 | 0.670 | 0.005 | 0.776 |
| `trafilatura` | 201 | 0.661 | 0.016 | 0.753 |
| `markitdown` | 201 | 0.692 | 0.259 | 0.691 |

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

