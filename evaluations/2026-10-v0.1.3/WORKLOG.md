# ChromeRAG 0.1.3 work log

## WP0 — Evaluation harness, speed benchmark, golden check

### Commands
```bash
export PYTHONPATH=src:. PYTHONWARNINGS=ignore
python -m pytest -q -p no:cacheprovider
python -m poc.golden --write
python -m poc.bench_speed --label baseline
python -m poc.run_wcxb_eval --split dev --out evaluations/2026-10-v0.1.3/wcxb_dev_wp0.json \
  --compare evaluations/2026-09-v0.1.2-baseline/wcxb_dev_v012_per_page.json
```

### Results
- **pytest:** 28 passed (27 existing + test_golden)
- **speed_baseline.json:** chromerag_coverage median 78.0 ms/page (baseline target ~75)
- **WCXB dev chromerag_coverage F1:** 0.754 (baseline 0.749, delta +0.0006 ALL — within ±0.002)
- **Golden:** manifest.json written (300 corpus pages × 3 modes + 4 fixtures)

### Gates (WP0 baseline)
| Gate | Metric | Value | Target | Status |
|------|--------|------:|--------|--------|
| G1 | median ms/page | 78.0 | ≤45 | FAIL |
| G2 | WCXB dev F1 | 0.754 | ≥0.79 | FAIL |
## WP1 — Speed (identical output)

### Commands
```bash
python -m pytest -q -p no:cacheprovider
python -m poc.golden --check
python -m poc.bench_speed --label wp1
```

### Results
- **pytest:** 29 passed; golden check zero changes
- **speed_wp1.json:** chromerag_coverage median **74.4 ms/page** (baseline 78.0 ms, ~5% faster)
- **G1:** NOT MET (need ≤45 ms with identical output; deferred str(tag) approximation — broke golden)

## WP2 — Robustness (content root, hidden, skip links)

- **pytest:** 40 passed
- **WCXB dev chromerag_coverage F1:** 0.784 (baseline 0.749, +0.035)
- **without contamination:** 0.124 (baseline 0.129)
- **with snippets:** 0.639 (baseline 0.616)
- Golden: `tests/golden/ALLOWED_CHANGES.md` documents WP2 output changes

## WP3 — Rule index (partial)

- Initial rules: consent (OneTrust, Cookiebot, Osano), share/related, Docusaurus footer
- CLI: `--explain`, `--no-rules`
- **Not yet:** `poc/rule_evidence.py`, `poc/rule_audit.py`, full rule corpus, `rules/README.md`

## WP4–WP9 — Not implemented this session

Stopped before HAND-OFF 1 completion items (CTA/promo/dedup, page-type classifier, platform fingerprints, innovations, final eval, docs).

---

## HAND-OFF 1 — Gate table (chromerag_coverage, WCXB dev)

| Gate | Metric | Baseline | Current | Target | Status |
|------|--------|----------|---------|--------|--------|
| G1 | median ms/page | ~75 | 74.4 | ≤45 | **FAIL** |
| G2 | WCXB dev F1 all | 0.749 | **0.784** | ≥0.79 | **FAIL** (−0.006) |
| G3 | service F1 | 0.787 | **0.798** | ≥0.787 | **PASS** |
| G4 | collection/listing | 0.584/0.574 | **0.619/0.637** | no drop +0.03 | **PASS** |
| G5 | documentation F1 | 0.888 | **0.885** | ≥0.90 | **FAIL** |
| G6 | product F1 | 0.494 | **0.557** | ≥0.55 | **PASS** |
| G7 | without contamination | 0.129 | **0.124** | ≤0.09 | **FAIL** |
| G8 | with snippets | 0.616 | **0.639** | ≥0.616 | **PASS** |
| G9 | anchor F_bal | 0.788/0.785 | not re-run | no drop | **PENDING** |
| G10 | retrieval | — | — | — | **PENDING** |
| G11 | pytest | 27 | **40 pass** | all pass | **PASS** |

