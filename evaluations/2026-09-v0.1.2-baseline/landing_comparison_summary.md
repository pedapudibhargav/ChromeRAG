# ChromeRAG Corpus Comparison (395 fetched / 397 listed)

Corpus URLs listed: **397**  
Pages fetched/available: **395**  
Scoreable (input DOM has ≥ 50 main-content anchors): **362**  
Thin / excluded from means: **33**

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
| `chromerag_coverage` | 362 | 0.666 | 0.001 | 0.785 | 1885 |
| `chromerag` | 362 | 0.640 | 0.002 | 0.763 | 1805 |
| `html2text` | 362 | 0.728 | 0.243 | 0.724 | 7716 |
| `markdownify` | 362 | 0.736 | 0.268 | 0.717 | 7612 |
| `markitdown` | 362 | 0.735 | 0.269 | 0.716 | 7147 |
| `trafilatura` | 362 | 0.526 | 0.014 | 0.659 | 1314 |
| `chromerag_precision` | 362 | 0.506 | 0.002 | 0.644 | 1498 |
| `readability` | 362 | 0.390 | 0.012 | 0.488 | 1029 |
| `beautifulsoup_text` | 362 | 0.797 | 0.868 | 0.178 | 3381 |

## All fetched pages (no cohort filter, n=395)

| Method | Pages | Recall ↑ | Noise ret ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 395 | 0.642 | 0.001 | 0.753 |
| `chromerag` | 395 | 0.616 | 0.001 | 0.731 |
| `html2text` | 395 | 0.703 | 0.241 | 0.696 |
| `markdownify` | 395 | 0.711 | 0.266 | 0.689 |
| `markitdown` | 395 | 0.711 | 0.267 | 0.689 |
| `trafilatura` | 395 | 0.513 | 0.015 | 0.633 |
| `chromerag_precision` | 395 | 0.481 | 0.002 | 0.610 |
| `readability` | 395 | 0.379 | 0.011 | 0.470 |
| `beautifulsoup_text` | 395 | 0.767 | 0.863 | 0.175 |

## Paired bootstrap (scoreable pages, 95% CI of mean difference)

| Comparison | Metric | Mean diff | 95% CI |
|---|---|---:|---:|
| `chromerag_coverage` − `trafilatura` | f_balanced | +0.127 | [+0.105, +0.147] |
| `chromerag_coverage` − `trafilatura` | content_recall | +0.140 | [+0.118, +0.164] |
| `chromerag_coverage` − `trafilatura` | noise_retention | -0.012 | [-0.021, -0.005] |
| `chromerag` − `trafilatura` | f_balanced | +0.105 | [+0.085, +0.127] |
| `chromerag` − `trafilatura` | content_recall | +0.113 | [+0.090, +0.137] |
| `chromerag` − `trafilatura` | noise_retention | -0.012 | [-0.021, -0.005] |
| `chromerag_coverage` − `markitdown` | f_balanced | +0.069 | [+0.052, +0.087] |
| `chromerag_coverage` − `markitdown` | content_recall | -0.069 | [-0.087, -0.052] |
| `chromerag_coverage` − `markitdown` | noise_retention | -0.267 | [-0.285, -0.249] |

## By page category (ChromeRAG vs Trafilatura vs MarkItDown)

### `homepage`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 86 | 0.614 | 0.001 | 0.745 |
| `chromerag` | 86 | 0.589 | 0.001 | 0.723 |
| `markitdown` | 86 | 0.674 | 0.261 | 0.687 |
| `trafilatura` | 86 | 0.444 | 0.008 | 0.581 |

### `pricing`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 57 | 0.643 | 0.001 | 0.764 |
| `chromerag` | 57 | 0.604 | 0.001 | 0.732 |
| `markitdown` | 57 | 0.722 | 0.270 | 0.708 |
| `trafilatura` | 57 | 0.511 | 0.017 | 0.636 |

### `product`

| Method | Pages | Recall ↑ | Noise ↓ | Fbal ↑ |
|---|---:|---:|---:|---:|
| `chromerag_coverage` | 219 | 0.693 | 0.002 | 0.807 |
| `chromerag` | 219 | 0.669 | 0.002 | 0.788 |
| `markitdown` | 219 | 0.763 | 0.271 | 0.730 |
| `trafilatura` | 219 | 0.563 | 0.015 | 0.695 |

