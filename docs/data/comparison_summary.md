# Extraction Comparison Report

Metrics use HTML-derived anchors (main/article content vs nav/footer chrome),
independent of any extractor. Thin JS-shell pages excluded from averages.

## Mode tradeoff (ours, scoreable pages only)

Pages where all our modes return ~0 content (static JS shells) are excluded here;
see per-page table in `comparison_report.json` for those failures.

| Mode | Pages | Content recall ↑ | Noise retention ↓ | F_precision | F_coverage | F_balanced | Avg tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| `ours_precision` | 12 | 0.7022 | 0.0 | 0.7367 | 0.7367 | 0.8014 | 2554 |
| `ours_balanced` | 12 | 0.8447 | 0.0 | 0.8704 | 0.8704 | 0.9134 | 2819 |
| `ours_coverage` | 12 | 0.8527 | 0.0 | 0.8774 | 0.8774 | 0.9184 | 2834 |

## All methods on scoreable pages

| Method | Pages | Recall ↑ | Noise ret ↓ | F_bal | Tokens | Noise/1k tok |
|---|---:|---:|---:|---:|---:|---:|
| `ours_coverage` | 12 | 0.853 | 0.000 | 0.918 | 2834 | 0.08 |
| `ours_balanced` | 12 | 0.845 | 0.000 | 0.913 | 2819 | 0.08 |
| `ours_precision` | 12 | 0.702 | 0.000 | 0.801 | 2554 | 0.09 |
| `markdownify` | 12 | 0.800 | 0.274 | 0.741 | 7748 | 0.82 |
| `trafilatura` | 12 | 0.719 | 0.105 | 0.737 | 2636 | 0.01 |
| `html2text` | 12 | 0.796 | 0.277 | 0.736 | 7754 | 0.82 |
| `readability` | 12 | 0.486 | 0.000 | 0.564 | 2162 | 0.05 |
| `beautifulsoup_text` | 12 | 0.859 | 0.668 | 0.383 | 4158 | 1.16 |
| `markitdown` | 12 | 0.000 | 0.000 | 0.000 | 6 | 0.00 |

## How to choose

- `--priority precision` — maximize cleanliness; accept lower content recall.
- `--priority coverage` — maximize content recall; accept more residual chrome.
- `--priority balanced` — default for enterprise RAG ingest.

## Known gaps

  needs optional Playwright render stage — not more aggressive pruning.
- MarkItDown not installed in this container run (excluded).