### Commits (local, not pushed)

```
76b4fbd WP3: rule index with evidence, fixtures, audit and --explain
8688622 WP2: per-call config, hidden nodes, skip links, content-root ladder, collapse fallback
393b3ee WP1: single-pass noise checks, one parse, cached densities (identical output)
3aed940 WP0: WCXB adapter, speed benchmark, golden check
```

---

## Review and learned block filter (2026-10-01)

Review of WP0–WP3 (commit 720b233): crash in skip-link removal, eval runner hiding crashes, golden check
skippable, rule engine never matching hyphenated class names, vacuous rule tests. All fixed; TreeStats gives
exact per-element text sizes (median 38 ms/page, output unchanged).

### What the dev errors were (WCXB dev, 1,495 pages)

| Cause | Example dev pages | Fix |
|---|---|---|
| Whole page lost: unclosed `<button>`/page-wide `<form>`/`<noscript>` swallowing the article | 0044 (button of 17,511 chars), 0225 (form of 12,076 chars) | unwrap instead of drop |
| Large `hidden`/`display:none` block of running text (reveal-by-script pages) | 0155 (hidden div of 16,419 chars), 4020 | keep hidden blocks with ≥1,500 chars and few links |
| Content after a stray `</html>` left outside `<body>` by lxml | 0310 (9,462 of 9,504 chars outside body) | adopt into `<body>` |
| Layout tables nested: text emitted 5–10 times (output larger than the HTML) | 0225 (234,384 output chars from 42,970 HTML chars), 0025 | unwrap layout tables, one pass |
| `class="col-sm-9 sidebar-first-only"` content column removed as a sidebar | 0139 | never prune elements with ≥2 long paragraphs and few links |
| Markdown written breadth-first (sections interleaved) | all | depth-first, document order |
| Link targets counted as words (2.9% of output tokens) | all | `include_links=False` by default |

After these: WCXB dev word F1 0.777 → 0.808.

### Learned block filter

Per-token statistics from labelled pages (`poc/learn_tokens.py`) showed a long tail of vendor-specific
class names; adding 20 learned words moved a held-out half by +0.003, so selectors were not the way.
Instead each block is scored by gradient-boosted trees (`src/chromerag/blockfeatures.py`, `lbc.py`,
`poc/lbc_data.py`, `poc/train_lbc.py`). Block labels come from word-trigram overlap with the reference
main content; blocks whose text the annotators listed as "without" snippets are labelled noise.

Tried without gain (do not repeat): second stage on neighbour/box probabilities, hashed bag-of-words text
model, tree distance to the main-prose blocks, keyword-group page shares, heading smoothing, orphan-heading
removal, tree depth 4/6/8, 300–600 iterations.

Evaluation protocol: 5 folds grouped by site (`crc32(site) % 5`); each fold's pages are scored by a model
trained on the other four (`poc/wcxb_diag.py run --fold K`, `poc/wcxb_cv_report.py`). The WCXB test split
and the landing held-out/fresh sets were not touched.

| WCXB dev, 5-fold CV | coverage | balanced | precision | Trafilatura | Readability | MarkItDown |
|---|---|---|---|---|---|---|
| all (1,495) | 0.846 | 0.845 | 0.833 | 0.818 | 0.700 | 0.513 |
| article (792) | 0.931 | 0.939 | 0.941 | 0.937 | 0.890 | 0.625 |
| documentation (91) | 0.910 | 0.908 | 0.885 | 0.915 | 0.811 | 0.653 |
| service (165) | 0.815 | 0.805 | 0.762 | 0.759 | 0.554 | 0.462 |
| forum (112) | 0.761 | 0.757 | 0.747 | 0.675 | 0.457 | 0.439 |
| product (119) | 0.634 | 0.642 | 0.646 | 0.626 | 0.410 | 0.231 |
| collection (117) | 0.669 | 0.641 | 0.604 | 0.564 | 0.387 | 0.226 |
| listing (99) | 0.723 | 0.693 | 0.641 | 0.565 | 0.313 | 0.333 |

