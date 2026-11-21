# Trafilatura favor_recall / favor_precision, WCXB test split (511 pages, 444 sites)

Robustness rows added by the author (not requested in review; an earlier version of this file and the run records called them reviewer-requested, see `../../PROTOCOL.md`, editorial note of 2026-11-20). Trafilatura 2.2.0, same arguments as the P07 default row (Markdown, tables, no
comments, no links, no metadata) plus `favor_recall=True` or `favor_precision=True`. Each run once, scored with
`poc.wcxb.word_f1` / `snippet_rate`. Reproduction check passed: the unmodified configuration gives F1 0.8596 and
matches the saved P07 rows on every page; ChromeRAG balanced (0.1.5, front matter stripped) is read from the saved P07
rows (0.8839). No errors, 3 / 14 empty outputs (recall / precision) against 3 for the default. Code: `poc/trafilatura_options.py`.

| Output | F1 | without-snippet | with-snippet |
|---|---|---|---|
| ChromeRAG balanced | 0.8839 | 0.0700 | 0.7595 |
| Trafilatura 2.2.0 default | 0.8596 | 0.0828 | 0.7200 |
| Trafilatura favor_recall | 0.8452 | 0.0869 | 0.7057 |
| Trafilatura favor_precision | 0.7871 | 0.0563 | 0.6212 |

Paired differences (sites resampled, 5,000 draws, seed 0; 95% interval), F1 / without / with:

| Difference | F1 | without | with |
|---|---|---|---|
| balanced minus favor_recall | +0.0387 [0.0170, 0.0616] | -0.0170 [-0.0354, 0.0017] | +0.0537 [0.0177, 0.0924] |
| balanced minus favor_precision | +0.0968 [0.0694, 0.1252] | +0.0137 [-0.0010, 0.0299] | +0.1383 [0.1015, 0.1768] |
| favor_recall minus default | -0.0144 [-0.0296, 0.0002] | +0.0041 [-0.0053, 0.0138] | -0.0143 [-0.0325, 0.0035] |
| favor_precision minus default | -0.0725 [-0.0943, -0.0511] | -0.0266 [-0.0390, -0.0154] | -0.0989 [-0.1219, -0.0775] |

A lower without-snippet rate is better, so for that column a negative "balanced minus variant" favors ChromeRAG.

## Trafilatura versions (saved files, not rerun)

Source: `evaluations/2026-11-baseline-reconciliation/wcxb_{test,dev}_trafilatura-<version>.json`, written 2026-11-01
(see `p0-02-baseline-reconciliation.md`). Same word-F1 tokenizer and rules; test files cover the same 511 pages
(6 with empty reference), dev files 1,495 pages. Versions were loaded from upstream tag source with the dependency
versions recorded in each file. The files hold no snippet rates. "repo" = Markdown/tables/no comments, "default" =
library default (plain text). The favor columns in these files use default arguments, not the repo arguments of the
new rows above, so they are not comparable with them. The void run `wcxb_test_trafilatura-2.2.0_chromerag-0.1.4.json`
was not used.

| Trafilatura | test F1 repo | test F1 default | test favor_recall | test favor_precision | dev F1 repo | dev F1 default |
|---|---|---|---|---|---|---|
| 1.12.2 | 0.8292 | 0.8192 | 0.8358 | 0.7785 | 0.7791 | 0.7764 |
| 2.0.0 | 0.8292 | 0.8193 | 0.8358 | 0.7785 | 0.7791 | 0.7764 |
| 2.1.0 | 0.8327 | 0.8226 | 0.8390 | 0.7801 | 0.7791 | 0.7767 |
| 2.2.0 (this work, P07) | 0.8596 | not rerun | 0.8452 (repo args) | 0.7871 (repo args) | n/a | n/a |
| 2.3.1 | 0.8625 | 0.8614 | 0.8462 | 0.7903 | 0.8222 | 0.8189 |

Caveat: the baseline-reconciliation note already lists test-split favor_recall 0.842 and favor_precision 0.782 for
2.2.0 (default arguments), so the test split was looked at for these options before this run.
