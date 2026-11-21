# Feature-group ablation of the learned block filter (strict development pages)

Reviewer question: what the design adds beyond a shallow-feature learned block detector
(Kohlschuetter et al. 2010, BoilerPy3) with the training data held equal. Each row is a full
five-fold retrain (folds grouped by registrable domain, same hyperparameters as the shipped
model) on the 1,238 strict WCXB dev pages; the rest of the pipeline is unchanged. Balanced
priority (threshold 0.50). Deltas are row minus full, paired site bootstrap (5,000 draws,
seed 0), 95% interval. Lower without-snippet rate is better. Code: `poc/feature_group_ablation.py`.

Feature groups (535 features in total; exact indices in the JSON):

| Group | Features | Contents |
|---|---|---|
| shallow_text | 18 | block's own shallow text statistics: lengths, word/char ratios, capitalisation, punctuation, stop-word ratio, sentence count, link density and link count, emphasis share |
| neighbour_shallow | 4 | length and link density of the previous and next block |
| position | 6 | relative position in the page (block index, characters before/after), page size, block length relative to the page median |
| dom_context | 46 | tag of the block, depth, ancestor-tag flags (main, article, nav, footer, ...), inside the detected content root, enclosing-box statistics, same-box neighbours, sibling counts, repeated-structure counts |
| class_id_hash | 192 | hashed words of the class/id attributes of the block and up to 8 ancestors (192 buckets) |
| heading_context | 195 | distance to the previous heading, h1 seen / before first h1, hashed words of the nearest heading and of the nearest h1-h3 (2 x 96 buckets) |
| lexical_cues | 68 | fixed word lists (chrome words, call-to-action verbs, month/date patterns) and hashed first two words of the block (64 buckets) |
| page_relations | 6 | duplicate text elsewhere on the page and word overlap with title, meta description and the page's long blocks |

Reproduction: the `full` row matches the saved strict CV scores on all 1238 pages (0 pages differ in F1; saved mean F1 0.8593, without 0.0552), and the filter-only `full` row matches the saved filter-only ablation row. Rows: `minus_<group>` drops one group; `shallow_only` = shallow_text + neighbour_shallow; `shallow_plus_position` adds position; `shallow_plus_context` adds position, dom_context and heading_context (so it keeps the hashed heading words but not the hashed class/id words, lexical cues or page relations).

## Full pipeline

| Row | Feat. | F1 | dF1 [95% CI] | without | dWithout [95% CI] | article F1 | forum F1 | d article F1 | d forum F1 |
|---|---|---|---|---|---|---|---|---|---|
| full | 535 | 0.8593 | - | 0.0552 | - | 0.9444 | 0.8006 | - | - |
| minus_shallow_text | 517 | 0.8609 | +0.0016 [-0.0005, +0.0039] | 0.0572 | +0.0020 [-0.0011, +0.0053] | 0.9453 | 0.8034 | +0.0009 | +0.0028 |
| minus_neighbour_shallow | 531 | 0.8590 | -0.0002 [-0.0020, +0.0017] | 0.0573 | +0.0022 [-0.0004, +0.0049] | 0.9435 | 0.8003 | -0.0009 | -0.0003 |
| minus_position | 529 | 0.8570 | -0.0022 [-0.0047, +0.0002] | 0.0590 | +0.0039 [+0.0004, +0.0074] | 0.9422 | 0.7958 | -0.0022 | -0.0048 |
| minus_dom_context | 489 | 0.8517 | -0.0076 [-0.0116, -0.0038] | 0.0657 | +0.0105 [+0.0060, +0.0151] | 0.9383 | 0.7985 | -0.0061 | -0.0021 |
| minus_class_id_hash | 343 | 0.8574 | -0.0019 [-0.0044, +0.0006] | 0.0555 | +0.0004 [-0.0023, +0.0031] | 0.9436 | 0.7862 | -0.0008 | -0.0143 |
| minus_heading_context | 340 | 0.8598 | +0.0005 [-0.0017, +0.0027] | 0.0544 | -0.0008 [-0.0035, +0.0020] | 0.9430 | 0.7979 | -0.0014 | -0.0027 |
| minus_lexical_cues | 467 | 0.8589 | -0.0004 [-0.0021, +0.0016] | 0.0567 | +0.0015 [-0.0011, +0.0043] | 0.9444 | 0.8000 | +0.0000 | -0.0005 |
| minus_page_relations | 529 | 0.8597 | +0.0004 [-0.0013, +0.0024] | 0.0577 | +0.0025 [+0.0000, +0.0051] | 0.9430 | 0.7984 | -0.0014 | -0.0022 |
| shallow_only | 22 | 0.8435 | -0.0157 [-0.0206, -0.0113] | 0.0873 | +0.0321 [+0.0259, +0.0384] | 0.9262 | 0.7813 | -0.0183 | -0.0193 |
| shallow_plus_position | 28 | 0.8448 | -0.0145 [-0.0193, -0.0097] | 0.0736 | +0.0184 [+0.0129, +0.0243] | 0.9300 | 0.7797 | -0.0145 | -0.0208 |
| shallow_plus_context | 269 | 0.8573 | -0.0020 [-0.0047, +0.0009] | 0.0596 | +0.0045 [+0.0012, +0.0077] | 0.9433 | 0.7929 | -0.0011 | -0.0076 |