Paired bootstrap vs Trafilatura (all pages): coverage +0.029 [+0.018, +0.039], balanced +0.028
[+0.018, +0.038], precision +0.016 [+0.005, +0.026].

Snippets (all pages): with 0.734 / 0.711 / 0.676 vs Trafilatura 0.659; without (lower is better)
0.102 / 0.080 / 0.065 vs Trafilatura 0.058.

Added after the first CV: repeated-structure features (siblings with the same tag and classes above a
block) and the heading text above a block; exact-repeat removal. Tried and dropped: expected-F selection of
blocks per page (same F as a fixed threshold), page-level generator/og:type words (no gain).

Ceilings of block selection (labels from the reference, perfect classifier): article 0.975,
documentation 0.965, service 0.902, product 0.845, listing 0.851, forum 0.832, collection 0.806.

Other gates: anchor F_bal docs 0.834 (baseline 0.788), landing dev 0.781 (baseline 0.785 on all 362
pages); speed median ~29 ms/page vs Trafilatura ~31 ms (`poc/bench_speed.py`).

### Ablation (WCXB dev, all 1,495 pages)

| | coverage | balanced | precision |
|---|---|---|---|
| v0.1.2 baseline (heuristics) | 0.749 | — | — |
| heuristics + robustness fixes (`enable_lbc=False`) | 0.822 | 0.817 | 0.790 |
| + learned block filter (5-fold CV) | 0.846 | 0.845 | 0.833 |

The robustness fixes (wrappers, tables, hidden text, order, links) account for most of the gain over 0.1.2;
the learned filter adds +0.024 / +0.028 / +0.043 on top.

---

## FINAL: WCXB test split (run once, 2026-10-02, commit 2d436bb tagged `freeze-0.1.3`)

Model trained on all of WCXB dev (`src/chromerag/assets/lbc_stage1.npz`), thresholds fixed beforehand
(0.30 / 0.50 / 0.70). 511 held-out pages, no crashes. Per-page file: `FINAL/wcxb_test.json`.
Command: `python -m poc.run_wcxb_eval --split test --final`.

| WCXB test (511) | coverage | balanced | precision | Trafilatura | Readability | MarkItDown |
|---|---|---|---|---|---|---|
| all | 0.900 | **0.902** | 0.887 | 0.860 | 0.763 | 0.540 |
| article (257) | 0.945 | 0.954 | 0.957 | 0.952 | 0.926 | 0.643 |
| documentation (42) | 0.954 | 0.956 | 0.946 | 0.934 | 0.872 | 0.615 |
| service (59) | 0.846 | 0.844 | 0.833 | 0.817 | 0.612 | 0.471 |
| forum (51) | 0.868 | 0.867 | 0.839 | 0.717 | 0.616 | 0.443 |
| product (28) | 0.853 | 0.874 | 0.861 | 0.724 | 0.527 | 0.335 |
| collection (34) | 0.799 | 0.795 | 0.714 | 0.626 | 0.450 | 0.284 |
| listing (40) | 0.789 | 0.760 | 0.676 | 0.722 | 0.439 | 0.386 |

Precision / recall / with / without (all pages): coverage 0.870 / 0.958 / 0.827 / 0.097; balanced 0.894 / 0.936 /
0.798 / 0.077; precision 0.905 / 0.899 / 0.752 / 0.065; Trafilatura 0.890 / 0.868 / 0.720 / 0.083; Readability
0.872 / 0.757 / 0.552 / 0.089; MarkItDown 0.410 / 0.989 / 0.768 / 0.967.

