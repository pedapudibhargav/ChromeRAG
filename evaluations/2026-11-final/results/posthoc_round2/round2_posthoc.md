# Post hoc analyses, revision round 2 (2026-11-20)

POST HOC (revision round 2, 2026-11-20). Computed from existing per-page results, ratings and saved HTML after all results had been seen; no extraction, no new scoring, no model call. Not in any pre-registered plan.

## 1. Human set pages on WCXB development domains

development domain = registrable domain (PSL) of any WCXB page: strict training page, WCXB test page (test split consulted in v0.1.3-v0.1.4 development) or other WCXB dev/ page; category order: training, then test, then other dev.

Pages on development domains: 34 of 75 (20 of 48 registrable domains); by category: no_wcxb_domain 41, strict_training_domain 20, test_split_domain 14. Forum pages on development domains: 5 of 10. Test-split-only domains: amazon.com, docker.com, github.com, microsoft.com, mit.edu, nih.gov, oracle.com.

| Pair | Subset | Net [95% CI] (W/L/T; pages, sites) |
|---|---|---|
| chromerag_vs_trafilatura | all_pages | +0.23 [+0.01, +0.42] (32/15/28; 75 pages, 48 sites) |
| chromerag_vs_trafilatura | pages_on_development_domains | +0.24 [-0.13, +0.54] (15/7/12; 34 pages, 20 sites) |
| chromerag_vs_trafilatura | pages_on_test_split_domains_only | +0.14 [-0.56, +0.61] (6/4/4; 14 pages, 7 sites) |
| chromerag_vs_trafilatura | clean_pages_no_wcxb_domain | +0.22 [-0.05, +0.46] (17/8/16; 41 pages, 28 sites) |
| chromerag_vs_trafilatura | clean_pages_without_forums | +0.14 [-0.15, +0.41] (13/8/15; 36 pages, 25 sites) |
| chromerag_vs_trafilatura | clean_forum_pages | +0.80 [+0.50, +1.00] (4/0/1; 5 pages, 3 sites) |
| chromerag_vs_readability | all_pages | +0.33 [+0.13, +0.52] (38/13/24; 75 pages, 48 sites) |
| chromerag_vs_readability | pages_on_development_domains | +0.38 [+0.06, +0.66] (19/6/9; 34 pages, 20 sites) |
| chromerag_vs_readability | pages_on_test_split_domains_only | +0.43 [-0.20, +0.81] (7/1/6; 14 pages, 7 sites) |
| chromerag_vs_readability | clean_pages_no_wcxb_domain | +0.29 [+0.03, +0.54] (19/7/15; 41 pages, 28 sites) |
| chromerag_vs_readability | clean_pages_without_forums | +0.28 [+0.00, +0.54] (16/6/14; 36 pages, 25 sites) |
| chromerag_vs_readability | clean_forum_pages | +0.40 [-0.50, +1.00] (3/1/1; 5 pages, 3 sites) |

Forum pages: human-0140 microsoft.com (test_split_domain, majority tie); human-0141 microsoft.com (test_split_domain, majority a); human-0145 repost.aws (no_wcxb_domain, majority a); human-0146 repost.aws (no_wcxb_domain, majority a); human-0148 python.org (strict_training_domain, majority a); human-0150 python.org (strict_training_domain, majority a); human-0153 pytorch.org (no_wcxb_domain, majority a); human-0157 ubuntu.com (no_wcxb_domain, majority a); human-0158 ubuntu.com (no_wcxb_domain, majority tie); human-0160 docker.com (test_split_domain, majority a).

## 2. WCXB test forum gain by platform seen in training

Rule: host on the Stack Exchange network -> stackexchange; else first matching HTML marker in PLATFORM_RULES (poc/rev1_round2_posthoc.py); else not_identified. Seen = the rule finds the platform on at least one strict training page labelled forum.

