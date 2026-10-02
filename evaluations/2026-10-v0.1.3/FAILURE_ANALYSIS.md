# Why ChromeRAG loses where it loses (WCXB dev, 1,495 pages), and what was done

All numbers: word-level F1 against the human-reviewed `main_content`, models from 5-fold cross-validation
grouped by site (a page is scored by a model that never saw its site). Commands are in `WORKLOG.md`.
Scripts: `poc/wcxb_diag.py`, `poc/wcxb_cv_report.py`, `poc/wcxb_errors.py`, `poc/wcxb_frontier.py`,
`poc/wcxb_trafilatura_variants.py`.

## 1. Where reference words are lost before the classifier sees them

Share of reference words still present after each stage (mean over pages):

| type | raw DOM | + hidden removal | + noise prune | block list (before fix) | block list (after loose-text fix) |
|---|---|---|---|---|---|
| article | 0.999 | 0.997 | 0.990 | 0.981 | 0.996 |
| documentation | 0.995 | 0.980 | 0.971 | 0.967 | 0.993 |
| service | 0.999 | 0.970 | 0.916 | 0.899 | 0.981 |
| collection | 0.993 | 0.961 | 0.918 | 0.833 | 0.946 |
| listing | 0.983 | 0.964 | 0.900 | 0.858 | 0.945 |
| forum | 0.944 | 0.940 | 0.930 | 0.866 | 0.937 |
| product | 0.990 | 0.962 | 0.920 | 0.883 | 0.965 |

Cause of the block-list loss: text that sits between block elements (`<div>Price: $5 <p>..</p></div>`) belonged to no
block. Fix: wrap such runs in `<p>` (`blockfeatures.wrap_loose_text`). Block-list recall ceiling 0.936 -> 0.981.

Noise prune: which rule removed how many reference-matching words (word trigrams found in the reference) versus
other words. Mostly good (tag `footer` 1% reference, `nav` 5%, `menu` 4%); the costly ones are class word `header`
(17%), `promo` (34%), `ad` (56%), `aside` (40%), `banner`/`cta` (15%). Moving those rules from "delete" to "flag for the
model" did not improve F1 (0.849 vs 0.851 on held-out sites), nor did flagging hidden elements (0.847) or all pruned
elements (0.829): the learned filter is less precise on obvious chrome than the rules, so the rules stay.

## 2. Mistakes of the classifier (words, threshold 0.5)

Articles: 1.46 M words kept correctly, 105 k wrongly kept, 30 k wrongly dropped.
Wrongly kept: prose paragraphs 39% (related-article teasers, author bios, promo copy), list items 17% (link lists),
navigation/footer-like 12%, comments 5.5%, code 4.6%. Wrongly dropped: prose paragraphs 43% (borderline scores
0.4-0.5), list items 18%, other text blocks 10%.
Documentation: wrongly kept 17 k words, of which code 66% and navigation 16%; wrongly dropped 11.5 k, of which code 76%.
Code is in the reference for 82% of documentation pages that have it, but annotators left out repeated "live sample"
code (MDN) and playground code; this is label inconsistency, not a feature gap.
Whole corpus: wrongly kept = prose 33%, lists 16%, navigation 10%, code 9%, other 9%, comments 6%.

## 3. What the literature suggests, and whether it helped here

| Idea (source) | Result on WCXB dev |
|---|---|
| Page-type routing with an ML classifier (rs-trafilatura, WCXB paper) | Oracle page type as a model input: +0.0035 block-level F1; per-type mode choice about +0.005. Not adopted. |
| JSON-LD fallback for products (WCXB paper) | Reference words missing from the visible DOM: 0.1-0.8% (forums 6.6%), found in JSON-LD: about 0. No gain possible. |
| Comments are content on forums, boilerplate on articles (WCXB paper) | The model learns this from ancestor names and repeated-structure features; forum F1 0.675 (Trafilatura) -> 0.783. |
| Block-level labelling of simplified HTML (Dripper/MinerU-HTML) | Same granularity; trees over about 500 features instead of a 0.6B model. |
| Word and tag sequences (Web2Text, BoilerNet) | A hashed bag-of-words block model added nothing (AUC 0.910 vs 0.913). |
| Context across blocks (sequence labelling) | Second stage on neighbour/box probabilities, box-mean mixing, heading smoothing, orphan-heading removal: all within +-0.002. |
| Confidence score with fallback (rs-trafilatura) | Implemented as `diagnostics["lbc"]` and a warning below expected F1 0.70 (below): flagged pages score 0.57 on average, the rest 0.88. |
| Density/link/tag-weight pruning (Crawl4AI `PruningContentFilter`) | This is the 0.1.2 heuristic filter; learned filter beats it by +0.024 to +0.043 F1. |
| Take the best of several extractors (Trafilatura's Readability/jusText fallback) | Not adopted: adds dependencies; the collapse fallback already retries with body root. |

## 4. Confidence (balanced mode, held-out fold models)

Pearson correlation between expected F1 and actual F1: 0.60. Flagging expected F1 < 0.70: 7.6% of pages, mean actual F1
0.57 vs 0.88 for the rest, 32% of the poor pages (F1 < 0.6) caught at 46% precision. At < 0.80: 14.5% flagged, 53% of poor
pages caught at 41% precision. (rs-trafilatura reports 35% of poor pages caught at 97% precision with a separate
regression model; the numbers are not comparable, protocols differ.)

## 5. Frontier (held-out fold models, balanced pipeline, word F1)

| threshold | 0.15 | 0.25 | 0.30 | 0.40 | 0.50 | 0.60 | 0.70 | 0.80 | 0.90 |
|---|---|---|---|---|---|---|---|---|---|
| precision | 0.811 | 0.822 | 0.828 | 0.838 | 0.846 | 0.856 | 0.865 | 0.875 | 0.875 |
| recall | 0.938 | 0.930 | 0.926 | 0.915 | 0.900 | 0.880 | 0.857 | 0.828 | 0.785 |
| F1 | 0.847 | 0.851 | 0.852 | 0.854 | 0.851 | 0.846 | 0.837 | 0.825 | 0.793 |

Trafilatura (best configuration) sits at P 0.855 / R 0.839 / F1 0.818: ChromeRAG's F1 is higher at every threshold up to 0.8,
and at thresholds 0.6-0.7 both its precision and its recall are higher. Trafilatura settings: defaults 0.814, tables+Markdown 0.818, favor_recall 0.789,
favor_precision 0.751 (the paper baseline is the best of them).

## 6. Comparison with published systems (not re-run)

WCXB paper (dev, tuned on dev, 1,497 pages): rs-trafilatura 0.859, MinerU-HTML 0.6B 0.827, Resiliparse 0.797,
Trafilatura 0.791, ReaderLM-v2 1.5B 0.741. Test (511 pages): rs-trafilatura 0.903, Trafilatura 0.841.
ChromeRAG's cross-validated dev F1 is 0.852 / 0.851 / 0.837 (coverage / balanced / precision). The two sets of numbers
differ in protocol (their Trafilatura scores 0.791, ours 0.818 with the best configuration, so the scales are not
interchangeable) and rs-trafilatura could not be built here (no Rust toolchain or crates.io access). Do not claim a
win over rs-trafilatura; claim parity-range accuracy with CPU-only pure-Python inference.