Paired bootstrap (5,000 resamples) of page-level F1 differences: balanced − Trafilatura **+0.043 [+0.027, +0.059]**;
coverage +0.040 [+0.024, +0.056]; precision +0.027 [+0.011, +0.045]; balanced − Readability +0.140 [+0.115, +0.165].
By type, balanced − Trafilatura: forum +0.150 [+0.091, +0.217], product +0.150 [+0.069, +0.243], collection +0.169
[+0.080, +0.264]; article +0.001 [−0.007, +0.009], documentation +0.022 [−0.016, +0.058], service +0.026 [−0.013,
+0.067], listing +0.038 [−0.067, +0.153] (ties). Snippets: with +0.078 [+0.051, +0.105], without −0.005 [−0.023,
+0.011] (no difference in contamination).

Published numbers for the same split (WCXB paper, different Trafilatura configuration, not re-run here): rs-trafilatura
0.903, Trafilatura 0.841. ChromeRAG balanced is 0.902 on the same pages under this repository's scorer.

Dev-to-test consistency: balanced 0.851 (CV on dev) vs 0.902 (test); Trafilatura 0.818 vs 0.860. The test split is
easier for every system; the gap to Trafilatura is the same size (+0.033 dev, +0.043 test).

## FINAL: landing held-out, fresh companies, judge, dense retrieval (run once, 2026-10-02, after the freeze)

Anchor metric (recall of `<main>`/`<article>` 5-grams, retention of nav/footer anchors, F_bal). Reports in `FINAL/`.

| | pages | coverage | balanced | precision | Trafilatura | MarkItDown | Readability |
|---|---|---|---|---|---|---|---|
| landing held-out companies | 177 | **0.759** | 0.717 | 0.628 | 0.680 | 0.723 | 0.512 |
| fresh companies (51, fetched 2026-10-02) | 178 | **0.780** | 0.744 | 0.667 | 0.649 | 0.741 | 0.567 |

The anchor metric rewards recall and cannot see chrome inside `<main>`; MarkItDown and the other converters keep
22-26% of the nav/footer anchors while ChromeRAG keeps 0.0-0.1%.

Blind pairwise LLM judge (`gpt-5.6-luna`, 100 pages: 50 held-out + 50 fresh; ChromeRAG coverage output vs
baseline, front matter removed, 20% of pairs repeated with positions swapped, 83% same verdict):

| vs | ChromeRAG wins | baseline wins | ties | net win rate [95% CI] | content (1-5) ours / theirs | chrome-free (1-5) ours / theirs |
|---|---|---|---|---|---|---|
| Trafilatura | 70% | 28% | 2% | +0.42 [+0.24, +0.59] | 4.40 / 3.48 | 3.96 / 4.65 |
| MarkItDown | 87% | 12% | 1% | +0.75 [+0.61, +0.87] | 4.25 / 2.30 | 4.58 / 1.18 |

The judge prefers ChromeRAG overall because it keeps much more content; Trafilatura leaves less chrome (4.65 vs 3.96).
Cost $0.203; total OpenAI spend $1.383 of the $2.10 budget.

Retrieval on the fresh companies (178 pages, 668 known-item queries, chunks of about 200 words):

| | BM25 hit@5 | chrome in top-5 | dense (`text-embedding-3-small`) hit@5 |
|---|---|---|---|
| ChromeRAG coverage | 0.916 | 0.001 | 0.708 |
| ChromeRAG balanced | 0.889 | 0.001 | 0.723 |
| Trafilatura | 0.832 | 0.011 | 0.698 |
| MarkItDown | 0.949 | 0.023 | 0.701 |
| Readability | 0.760 | 0.008 | 0.645 |

Paired bootstrap, coverage − Trafilatura, BM25 hit@5 +0.084 [+0.045, +0.123], chrome −0.010 [−0.014, −0.006];
dense hit@5 +0.010 [−0.024, +0.047] (tie), chrome −0.007 [−0.011, −0.004]. MarkItDown retrieves slightly better with BM25
(+0.033) because it keeps everything, with 23 times more chrome in the retrieved context.