## Filter only (rules, chrome pruning off)

| Row | Feat. | F1 | dF1 [95% CI] | without | dWithout [95% CI] | article F1 | forum F1 | d article F1 | d forum F1 |
|---|---|---|---|---|---|---|---|---|---|
| full | 535 | 0.8404 | - | 0.2043 | - | 0.9218 | 0.7489 | - | - |
| minus_shallow_text | 517 | 0.8432 | +0.0028 [-0.0003, +0.0058] | 0.2056 | +0.0013 [-0.0041, +0.0068] | 0.9229 | 0.7530 | +0.0011 | +0.0041 |
| minus_neighbour_shallow | 531 | 0.8409 | +0.0005 [-0.0014, +0.0024] | 0.2080 | +0.0038 [-0.0009, +0.0084] | 0.9208 | 0.7515 | -0.0011 | +0.0026 |
| minus_position | 529 | 0.8423 | +0.0019 [-0.0013, +0.0052] | 0.2049 | +0.0006 [-0.0058, +0.0070] | 0.9241 | 0.7443 | +0.0023 | -0.0046 |
| minus_dom_context | 489 | 0.8152 | -0.0253 [-0.0304, -0.0202] | 0.2719 | +0.0677 [+0.0574, +0.0785] | 0.8968 | 0.7378 | -0.0250 | -0.0111 |
| minus_class_id_hash | 343 | 0.8421 | +0.0017 [-0.0022, +0.0061] | 0.2056 | +0.0014 [-0.0050, +0.0078] | 0.9235 | 0.7359 | +0.0017 | -0.0130 |
| minus_heading_context | 340 | 0.8401 | -0.0004 [-0.0030, +0.0022] | 0.2085 | +0.0042 [-0.0012, +0.0099] | 0.9198 | 0.7494 | -0.0020 | +0.0005 |
| minus_lexical_cues | 467 | 0.8403 | -0.0002 [-0.0022, +0.0019] | 0.2138 | +0.0095 [+0.0042, +0.0150] | 0.9222 | 0.7443 | +0.0003 | -0.0047 |
| minus_page_relations | 529 | 0.8417 | +0.0012 [-0.0009, +0.0033] | 0.2030 | -0.0013 [-0.0065, +0.0037] | 0.9229 | 0.7475 | +0.0011 | -0.0014 |
| shallow_only | 22 | 0.7996 | -0.0409 [-0.0479, -0.0340] | 0.3898 | +0.1855 [+0.1704, +0.2008] | 0.8777 | 0.7120 | -0.0441 | -0.0370 |
| shallow_plus_position | 28 | 0.7920 | -0.0485 [-0.0545, -0.0425] | 0.3404 | +0.1362 [+0.1230, +0.1497] | 0.8759 | 0.7188 | -0.0460 | -0.0301 |
| shallow_plus_context | 269 | 0.8413 | +0.0009 [-0.0033, +0.0058] | 0.2104 | +0.0061 [-0.0004, +0.0128] | 0.9220 | 0.7391 | +0.0002 | -0.0099 |

## Summary

With the rest of the pipeline unchanged, a model restricted to the 22 Kohlschuetter-style shallow features (the block's own plus the previous and next block's) scores F1 0.8435 against 0.8593 for the full 535-feature model (-0.0157 [-0.0206, -0.0113]) and lets more chrome through (without-snippet rate 0.0873 against 0.0552); with the filter alone the gap is larger (-0.0409 F1, without rate 0.390 against 0.204). Nearly all of that gap is recovered by adding position, DOM-tree and heading context while leaving out the hashed class/id words, lexical cues and page relations (shallow_plus_context: -0.0020 [-0.0047, +0.0009] F1, +0.0045 without rate), and DOM-tree context is the only group whose removal from the full model clearly lowers F1 (-0.0076 in the pipeline, -0.0253 filter only); dropping any other single group moves F1 by at most 0.0022 with intervals covering zero, though the hashed class/id words matter on forum pages (-0.0143 [-0.0255, -0.0053]). The block's own shallow text features are redundant given the rest (removing them leaves F1 unchanged, +0.0016 [-0.0005, +0.0039]), so on these pages the feature design adds a moderate 1.6 F1 points over a shallow learned detector trained on the same data, and that gain comes from structural context rather than from the large hashed vocabularies.
