# Final results

Each folder holds one test and nothing else.

- `wcxb_test/`: WCXB test split, 511 pages, run once. Planned result.
- `answer_test_locked_planned/`: CRAG split 1, 500 questions, run once with the original grader. Planned result.
- `answer_test_regrade_posthoc/`: the same saved answers regraded under `RUBRIC.md` (tag `rubric-2026-11`). Post hoc: reported beside the planned result, never instead of it. Includes the practice split.
- `answer_test_practice/`: CRAG split 0, 500 questions. Practice data, consulted during development; not evidence for the locked claim.
- `new_pages/`: extraction summary and blind page judging on the 296 pages kept by `page_filter.json`.
- `revision_rows/`: rows added for the revision on the WCXB test split (front matter, 372-page and domain-absent subsets, page types, with-snippet rate, freeze-0.1.3 code with the 0.1.5 model, jusText, BoilerPy3, speed). Each file is produced once by `poc/revision_rows.py`; `gt_manifest.json` hashes the local test ground truth.
- `revision_rows/trafilatura_options.json`: Trafilatura `favor_recall` and `favor_precision` rows and the saved version table (`poc/trafilatura_options.py`).
- `human_set_ai_judges/`: GPT, Grok and Gemini verdicts on the human rating set, saved before any rating was read.
- `human_set_analysis/`: post hoc analyses of the human rating set (robustness, training-domain overlap, history of the set, coded error analysis); the analysis fixed in advance runs from `../human_set_ratings/`.
- `posthoc_round2/`: post hoc checks for the second review round (`poc/rev1_round2_posthoc.py`): rated pages on WCXB development domains, WCXB forum gain by whether the forum platform occurs in training, the old-code control and exact held-out ledger counts. Computed from existing results only; nothing was re-extracted or re-judged.
- `held_out_runs.jsonl`: ledger of held-out runs. Times are local time with UTC offset (US Pacific), as written by the scripts, not UTC. The re-scoring of the WCXB test split on 2026-11-20 is recorded as a dated amendment in `../PROTOCOL.md`.

Voided and crashed runs are not kept here. They are disclosed in the author-held audit record and the manuscript where relevant.