Documentation corpus (data/raw, not held out), BM25, 242 pages: coverage hit@5 0.940, Trafilatura 0.921, MarkItDown
0.964, Readability 0.776; chrome in context 0.002 / 0.006 / 0.025 / 0.006.

### Second judge run: stratified WCXB test sample (2026-10-02)

105 WCXB test pages (15 per page type, seed 7), ChromeRAG balanced against three baselines, 384 judgements, same
model, prompt and blinding; position consistency 83% (69 repeated pairs). Cost $0.298; total OpenAI spend $1.681.

| vs | ChromeRAG wins | baseline wins | net win rate [95% CI] | content (1-5) ours / theirs | chrome-free (1-5) ours / theirs |
|---|---|---|---|---|---|
| Trafilatura | 56% | 42% | +0.14 [−0.05, +0.33] | 4.15 / 3.70 | 3.90 / 4.11 |
| MarkItDown | 83% | 17% | +0.66 [+0.51, +0.79] | 4.08 / 3.25 | 4.41 / 1.23 |

By page type (ChromeRAG wins / baseline wins, 15 pages each), vs Trafilatura: article 40% / 60%, documentation 33% /
67%, listing 33% / 53%, collection 73% / 27%, service 73% / 27%, product 67% / 33%, forum 73% / 27%.
Reading: on the mixed WCXB sample the judge's preference over Trafilatura is not significant (the interval includes
zero); it favours ChromeRAG on forum, product, collection and service pages and Trafilatura on articles,
documentation and listings. This agrees with the F1 ties on articles and documentation, and it is the more
conservative of the two judge results (the landing-page sample, 70% vs 28%, is marketing pages only).
The coverage of all evaluation sets is in `EVALUATION_COVERAGE.md` and `evaluation_domains.csv`.

---

## Audit after the final run (2026-10-02): duplicates between WCXB dev and test

Found while preparing the paper (a reviewer-style check of the split):

* 138 of the 511 WCXB test pages have the same URL as a development page, and 139 have byte-identical HTML (SHA-1).
  They include 26 of the 28 product pages and 25 of the 34 collection pages. 166 test pages (155 of 473 domains) are
  on a domain that also occurs in development. The final model was trained on all of development, so it saw these
  pages. The overall test score hardly changes (0.902 on all 511, 0.903 on the 373 pages not in development), but the
  per-type claims for products and collections on the test split were contaminated.
* Primary test result is therefore the 372 deduplicated pages (`FINAL/wcxb_test_deduplicated.json`): balanced 0.903,
  Trafilatura 0.867, Readability 0.778, MarkItDown 0.567; difference to Trafilatura +0.036 [+0.018, +0.054]. By type:
  forum +0.153 [+0.091, +0.219] (clear); collection +0.071 [+0.025, +0.117] (n = 9); article −0.003, documentation +0.023,
  service +0.025, listing +0.062 (intervals contain zero); product n = 2. Domains absent from development (345 pages):
  0.903 vs 0.874, +0.029 [+0.012, +0.046]. Domain-clustered bootstrap on all 511: +0.043 [+0.027, +0.060].
* The earlier statement "large gains on forums, product and collection pages" is withdrawn for product pages. Cross-
  validated development gains: product +0.026, collection +0.087, forum +0.108.
* Judge sample on WCXB test: 33 of the 105 pages were duplicates (14 product, 11 collection, 5 article, 2 listing, 1
  documentation). On the other 72 pages: ChromeRAG 53% vs Trafilatura 44% (interval includes zero), 79% vs MarkItDown 21%
  (`FINAL/llm_judge_wcxb_test_deduplicated.json`).
