# Final results

Each folder holds one test and nothing else.

- `wcxb_test/`: WCXB test split, 511 pages, run once. Planned result.
- `answer_test_locked_planned/`: CRAG split 1, 500 questions, run once with the original grader. Planned result.
- `answer_test_regrade_posthoc/`: the same saved answers regraded under `RUBRIC.md` (tag `rubric-2026-11`). Post hoc: reported beside the planned result, never instead of it. Includes the practice split.
- `answer_test_practice/`: CRAG split 0, 500 questions. Practice data, consulted during development; not evidence for the locked claim.
- `new_pages/`: extraction summary and blind page judging on the 296 pages kept by `page_filter.json`.
- `held_out_runs.jsonl`: ledger of held-out runs.

Voided and crashed runs are not kept here. They are disclosed in the author-held audit record and the manuscript where relevant.
