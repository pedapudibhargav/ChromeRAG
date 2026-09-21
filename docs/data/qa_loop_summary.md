# ChromeRAG QA Loop

Fixtures: 26  Passed: True

| Method | n | Recall | Noise ret | Fbal | Tokens |
|---|---:|---:|---:|---:|---:|
| `chromerag_coverage` | 23 | 0.817 | 0.002 | 0.894 | 2250 |
| `chromerag` | 23 | 0.799 | 0.002 | 0.883 | 2217 |
| `trafilatura` | 23 | 0.743 | 0.055 | 0.796 | 2034 |
| `chromerag_precision` | 23 | 0.688 | 0.002 | 0.795 | 2012 |
| `markdownify` | 23 | 0.802 | 0.297 | 0.729 | 7016 |
| `html2text` | 23 | 0.801 | 0.305 | 0.723 | 7041 |
| `readability` | 23 | 0.511 | 0.000 | 0.588 | 1557 |
| `beautifulsoup_text` | 23 | 0.865 | 0.759 | 0.315 | 3582 |

## Unscored / near-zero recall

- `stripe-docs-home` — chromerag_recall_near_zero (best other: ('beautifulsoup_text', 0.8315))
- `stripe-docs-payments` — chromerag_recall_near_zero (best other: ('beautifulsoup_text', 0.6964))