Strict training forum pages: 100; by platform: xenforo 27, discourse 21, invision 8, phpbb 7, stackexchange 6, nodebb 3, vbulletin 2, smf 1, flarum 1, mybb 1, vanilla 1.
Rule history: A first version of the rule checked product names that can occur in page text before asset-path markers; it classed the one Vanilla training page (which names other forum products in its text) as Flarum and one XenForo training page as vBulletin. Under that version 15 test forum pages were 'not seen', balanced - Trafilatura +0.111 [-0.014, +0.246]. The rule was reordered after seeing this, so the split is sensitive to the rule; both versions are reported.
Test forum pages by platform: xenforo 14, stackexchange 11, bbpress 6, not_identified 4, vbulletin 3, phpbb 2, vanilla 2, jforum 2, wpforo 2, discourse 1, ubbthreads 1, gainsight_insided 1, invision 1, khoros 1.

| Group | Balanced − Trafilatura F1 [95% CI] |
|---|---|
| all_forum_pages | +0.149 [+0.092, +0.230] (51 pages, 38 sites) |
| seen_in_training_forum_pages | +0.157 [+0.099, +0.249] (34 pages, 25 sites) |
| not_seen_in_training | +0.059 [-0.071, +0.187] (13 pages, 9 sites) |
| not_identified | +0.376 [+0.013, +0.738] (4 pages, 4 sites) |
| not_seen_or_not_identified | +0.133 [-0.002, +0.298] (17 pages, 13 sites) |
| seen_without_stackexchange | +0.210 [+0.143, +0.277] (23 pages, 23 sites) |

| Platform | Balanced − Trafilatura F1 [95% CI] |
|---|---|
| xenforo | +0.183 [+0.105, +0.265] (14 pages, 14 sites) |
| stackexchange | +0.046 [-0.018, +0.052] (11 pages, 2 sites) |
| bbpress | +0.049 [+0.006, +0.093] (6 pages, 3 sites) |
| not_identified | +0.376 [+0.013, +0.738] (4 pages, 4 sites) |
| vbulletin | +0.234 [+0.153, +0.342] (3 pages, 3 sites) |
| phpbb | +0.108 [+0.070, +0.147] (2 pages, 2 sites) |
| vanilla | +0.451 [+0.396, +0.506] (2 pages, 2 sites) |
| jforum | +0.358 [+0.358, +0.358] (2 pages, 1 sites) |
| wpforo | -0.054 [-0.062, -0.046] (2 pages, 2 sites) |
| discourse | +0.000 [+0.000, +0.000] (1 pages, 1 sites) |
| ubbthreads | +0.291 [+0.291, +0.291] (1 pages, 1 sites) |
| gainsight_insided | -0.387 [-0.387, -0.387] (1 pages, 1 sites) |
| invision | +0.443 [+0.443, +0.443] (1 pages, 1 sites) |
| khoros | -0.039 [-0.039, -0.039] (1 pages, 1 sites) |

## 3. Old-code control (0.1.5 minus freeze-0.1.3 code with the 0.1.5 model, 511 pages)

f1 -0.0015 [-0.0083, +0.0047]; without -0.0219 [-0.0336, -0.0109]; with -0.0350 [-0.0490, -0.0219]. Source: results/revision_rows/p03_extra_rows.json all_511 (paired chromerag_balanced_minus_old013_balanced).

## 4. WCXB test-split use after the freeze-0.1.3 run (Table S1a)

Full 511-page F1 scorings: 12 (rows 7, 8, 9, 11, 12, 18, 19, 28, 30, 32, 46, 47). Subset re-scorings: rows [6, 31]. AI-judge runs on test pages only: 8 (rows 3, 22, 26, 34, 37, 51, 52, 53); on mixed sets that include test pages: 2 (rows 16, 17); derived subsets, not separate runs: rows 5. By judge: gpt-5.6-luna 3, Claude Sonnet 5.5 7.