* Landing held-out and fresh companies: 11 of 42 and 9 of 47 registrable domains occur in WCXB development. On pages from
  other domains coverage − Trafilatura is +0.052 [+0.017, +0.086] (130 held-out pages) and +0.136 [+0.105, +0.167]
  (147 fresh pages) (`FINAL/landing_unseen_domain.json`); the full-set differences are +0.079 and +0.131.
* Documentation corpus rerun (2026-10-02, `data/raw` re-fetched): anchor F_bal 0.833 (coverage), 0.798 (balanced),
  Trafilatura 0.739, MarkItDown 0.696, Readability 0.531; BM25 hit@5 0.947 / 0.935 / 0.921 / 0.964 / 0.775
  (supersedes the 0.940 in the first run above). STCE rerun: 11 groups, 49 pages, F_bal 0.868 -> 0.870; crawl 125 groups,
  1,791 pages, 314 changed, 0.876 -> 0.877, repeated 5-grams per page 12.6 -> 12.3; 13 pages lose more than 0.05 recall.
* Heuristic-only ablation and speed table: see the earlier sections; speed bench 36 / 30 / 30 / 37 ms (ChromeRAG /
  Trafilatura / Readability / MarkItDown), p95 108 vs 147 ms, Apple M4 Pro 48 GB, Python 3.14.7.

### Corrections (2026-10-02, after the audits)

* The first dev cross-validation tables above (0.846 / 0.845 / 0.833, bootstrap +0.028) are from before the final model
  features; the final cross-validated numbers are 0.852 / 0.851 / 0.837 (`wcxb_dev_cv.json`, bootstrap +0.029 / +0.028 / +0.016).
* Documentation-corpus BM25 hit@5 (coverage) is 0.947 in the final rerun; 0.940 above is the first run.
* Audit result: scored on the benchmark's own script, ChromeRAG's raw default output (with YAML front-matter) gives 0.869
  on the 372 clean test pages and 0.904 with `enable_schema=False`; the paper reports the front-matter-stripped score and says so.
* LLM judge on the landing pages by subsample: held-out 62% vs 36% (Trafilatura), 80% vs 20% (MarkItDown); fresh 78% vs 20%
  and 94% vs 4%. WCXB sample without duplicates (72 pages): Readability 68% vs 28% (49 / 20 pairs).
* Clean test definition: ids absent from the public dev/ folder (`poc/wcxb_leaked_ids.json`, 139 ids) leaves 372 pages
  (an earlier URL-based filter gave 373).

### 0.1.4 close-out (2026-10-03)

* Speed: the new chrome passes raised the median from 36 to 76 ms. Size gates, ancestor sets and a text-after index in
  `generic_chrome.py`/`trafilatura_ideas.py`/`treestats.py` bring it to about 52 ms (Trafilatura 32, Readability 31, MarkItDown 39;
  `speed_final.json`, Apple M4 Pro, Python 3.14.7) and a page nested 20,000 levels deep from 79 s to 2 s; the test suite runs in 83 s
  instead of 270 s. Checked before any score was touched: 960 output hashes (3 modes x 320 pages) equal to the previous code, the 972
  judged outputs unchanged, 195 tests and ruff clean. No judge call was repeated.
* STCE rerun on the 0.1.4 pipeline: 11 benchmark groups (47 scoreable pages) F_bal 0.840 without / 0.837 with the site model; crawl
  125 groups, 1,727 scoreable pages, 138 changed: 0.866 / 0.867 (Trafilatura 0.841, MarkItDown 0.749); site-repeated text 2.0% / 2.0%.
* Manuscript review by one language model (private notes) led to: 135 seed sites listed vs 106 that responded (the text said 106 for both),
  masking details for the judges, a domain-clustered interval for the main F1 gap (+0.019 to +0.062, 316 domains), and a note that the
  retrieval queries are self-retrieval. Not addressed by new data: no human judges, no answer-level RAG evaluation.
* Fig. 5 (judge results) had colliding labels; it is now Fig. 4 of the manuscript (retrieval bars dropped from the paper to keep within 4,000 words).
