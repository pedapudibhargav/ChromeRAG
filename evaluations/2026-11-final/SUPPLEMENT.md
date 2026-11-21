# Supplementary material: ChromeRAG 0.1.5 (SoftwareX revision 1, SOFTX-D-26-01378)

Tables S1–S9 support the revised manuscript. Values are read by script (`poc/gen_supplement.py`) from the file named in each table note. Values marked "author record" come from the author's dated audit record and have no public file. Intervals are 95% percentile bootstrap intervals; "site" means registrable domain (Public Suffix List, `poc/psl.py`). Lower without-snippet ("without") rates are better; higher with-snippet rates are better. Code under test is tag `freeze-0.1.5` (commit `04cbb05`; model sha256 `2e2fecb9…c265c8e`, 152,432 bytes) unless a row says otherwise. Commits cited here are public through the tags `freeze-0.1.5`, `protocol-2026-11`, `protocol-2026-11a`, `pages-2026-11`, `rubric-2026-11`, `human-set-plan-2026-11` and `rater-kit-2026-11` and the release `v0.1.5`, except commit `3b4f43d` (AI verdicts on the human set, 2 November), the six protocol amendments made before rating (2 November: `841867c`, `f7f99f4`, `f00d5d5` careless-rating rule, `c93d0e4`, `1a6c1e6`; 3 November: `6da13d2` difference highlighting), the ablation harness commit `54477c5` and the 20 November harness commits `99c6612` and `cf380e5` recorded in result files; these belong to the author's private development history and are available to the editor on request. The amended protocol text itself is public in `PROTOCOL.md`, and the rating-kit side of these amendments (layout, three parts with shared anchor pages, task explanation, difference highlighting) is public through `rater-kit-2026-11` (commit `69981e8`, app 1.1.0 as sent to raters).

## Table S1. Held-out ledger

### S1a. Runs on held-out or later-held-out sets during v0.1.3 and v0.1.4 development (October 2026)

Source: `evaluations/2026-10-v0.1.3/HELD_OUT_LEDGER.csv` (53 rows, all shown), with output hashes per round in `held_out_round_hashes.json`. "uncommitted tree" means the code was a working tree that was not kept; the nearest commit is a lower bound. Prompt hash `6f502417…` is the v0.1.4 judge prompt (`poc/claude_judge_build.py`). Temperatures of these rounds were not recorded. Claude rounds ran through sub-agents (no fixed API configuration). Rows with result "deleted" are batches whose files were deleted; their summary values were recovered from git history.

| # | Time (Pacific) | Set | Pages | Code | Judge | Route | Prompt | Net | Result file | Note |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-02T08:45:26-07:00 | wcxb_test | 511 | 2d436bb | n/a | n/a | n/a | n/a | wcxb_test.json | WORKLOG: WCXB test run once 2026-10-02 commit 2d436bb tagged freeze-0.1.3; mtime matches freeze minute; primary metric is word F1 balanced 0.902 (WORKLOG), not a judge net |
| 2 | 2026-10-02T08:58:31-07:00 | landing_heldout+fresh | 100 | b1432c3 | gpt-5.6-luna | openai_api | 6f502417… | 0.420000 | llm_judge_final.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T08:47:18-07:00; Record final WCXB test results); WORKLOG: 100 pages (50 held-out + 50 fresh); n_judgements in file; temperature not passed in poc/openai_client.chat_json payload; WORKLOG: landing/fresh judge after freeze; recorded in commit b1432c3 |
| 3 | 2026-10-02T10:21:37-07:00 | wcxb_test | 105 | 0652236 | gpt-5.6-luna | openai_api | 6f502417… | 0.143000 | llm_judge_wcxb_test.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T10:16:34-07:00; Release 0.1.3); temperature not passed in poc/openai_client.chat_json payload; git log -- FINAL/llm_judge_wcxb_test.json -> 0652236 |
| 4 | 2026-10-02T14:54:26-07:00 | landing_heldout+fresh_unseen_domain | heldout_all=177; fresh_all=178; heldout_unseen=130; fresh_unseen=147 | 2d436bb | n/a | n/a | n/a | n/a | landing_unseen_domain.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T13:43:41-07:00; AI declaration: name the OpenAI models used for judging and ); audit filter of landing results; tool same as freeze evaluations (inferred) |
| 5 | 2026-10-02T14:56:46-07:00 | wcxb_test | 72 | 0652236 | gpt-5.6-luna | openai_api | 6f502417… | unknown | llm_judge_wcxb_test_deduplicated.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T13:43:41-07:00; AI declaration: name the OpenAI models used for judging and ); derived from llm_judge_wcxb_test.json excluding 33 duplicate pages; no per-judgement payload; commit inferred from git log of parent llm_judge_wcxb_test.json (0652236) |
| 6 | 2026-10-02T14:56:46-07:00 | wcxb_test | 372 | 2d436bb | n/a | n/a | n/a | n/a | wcxb_test_deduplicated.json | audit of freeze test split; tool commit same as wcxb_test.json (inferred); file records aggregate only |
| 7 | 2026-10-02T15:06 | wcxb_test | 511 | uncommitted tree | n/a | n/a | n/a | unknown | not kept | after robustness fixes |
| 8 | 2026-10-02T16:28 | wcxb_test | 511 | uncommitted tree | n/a | n/a | n/a | unknown | not kept | during output-quality work |
| 9 | 2026-10-02T16:45 | wcxb_test | 511 | uncommitted tree | n/a | n/a | n/a | unknown | not kept | coding task 1, scored on test after the change |
| 10 | 2026-10-02T16:55:23-07:00 | docs_final | 400 | f1523fe | Claude Sonnet 5.5 | anthropic_subagent | unknown | n/a | heading_context_retrieval.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T15:11:52-07:00; 0.1.4: robustness fixes (deep nesting, failing batch pages, ); held-out documentation corpus; n_pages column stores n_questions from file; questions written by blinded Claude judge; retrieval prompt hash not the judge SYSTEM hash |
| 11 | 2026-10-02T16:59 | wcxb_test | 511 | uncommitted tree | n/a | n/a | n/a | unknown | not kept | during output-quality work |
| 12 | 2026-10-02T17:00 | wcxb_test | 511 | uncommitted tree | n/a | n/a | n/a | unknown | not kept | coding task 3, scored on test after the change |
| 13 | 2026-10-02T17:14:31-07:00 | docs | 353 | 9b0afed | Claude Sonnet 5.5 | anthropic_subagent | 6f502417… | -0.036827 | deleted | deleted path was claude_judge_v014_docs.json; recovered summary.ALL from git show 4259080^; README superseded list; mtime unknown after delete |
| 14 | 2026-10-02T17:14:31-07:00 | docs | 354 | 9b0afed | Claude Sonnet 5.5 | anthropic_subagent | 6f502417… | 0.240113 | deleted | deleted path was claude_judge_v014b_docs.json; recovered summary.ALL from git show 4259080^; README superseded list; mtime unknown after delete |
| 15 | 2026-10-02T17:14:31-07:00 | products | 307 | 9b0afed | Claude Sonnet 5.5 | anthropic_subagent | 6f502417… | 0.355049 | deleted | deleted path was claude_judge_v014_products.json; recovered summary.ALL from git show 4259080^; README superseded list; mtime unknown after delete |
| 16 | 2026-10-02T17:17:23-07:00 | mix_wcxb_clean+docs_final+products_final | 248 | 9b0afed | Claude Sonnet 5.5 | anthropic_subagent | 6f502417… | 0.915323 | claude_judge_v014b_mix_markitdown.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); temperature not present in OpenAI client payload; Claude/Gemini temperature not recorded in repo; model name from manuscript judge paragraph; access via blinded sub-agent batches (poc/claude_judge_build.py); seeded mix over wcxb_clean+docs_final+products_final (poc/claude_judge_build pages('mix')) |
| 17 | 2026-10-02T17:17:23-07:00 | mix_wcxb_clean+docs_final+products_final | 248 | 9b0afed | Claude Sonnet 5.5 | anthropic_subagent | 6f502417… | 0.399194 | claude_judge_v014b_mix_readability.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); temperature not present in OpenAI client payload; Claude/Gemini temperature not recorded in repo; model name from manuscript judge paragraph; access via blinded sub-agent batches (poc/claude_judge_build.py); rival=readability; net is vs Readability not Trafilatura; seeded mix over wcxb_clean+docs_final+products_final (poc/claude_judge_build pages('mix')) |
| 18 | 2026-10-02T18:23 | wcxb_test | 511 | uncommitted tree | n/a | n/a | n/a | unknown | not kept | coding task 4, scored on test after the change; brief cites judge reasons from 223 lost comparisons (source sets not confirmed) |
| 19 | 2026-10-02T18:47 | wcxb_test | 511 | uncommitted tree | n/a | n/a | n/a | unknown | not kept | coding task 6, scored on test after the change; brief used judge reasons from WCXB test pages |
| 20 | 2026-10-02T19:04:56-07:00 | docs_final | 180 | uncommitted tree after 9b0afed, before d396e64 | gpt-5.6-luna | openai_api | 6f502417… | 0.122222 | gpt_judge_v014c_docs_final.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); temperature not present in OpenAI client payload; Claude/Gemini temperature not recorded in repo; model from poc/gpt_judge_batches.py / poc/run_llm_judge.py MODEL Code held coding-task changes not committed until d396e64. |
| 21 | 2026-10-02T19:04:56-07:00 | products_final | 97 | uncommitted tree after 9b0afed, before d396e64 | gpt-5.6-luna | openai_api | 6f502417… | 0.371134 | gpt_judge_v014c_products_final.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); temperature not present in OpenAI client payload; Claude/Gemini temperature not recorded in repo; model from poc/gpt_judge_batches.py / poc/run_llm_judge.py MODEL Code held coding-task changes not committed until d396e64. |
| 22 | 2026-10-02T19:04:56-07:00 | wcxb_clean | 369 | uncommitted tree after 9b0afed, before d396e64 | gpt-5.6-luna | openai_api | 6f502417… | 0.146341 | gpt_judge_v014c_wcxb_clean.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); temperature not present in OpenAI client payload; Claude/Gemini temperature not recorded in repo; model from poc/gpt_judge_batches.py / poc/run_llm_judge.py MODEL Code held coding-task changes not committed until d396e64. |
| 23 | 2026-10-02T19:05:07-07:00 | final2 | 328 | uncommitted tree after 9b0afed, before d396e64 | gpt-5.6-luna | openai_api | 6f502417… | 0.170732 | gpt_judge_v014c_final2.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); temperature not present in OpenAI client payload; Claude/Gemini temperature not recorded in repo; model from poc/gpt_judge_batches.py / poc/run_llm_judge.py MODEL; mtime in 19:05-19:48 window: code may have been uncommitted between 9b0afed (17:14) and d396e64 (20:26); 9b0afed checkout may not be the exact code of this round Code held coding-task changes not committed until d396e64. |
| 24 | 2026-10-02T19:05:07-07:00 | final2 | 328 | uncommitted tree after 9b0afed, before d396e64 | gpt-5.6-luna | openai_api | 6f502417… | 0.478659 | gpt_judge_v014c_final2_readability.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); temperature not present in OpenAI client payload; Claude/Gemini temperature not recorded in repo; model from poc/gpt_judge_batches.py / poc/run_llm_judge.py MODEL; rival=readability; net is vs Readability not Trafilatura; mtime in 19:05-19:48 window: code may have been uncommitted between 9b0afed (17:14) and d396e64 (20:26); 9b0afed checkout may not be the exact code of this round Code held coding-task changes not committed until d396e64. |
| 25 | 2026-10-02T19:16:50-07:00 | final2 | 328 | uncommitted tree after 9b0afed, before d396e64 | Claude Sonnet 5.5 | anthropic_subagent | 6f502417… | 0.429878 | claude_judge_v014d_final2.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); temperature not present in OpenAI client payload; Claude/Gemini temperature not recorded in repo; model name from manuscript judge paragraph; access via blinded sub-agent batches (poc/claude_judge_build.py); mtime in 19:05-19:48 window: code may have been uncommitted between 9b0afed (17:14) and d396e64 (20:26); 9b0afed checkout may not be the exact code of this round Code held coding-task changes not committed until d396e64. |
| 26 | 2026-10-02T19:16:51-07:00 | wcxb_clean | 369 | uncommitted tree after 9b0afed, before d396e64 | Claude Sonnet 5.5 | anthropic_subagent | 6f502417… | 0.135501 | claude_judge_v014d_wcxb_clean.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); temperature not present in OpenAI client payload; Claude/Gemini temperature not recorded in repo; model name from manuscript judge paragraph; access via blinded sub-agent batches (poc/claude_judge_build.py); mtime in 19:05-19:48 window: code may have been uncommitted between 9b0afed (17:14) and d396e64 (20:26); 9b0afed checkout may not be the exact code of this round Code held coding-task changes not committed until d396e64. |
| 27 | 2026-10-02T19:16:51-07:00 | final2 | 250 | uncommitted tree after 9b0afed, before d396e64 | gpt-5.6-luna | openai_api | 6f502417… | 0.136000 | gpt_judge_v014d_final2.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); temperature not present in OpenAI client payload; Claude/Gemini temperature not recorded in repo; model from poc/gpt_judge_batches.py / poc/run_llm_judge.py MODEL; mtime in 19:05-19:48 window: code may have been uncommitted between 9b0afed (17:14) and d396e64 (20:26); 9b0afed checkout may not be the exact code of this round Code held coding-task changes not committed until d396e64. |
| 28 | 2026-10-02T19:17 | wcxb_test | 511 | uncommitted tree | n/a | n/a | n/a | unknown | not kept | coding task 8; brief used judge reasons from WCXB test pages |
| 29 | 2026-10-02T19:48:07-07:00 | final2 | 328 | uncommitted tree after 9b0afed, before d396e64 | Gemini 3.7 Flash | unknown | 6f502417… | 0.475610 | gemini_judge_v014d_final2.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); temperature not present in OpenAI client payload; Claude/Gemini temperature not recorded in repo; model name from manuscript; no Gemini runner script in poc/, access route not recorded; mtime in 19:05-19:48 window: code may have been uncommitted between 9b0afed (17:14) and d396e64 (20:26); 9b0afed checkout may not be the exact code of this round Code held coding-task changes not committed until d396e64. |
| 30 | 2026-10-02T19:52 | wcxb_test | 511 | uncommitted tree | n/a | n/a | n/a | unknown | not kept | coding task 10, Trafilatura-inspired rule groups kept only if F1 held on test and dev: selection on test |
| 31 | 2026-10-02T20:26:21-07:00 | wcxb_clean | 372 | d396e64 tree | n/a | n/a | n/a | n/a | wcxb_clean_f1_v014_final.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); F1 re-score under 0.1.4 pipeline; not a judge net |
| 32 | 2026-10-02T20:26:21-07:00 | wcxb_test | 511 | d396e64 tree | n/a | n/a | n/a | n/a | wcxb_test_v014_final.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T17:14:31-07:00; Output quality: structure fixes, pipe tables, docs-framework); F1 re-score under 0.1.4 pipeline; not a judge net |
| 33 | 2026-10-02T20:37:49-07:00 | final2 | 328 | d396e64 | Claude Sonnet 5.5 | anthropic_subagent | 6f502417… | 0.414634 | claude_judge_final_final2.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T20:26:40-07:00; Chrome removal: generic structural rules, Trafilatura-inspir); latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T20:26:40-07:00; Chrome removal: generic structural rules, Trafilatura-inspir); temperature not present in OpenAI client payload; Claude/Gemini temperature not recorded in repo; model name from manuscript judge paragraph; access via blinded sub-agent batches (poc/claude_judge_build.py) |
| 34 | 2026-10-02T20:37:49-07:00 | wcxb_clean | 367 | d396e64 | Claude Sonnet 5.5 | anthropic_subagent | 6f502417… | 0.253406 | claude_judge_final_wcxb_clean.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T20:26:40-07:00; Chrome removal: generic structural rules, Trafilatura-inspir); latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T20:26:40-07:00; Chrome removal: generic structural rules, Trafilatura-inspir); temperature not present in OpenAI client payload; Claude/Gemini temperature not recorded in repo; model name from manuscript judge paragraph; access via blinded sub-agent batches (poc/claude_judge_build.py) |
| 35 | 2026-10-02T20:44:46-07:00 | final2 | 328 | d396e64 | gpt-5.6-luna | openai_api | 6f502417… | 0.192073 | gpt_judge_final_final2.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T20:26:40-07:00; Chrome removal: generic structural rules, Trafilatura-inspir); latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T20:26:40-07:00; Chrome removal: generic structural rules, Trafilatura-inspir); temperature not present in OpenAI client payload; Claude/Gemini temperature not recorded in repo; model from poc/gpt_judge_batches.py / poc/run_llm_judge.py MODEL |
| 36 | 2026-10-02T20:44:46-07:00 | final2 | 328 | d396e64 | gpt-5.6-luna | openai_api | 6f502417… | 0.524390 | gpt_judge_final_final2_readability.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T20:26:40-07:00; Chrome removal: generic structural rules, Trafilatura-inspir); latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T20:26:40-07:00; Chrome removal: generic structural rules, Trafilatura-inspir); temperature not present in OpenAI client payload; Claude/Gemini temperature not recorded in repo; model from poc/gpt_judge_batches.py / poc/run_llm_judge.py MODEL; rival=readability; net is vs Readability not Trafilatura |
| 37 | 2026-10-02T20:44:46-07:00 | wcxb_clean | 367 | d396e64 | gpt-5.6-luna | openai_api | 6f502417… | 0.223433 | gpt_judge_final_wcxb_clean.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T20:26:40-07:00; Chrome removal: generic structural rules, Trafilatura-inspir); latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T20:26:40-07:00; Chrome removal: generic structural rules, Trafilatura-inspir); temperature not present in OpenAI client payload; Claude/Gemini temperature not recorded in repo; model from poc/gpt_judge_batches.py / poc/run_llm_judge.py MODEL |
| 38 | 2026-10-02T20:45:27-07:00 | landing_fresh | 178 | d396e64 tree (rerun) | n/a | n/a | n/a | n/a | landing_comparison_fresh_report.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T20:26:40-07:00; Chrome removal: generic structural rules, Trafilatura-inspir); anchor F_bal in summary; net_overall n/a; WORKLOG: landing held-out/fresh scored once after freeze (commit b1432c3). mtime 2026-10-02T20:45:27-07:00 is later than that commit; may be a rewrite — commit_basis kept as worklog for the evaluation event Rerun after the rule changes; earlier run on b1432c3 was overwritten. |
| 39 | 2026-10-02T20:45:27-07:00 | landing_heldout | 177 | d396e64 tree (rerun) | n/a | n/a | n/a | n/a | landing_comparison_heldout_report.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T20:26:40-07:00; Chrome removal: generic structural rules, Trafilatura-inspir); anchor F_bal in summary; net_overall n/a; WORKLOG: landing held-out/fresh scored once after freeze (commit b1432c3). mtime 2026-10-02T20:45:27-07:00 is later than that commit; may be a rewrite — commit_basis kept as worklog for the evaluation event Rerun after the rule changes; earlier run on b1432c3 was overwritten. |
| 40 | 2026-10-02T20:45:27-07:00 | landing_heldout | 177 | d396e64 tree (rerun) | n/a | n/a | n/a | n/a | landing_comparison_heldout_summary.md | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T20:26:40-07:00; Chrome removal: generic structural rules, Trafilatura-inspir); markdown summary companion of the JSON report; WORKLOG: landing held-out/fresh scored once after freeze (commit b1432c3). mtime 2026-10-02T20:45:27-07:00 is later than that commit; may be a rewrite — commit_basis kept as worklog for the evaluation event Rerun after the rule changes; earlier run on b1432c3 was overwritten. |
| 41 | 2026-10-02T20:45:28-07:00 | landing_fresh | 178 | d396e64 tree (rerun) | n/a | n/a | n/a | n/a | fresh_retrieval_eval_report.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T20:26:40-07:00; Chrome removal: generic structural rules, Trafilatura-inspir); WORKLOG retrieval on fresh companies; cost includes embeddings in openai_spend.json aggregate Rerun after the rule changes; earlier run on b1432c3 was overwritten. |
| 42 | 2026-10-02T20:45:28-07:00 | landing_fresh | 178 | d396e64 tree (rerun) | n/a | n/a | n/a | n/a | landing_comparison_fresh_summary.md | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T20:26:40-07:00; Chrome removal: generic structural rules, Trafilatura-inspir); markdown summary companion of the JSON report; WORKLOG: landing held-out/fresh scored once after freeze (commit b1432c3). mtime 2026-10-02T20:45:28-07:00 is later than that commit; may be a rewrite — commit_basis kept as worklog for the evaluation event Rerun after the rule changes; earlier run on b1432c3 was overwritten. |
| 43 | 2026-10-02T20:47:01-07:00 | docs_final | 180 | d396e64 | gpt-5.6-luna | openai_api | 6f502417… | 0.066667 | gpt_judge_final_docs_final.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T20:26:40-07:00; Chrome removal: generic structural rules, Trafilatura-inspir); latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T20:26:40-07:00; Chrome removal: generic structural rules, Trafilatura-inspir); temperature not present in OpenAI client payload; Claude/Gemini temperature not recorded in repo; model from poc/gpt_judge_batches.py / poc/run_llm_judge.py MODEL |
| 44 | 2026-10-02T20:47:01-07:00 | products_final | 97 | d396e64 | gpt-5.6-luna | openai_api | 6f502417… | 0.402062 | gpt_judge_final_products_final.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T20:26:40-07:00; Chrome removal: generic structural rules, Trafilatura-inspir); latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T20:26:40-07:00; Chrome removal: generic structural rules, Trafilatura-inspir); temperature not present in OpenAI client payload; Claude/Gemini temperature not recorded in repo; model from poc/gpt_judge_batches.py / poc/run_llm_judge.py MODEL |
| 45 | 2026-10-02T20:49:54-07:00 | final2 | 328 | d396e64 | Gemini 3.7 Flash | unknown | 6f502417… | 0.448171 | gemini_judge_final_final2.json | latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T20:26:40-07:00; Chrome removal: generic structural rules, Trafilatura-inspir); latest freeze-0.1.3..v0.1.4 commit with author-date <= mtime (2026-10-02T20:26:40-07:00; Chrome removal: generic structural rules, Trafilatura-inspir); temperature not present in OpenAI client payload; Claude/Gemini temperature not recorded in repo; model name from manuscript; no Gemini runner script in poc/, access route not recorded |
| 46 | 2026-10-02T20:50 | wcxb_test | 511 | uncommitted tree | n/a | n/a | n/a | unknown | not kept | coding task 12, scored on test after the change, after the final judge round |
| 47 | 2026-10-02T21:32 | wcxb_test | 511 | uncommitted tree | n/a | n/a | n/a | unknown | not kept | coding task 13, speed work, outputs required byte-identical; scored on test |
| 48 | unknown | docs_final | 180 | 9b0afed | Claude Sonnet 5.5 | anthropic_subagent | 6f502417… | 0.094444 | deleted | old name claude_judge_v014b_docs_final.json; renamed/replaced by gpt_judge_final_docs_final.json in 4259080; summary.ALL from git show 4259080^; listed under README superseded patterns |
| 49 | unknown | products_final | 97 | 9b0afed | Claude Sonnet 5.5 | anthropic_subagent | 6f502417… | 0.474227 | deleted | old name claude_judge_v014b_products_final.json; renamed/replaced by gpt_judge_v014c_products_final.json in 4259080; summary.ALL from git show 4259080^; listed under README superseded patterns |
| 50 | unknown | unknown | unknown | unknown | Claude Sonnet 5.5 | anthropic_subagent | 6f502417… | unknown | deleted | FINAL/README.md lists claude_judge_v014c_*.json as deleted; no such path in git history (unknown whether ever written) |
| 51 | unknown | wcxb_clean | 369 | 9b0afed | Claude Sonnet 5.5 | anthropic_subagent | 6f502417… | -0.051491 | deleted | old name claude_judge_v014_wcxb_clean.json; renamed to claude_judge_final_wcxb_clean.json in 4259080; summary.ALL from git show 4259080^; listed under README superseded patterns |
| 52 | unknown | wcxb_clean | 369 | 9b0afed | Claude Sonnet 5.5 | anthropic_subagent | 6f502417… | 0.130081 | deleted | old name claude_judge_v014b_wcxb_clean.json; renamed to claude_judge_v014d_wcxb_clean.json in 4259080; summary.ALL from git show 4259080^; listed under README superseded patterns |
| 53 | unknown | wcxb_clean | 369 | 9b0afed | Claude Sonnet 5.5 | anthropic_subagent | 6f502417… | -0.130081 | deleted | old name claude_judge_wcxb_clean.json; renamed/replaced by gpt_judge_v014c_wcxb_clean.json in 4259080; early net matches manuscript -0.13; summary.ALL from git show 4259080^; listed under README superseded patterns |

Between the 328-page rounds, ChromeRAG output changed on most pages: see `held_out_round_hashes.json` (per-round output hashes; caveat recorded there: Judge rounds v014c/v014d ran at 19:05–19:48 on 2026-10-02 while the only committed extractor tip was 9b0afed (17:14); d396e64 landed at 20:26. The session log shows those rounds ran on a working tree already holding coding tasks 4 to 6, not on 9b0afed, and that tree was not kept. So 9b0afed is a lower bound on the code of those rounds, the differ counts overstate the change between rounds, and the winner split is indicative only.)

**Counts after the freeze-0.1.3 run (row 1)** (post hoc count from the ledger; `posthoc_round2/round2_posthoc.json`, key `ledger_counts`): 12 full scorings of the 511 test pages (rows 7, 8, 9, 11, 12, 18, 19, 28, 30, 32, 46, 47); 2 subset re-scorings (rows 6, 31; row 6 is an aggregate of the freeze run; row 31 accompanies row 32); 8 AI-judge runs on test pages only (rows 3, 22, 26, 34, 37, 51, 52, 53) and 2 on mixed sets that include test pages (rows 16, 17), by judge gpt-5.6-luna 3, Claude Sonnet 5.5 7; row 5 is a subset derived from row 3, not a separate run.

### S1b. November 2026 runs (version 0.1.5 frozen, plus third-party and void runs)

Sources: `evaluations/2026-11-final/results/held_out_runs.jsonl` (rows with run ids) and, for rows marked "author record", the author-held audit record of the revision (kept privately because it names private paths and raters); result files are in `evaluations/2026-11-final/results/` unless stated.

| When | Set | Code or tool | Purpose and status | Source |
|---|---|---|---|---|
| 2026-11-01 ~09:25 and ~09:41 | WCXB test (511) | ChromeRAG 0.1.4 (`ec56321`), 3 modes; Trafilatura version and metadata variants | Adoption-strategy work; **void**: ChromeRAG numbers never reported and no change derived from them; Trafilatura-only variants used for the version sensitivity in Table S3 | author record |
| 2026-11-01 11:04 | WCXB test (511) | rs-trafilatura 0.1.1, CI run 41339838506 (Linux) | one run, third-party tool only; outputs re-scored with our scorer (Table S3) | author record; scores in `revision_rows/p03_extra_rows.json` |
| 2026-11-01 | strict dev (1,238) | rs-trafilatura 0.1.1, CI run 41345382478 | development comparison (not held out) | author record |
| 2026-11-01 (commit 2263988) | CRAG split 0 (500) | ChromeRAG candidate code, gpt-5.6-luna | **void**: harness chunking bug (long single lines dropped); $0.7569; results deleted | author record |
| 2026-11-01 (commit 602590f) | CRAG split 0 (500) | ChromeRAG candidate code, gpt-5.6-luna | practice run, used to choose the default mode; $0.7602 | `answer_test_practice/crag_split0.json` |
| 2026-11-01 | new pages (307 fetched) | run aae56bd7; 7 tools listed, freeze-0.1.5 (rs-trafilatura not installed: no output on any page) | single extraction run of the frozen page list (tag pages-2026-11) | `new_pages/new_pages_extract.json` |
| 2026-11-01, between 19:49 and 21:27 -0800 (inferred: after commit ed5dc92 that added poc/final_wcxb.py, before commit 01c16f3 that added the result; the result file has no timestamp) | wcxb_test (511) | run 7e5fa6b6; ed5dc92 or later; src identical to freeze-0.1.5 (checked by the script) | planned one-run comparison on the WCXB test split (protocol-2026-11) | `wcxb_test/wcxb_test.json` |
| 2026-11-01, on or after commit ed5dc92 (19:49 -0800), before commit 01c16f3 (21:27 -0800) (inferred; the result file has no timestamp) | crag_split1 (500) | run 835b0782; ed5dc923fdb7aec8b73a4c2ce5c8eb9db694b43c (git_commit in the result file) | planned one-run answer test, CRAG split 1, seed 0 | `answer_test_locked_planned/crag_split1.json` |
| 2026-11-20T13:10:43-08:00 (extraction, 22.5 s) and 13:11:27 (scoring) | wcxb_test (511) | run 9d93c725; 99c6612 (harness poc/revision_rows.py; src identical to freeze-0.1.5) | P07 front matter: ChromeRAG raw and stripped, Trafilatura with_metadata True and False | `revision_rows/p07_front_matter.json` |
| 2026-11-20T13:11:11-08:00 (freeze-0.1.3 code extraction, 5.4 s) and 13:11:44 (scoring) | wcxb_test (511) | run 3fd7d39e; 99c6612; old code = git archive freeze-0.1.3 src with assets/lbc_stage1.npz replaced by the 0.1.5 model, no code edit | P03 extra rows: 372-page set, domains absent from original dev, page types, with-snippet rate, freeze-0.1.3 code with the 0.1.5 model; rs-trafilatura (CI run 41339838506) and BoilerPy3 (CI run 44817203676) saved outputs re-scored | `revision_rows/p03_extra_rows.json` |
| 2026-11-20T13:10:43-08:00 (same extraction pass as P07) and 13:11:46 (scoring) | wcxb_test (511) | run 466d060d; 99c6612 | P13 jusText 3.0.2 baseline, default English stoplist | `revision_rows/p13_justext.json` |
| extraction in CI run 44817203676 (ubuntu-24.04, Python 3.12); scored 2026-11-20T13:11:48-08:00 | wcxb_test (511) | run 53fb314b; 99c6612 for scoring; CI workflow on temporary branch ci/boilerpy3-wcxb | P13 BoilerPy3 1.0.7 DefaultExtractor and ArticleExtractor | `revision_rows/p13_boilerpy3.json` |
| 2026-11-20T13:12:06-08:00 to 13:12:58-08:00 | wcxb_test (511) | run be39e883; 99c6612 | speed, one process, warm (25 pages untimed), ChromeRAG balanced, Trafilatura, Readability, jusText | `revision_rows/speed.json` |
| 2026-11-20T14:12:54-08:00 | wcxb_test (511) | run 32e3fcd8; cf380e5; src identical to tag freeze-0.1.5 (checked by the script); Trafilatura 2.2.0, repo arguments (Markdown, tables, no comments, no links, no metadata) | author-added robustness row (ledger says "reviewer-requested" in error): Trafilatura favor_recall / favor_precision (favor_recall=True); scored once | `revision_rows/trafilatura_options.json` |
| 2026-11-20T14:12:54-08:00 | wcxb_test (511) | run 16e9c14a; cf380e5; src identical to tag freeze-0.1.5 (checked by the script); Trafilatura 2.2.0, repo arguments (Markdown, tables, no comments, no links, no metadata) | author-added robustness row (ledger says "reviewer-requested" in error): Trafilatura favor_recall / favor_precision (favor_precision=True); scored once | `revision_rows/trafilatura_options.json` |
| 2026-11-01 | new pages (296) | GPT page judge, gpt-5.6-luna | **crashed** on an API timeout at 630 of 643 jobs (author log; this run judged two baselines; MarkItDown was added before the rerun, which had 963 jobs, 888 pairs and 75 swapped re-judgments); $0.642; no result kept or seen | author record |
| 2026-11-01 | new pages (296) | GPT page judge, gpt-5.6-luna, rubric-2026-11 | complete run, 963 judgments (888 primary, 75 swapped); $1.2267 | `new_pages/new_pages_judge.json` |
| 2026-11-01 | CRAG splits 0 and 1 | regrade of saved answers under rubric v2 | post hoc; split 1 $0.2696, split 0 $0.2786 | `answer_test_regrade_posthoc/` |
| 2026-11-01 | first human-set draw (75 of the 296 new pages; never sent to raters; replaced 2026-11-02) | no separate judge run: GPT verdicts on these pages were part of the 296-page run above, whose totals had been seen | post hoc on the 75 drawn pages (ChromeRAG-baseline-tie): 34-32-9 vs Trafilatura, 47-25-3 vs Readability | `human_set_analysis/posthoc.json` (history) |
| 2026-11-02 (judge plan 4f5ce3a, 18:52) | approved-site human set before 5 length swaps (75) | GPT, Grok, Gemini judges | totals seen; then two tool-blind length rules swapped 5 pages (850cf98, 5ebf4fb); GPT 42-27-6 before and 43-27-5 after the swaps vs Trafilatura (Table S6) | `human_set_ai_judges/*.progress.jsonl`; `human_set_analysis/posthoc.json` |
| 2026-11-02 19:21 (commit 3b4f43d) | human set (75) | GPT, Grok, Gemini judges, 163 judgments each | 5 swapped-in pages judged; all verdicts frozen before any human rating was returned | `human_set_ai_judges/` |
| 2026-11-04 to 2026-11-19 | human set (75) | 5 raters, app 1.1.0 | analysis fixed before rating, commit 70b7d93 (Table S6) | `evaluations/2026-11-final/human_set_ratings/` (pseudonymized files and `label_key.json`) |
| 2026-11-20 | human set (75) | post hoc analyses, no new data | robustness, training-domain overlap, set history, coded error analysis (Table S6) | `human_set_analysis/` |
| 2026-11-20 | WCXB test (upstream copy) | hash check, CI run 44818754399 | local test split equals the upstream copy (1,022 files) | `revision_rows/gt_upstream_check.json` |

Two rows of `held_out_runs.jsonl` (the planned WCXB test run and CRAG split 1, both on 1 November) were missing and were reconstructed on 20 November from the result files and git history (field `added`). Of the 20 November WCXB test rows, the raw and stripped output, subsets, old code and BoilerPy3 were requested in review; jusText, the Trafilatura options and speed were added by the author. The `purpose` field of the two Trafilatura option rows says "reviewer-requested"; that label is wrong, and the rows were added by the author. Ledger rows are kept as written.

Code changed after a test-split result was seen (before the freeze): on 1 November rs-trafilatura was scored on the test split at 11:04; four ideas described for it were then implemented without reading its source and tested on the strict development pages only, and one passed (a richer collapse signal for the coverage retry, +0.00017 F1 on 5 development pages; commit `f1de490`, 16:57, public through `freeze-0.1.5`; credited in the acknowledgements). The test split was not used for that decision (author record). Other `src/` commits that day also followed the morning test-split runs and preceded the freeze: `6629eda` (09:34, rule groups and detectors dropped by the strict development rule), `af8ff55` (12:23, table rescue and model refit), `b1ba63e` (14:31) and `5a66bb5` (15:50, output and review fixes) and `602590f` (17:35, answer-test and output fixes). Their messages record development-page measurements only; no record links them to a test-split result, but the history alone cannot show that.

The BoilerPy3 ledger row keeps the `ground_truth_check` text written before the upstream digest was checked; the later check, in a separate CI run, matched (`ci/README.md`).

Not done: the planned continuity rejudge of the 328 v0.1.4 pages; rs-trafilatura on the 296 new pages and on the human set.

The protocol section "Sets scored exactly once" held for the new pages and CRAG split 1. The WCXB test split was scored once as planned on 1 November and re-scored on 20 November with the same frozen code for rows requested in review and rows added by the author; this is recorded as a dated amendment in `PROTOCOL.md` ("Re-scoring of the WCXB test split for review"). Ledger times are local time with UTC offset.

## Table S2. Judge and grader settings

| Use | Model id (as recorded) | Access route | Temperature | Other settings | Source |
|---|---|---|---|---|---|
| Page judge, 296 new pages | gpt-5.6-luna | OpenAI API, chat completions | not sent (API default) | JSON mode; reasoning effort low; A/B order seed 20261101; 24,000 characters per text; cost $1.2267 | `new_pages/new_pages_judge.json`, `poc/final_page_judge.py`, `poc/openai_client.py` |
| Page judge, human set | gpt-5.6-luna | OpenAI API, chat completions | not sent (API default) | as above; seed 20261101; the file records cost 0.0 because cost was not tracked (author record: $0.208; no public file) | `human_set_ai_judges/gpt.json` |
| Page judge, human set | grok-4.5 (medium reasoning), run through a third-party agent tool | third-party agent tool | unknown, not controllable | coding agent, settings not controllable | `human_set_ai_judges/grok.json` |
| Page judge, human set | gemini-4-argon-medium | third-party agent tool | unknown, not controllable | coding agent, settings not controllable | `human_set_ai_judges/gemini.json` |
| CRAG answers and grading | gpt-5.6-luna | OpenAI API, chat completions | 0 requested; dropped by the API (generate True, judge True) | question sample seed 0; top 5 BM25 chunks of 200 words; context cap 1,200 words | `answer_test_locked_planned/crag_split1.json`, `poc/crag_answer_eval.py` |
| v0.1.4 rounds (superseded) | Claude Sonnet 5.5; gpt-5.6-luna; Gemini 3.7 Flash | Claude sub-agents; OpenAI API; not recorded | not recorded | prompt hash 6f502417… | Table S1a |

All page judges use the same rubric (`RUBRIC.md`, tag `rubric-2026-11`), see tool outputs labeled A and B only, and re-judge each pair with A and B swapped with probability 0.1 (realized: 75 of 888 pairs on the 296 new pages; 13 of 150 per judge on the human set). Model ids are the ids requested (no returned model snapshot string was saved); for Grok and Gemini, as recorded in the third-party agent tool; "medium" (Grok's reasoning level, and part of the Gemini model id) was selected in that tool and could not be verified. Both ran as coding agents; the public files do not record what the agent tool could read besides the job file, so their blinding rests on the job file and cannot be shown. The access-route label in `human_set_ai_judges/grok.json` was reworded to a neutral label on 20 November (private history); no verdict changed. Outside judging, a Claude model (Claude Opus 5.5) was used throughout development, for the address and page safety reviews together with Grok, and for coding the error analysis; Grok wrote and reviewed code and reviewed the practice notes; Gemini reviewed code, the protocol and the CRAG harness; a coding model offered in a third-party coding-agent tool wrote part of the code; GPT judged repeatedly, and Gemini 3.7 Flash twice, during v0.1.4 development (Table S1a). No Claude model is used as a judge in this version.

## Table S3. WCXB test split: all rows

Sources: `revision_rows/p03_extra_rows.json` (subsets, baselines, old code), `revision_rows/p07_front_matter.json` (raw and stripped output), `revision_rows/p13_justext.json`, `revision_rows/p13_boilerpy3.json`. ChromeRAG rows remove one leading YAML front-matter block unless marked raw. Scorer: `poc.wcxb.word_f1` and `snippet_rate` (same tokenizer as WCXB `evaluate.py`; an empty snippet list scores 1.0; this holds for 5 pages in the without list and 6 in the with list, the same for every tool). Paired intervals resample 444 sites, 5,000 draws, seed 0.

**All 511 pages** (n = 511, sites = 444).

| Tool | P | R | F1 | Without | With | Pages F1 < 0.1 | Empty outputs |
|---|---|---|---|---|---|---|---|
| ChromeRAG 0.1.5 balanced | 0.884 | 0.918 | 0.8839 | 0.070 | 0.759 | 10 | 5 |
| ChromeRAG 0.1.5 coverage | 0.867 | 0.935 | 0.8821 | 0.083 | 0.781 | 10 | 5 |
| ChromeRAG 0.1.5 precision | 0.893 | 0.887 | 0.8715 | 0.060 | 0.725 | 11 | 5 |
| freeze-0.1.3 code + 0.1.5 model, balanced | 0.872 | 0.933 | 0.8854 | 0.092 | 0.794 | 7 | 4 |
| freeze-0.1.3 code + 0.1.5 model, coverage | 0.850 | 0.960 | 0.8847 | 0.109 | 0.828 | 7 | 4 |
| freeze-0.1.3 code + 0.1.5 model, precision | 0.890 | 0.890 | 0.8725 | 0.072 | 0.742 | 7 | 6 |
| Trafilatura 2.2.0 (no metadata) | 0.890 | 0.868 | 0.8596 | 0.083 | 0.720 | 16 | 3 |
| rs-trafilatura 0.1.1 | 0.894 | 0.926 | 0.8905 | 0.111 | 0.864 | 14 | 0 |
| Readability (readability-lxml 0.9) | 0.872 | 0.757 | 0.7625 | 0.089 | 0.552 | 52 | 0 |
| BoilerPy3 1.0.7 DefaultExtractor | 0.787 | 0.792 | 0.7531 | 0.150 | 0.695 | 35 | 11 |
| BoilerPy3 1.0.7 ArticleExtractor | 0.849 | 0.652 | 0.6865 | 0.099 | 0.545 | 42 | 14 |
| jusText 3.0.2 | 0.803 | 0.701 | 0.7129 | 0.058 | 0.593 | 53 | 48 |
| MarkItDown 0.1.7 | 0.410 | 0.989 | 0.5402 | 0.967 | 0.768 | 26 | 3 |

Paired differences: balanced minus trafilatura: F1 +0.0243 [+0.0075, +0.0422], without −0.0129 [−0.0298, +0.0051], with +0.0394 [+0.0082, +0.0711]; chromerag balanced minus old013 balanced: F1 −0.0015 [−0.0083, +0.0047], without −0.0219 [−0.0336, −0.0109], with −0.0350 [−0.0490, −0.0219]; old013 balanced minus trafilatura: F1 +0.0259 [+0.0088, +0.0437], without +0.0090 [−0.0106, +0.0290], with +0.0744 [+0.0422, +0.1062]; rs trafilatura minus chromerag balanced: F1 +0.0066 [−0.0134, +0.0251], without +0.0414 [+0.0251, +0.0586], with +0.1046 [+0.0751, +0.1339].

**372 pages not duplicated in dev/ (primary set of v0.1.4)** (n = 372, sites = 317).

| Tool | P | R | F1 | Without | With | Pages F1 < 0.1 | Empty outputs |
|---|---|---|---|---|---|---|---|
| ChromeRAG 0.1.5 balanced | 0.900 | 0.926 | 0.8989 | 0.065 | 0.779 | 6 | 4 |
| ChromeRAG 0.1.5 coverage | 0.882 | 0.943 | 0.8973 | 0.076 | 0.805 | 6 | 4 |
| ChromeRAG 0.1.5 precision | 0.910 | 0.895 | 0.8867 | 0.058 | 0.746 | 6 | 4 |
| freeze-0.1.3 code + 0.1.5 model, balanced | 0.884 | 0.937 | 0.8959 | 0.092 | 0.807 | 5 | 3 |
| freeze-0.1.3 code + 0.1.5 model, coverage | 0.864 | 0.963 | 0.8966 | 0.108 | 0.844 | 5 | 3 |
| freeze-0.1.3 code + 0.1.5 model, precision | 0.901 | 0.895 | 0.8810 | 0.079 | 0.757 | 4 | 5 |
| Trafilatura 2.2.0 (no metadata) | 0.903 | 0.869 | 0.8672 | 0.083 | 0.743 | 10 | 2 |
| rs-trafilatura 0.1.1 | 0.902 | 0.927 | 0.8967 | 0.108 | 0.887 | 12 | 0 |
| Readability (readability-lxml 0.9) | 0.887 | 0.773 | 0.7779 | 0.101 | 0.575 | 32 | 0 |
| BoilerPy3 1.0.7 DefaultExtractor | 0.805 | 0.780 | 0.7536 | 0.154 | 0.700 | 24 | 7 |
| BoilerPy3 1.0.7 ArticleExtractor | 0.867 | 0.640 | 0.6821 | 0.097 | 0.548 | 29 | 10 |
| jusText 3.0.2 | 0.820 | 0.691 | 0.7132 | 0.056 | 0.600 | 36 | 35 |
| MarkItDown 0.1.7 | 0.436 | 0.988 | 0.5677 | 0.969 | 0.782 | 12 | 2 |

Paired differences: balanced minus trafilatura: F1 +0.0318 [+0.0112, +0.0536], without −0.0181 [−0.0374, +0.0007], with +0.0366 [+0.0005, +0.0763].

**311 pages whose domain is absent from the original dev/ folder** (n = 311, sites = 287).

| Tool | P | R | F1 | Without | With | Pages F1 < 0.1 | Empty outputs |
|---|---|---|---|---|---|---|---|
| ChromeRAG 0.1.5 balanced | 0.902 | 0.925 | 0.9003 | 0.054 | 0.781 | 6 | 2 |
| ChromeRAG 0.1.5 coverage | 0.887 | 0.942 | 0.9013 | 0.065 | 0.804 | 6 | 2 |
| ChromeRAG 0.1.5 precision | 0.911 | 0.891 | 0.8854 | 0.049 | 0.744 | 6 | 2 |
| freeze-0.1.3 code + 0.1.5 model, balanced | 0.886 | 0.934 | 0.8961 | 0.078 | 0.808 | 5 | 1 |
| freeze-0.1.3 code + 0.1.5 model, coverage | 0.867 | 0.963 | 0.8996 | 0.093 | 0.846 | 5 | 1 |
| freeze-0.1.3 code + 0.1.5 model, precision | 0.901 | 0.889 | 0.8784 | 0.069 | 0.756 | 4 | 3 |
| Trafilatura 2.2.0 (no metadata) | 0.904 | 0.874 | 0.8705 | 0.079 | 0.750 | 8 | 1 |
| rs-trafilatura 0.1.1 | 0.906 | 0.928 | 0.9016 | 0.099 | 0.887 | 10 | 0 |
| Readability (readability-lxml 0.9) | 0.890 | 0.769 | 0.7754 | 0.095 | 0.568 | 27 | 0 |
| BoilerPy3 1.0.7 DefaultExtractor | 0.810 | 0.792 | 0.7645 | 0.139 | 0.707 | 21 | 5 |
| BoilerPy3 1.0.7 ArticleExtractor | 0.872 | 0.650 | 0.6936 | 0.081 | 0.552 | 24 | 8 |
| jusText 3.0.2 | 0.812 | 0.693 | 0.7145 | 0.048 | 0.598 | 33 | 32 |
| MarkItDown 0.1.7 | 0.439 | 0.989 | 0.5716 | 0.963 | 0.784 | 9 | 1 |

Paired differences: balanced minus trafilatura: F1 +0.0298 [+0.0110, +0.0496], without −0.0247 [−0.0460, −0.0056], with +0.0304 [−0.0016, +0.0631].

**Raw and stripped output (all 511 pages).** Source `p07_front_matter.json`.

| Output | P | R | F1 | Without | With |
|---|---|---|---|---|---|
| chromerag_balanced_raw | 0.830 | 0.917 | 0.8535 | 0.092 | 0.761 |
| chromerag_balanced | 0.884 | 0.918 | 0.8839 | 0.070 | 0.759 |
| chromerag_precision_raw | 0.839 | 0.888 | 0.8432 | 0.083 | 0.726 |
| chromerag_precision | 0.893 | 0.887 | 0.8715 | 0.060 | 0.725 |
| chromerag_coverage_raw | 0.815 | 0.933 | 0.8513 | 0.103 | 0.783 |
| chromerag_coverage | 0.867 | 0.935 | 0.8821 | 0.083 | 0.781 |
| trafilatura | 0.890 | 0.868 | 0.8596 | 0.083 | 0.720 |
| trafilatura_meta_raw | 0.824 | 0.881 | 0.8316 | 0.110 | 0.725 |
| trafilatura_meta_stripped | 0.890 | 0.868 | 0.8596 | 0.083 | 0.720 |

| Paired difference | F1 | Without | With |
|---|---|---|---|
| balanced_raw_minus_balanced_stripped | −0.0305 [−0.0401, −0.0226] | +0.0223 [+0.0146, +0.0313] | +0.0011 [+0.0000, +0.0029] |
| precision_raw_minus_precision_stripped | −0.0284 [−0.0379, −0.0206] | +0.0230 [+0.0152, +0.0322] | +0.0016 [+0.0000, +0.0036] |
| coverage_raw_minus_coverage_stripped | −0.0308 [−0.0402, −0.0231] | +0.0209 [+0.0132, +0.0297] | +0.0011 [+0.0000, +0.0029] |
| trafilatura_meta_raw_minus_trafilatura | −0.0280 [−0.0328, −0.0236] | +0.0271 [+0.0186, +0.0367] | +0.0046 [+0.0013, +0.0089] |
| trafilatura_meta_stripped_minus_trafilatura | +0.0000 [+0.0000, +0.0000] | +0.0000 [+0.0000, +0.0000] | +0.0000 [+0.0000, +0.0000] |
| balanced_stripped_minus_trafilatura (primary, both without metadata) | +0.0243 [+0.0075, +0.0422] | −0.0129 [−0.0298, +0.0051] | +0.0394 [+0.0082, +0.0711] |
| balanced_raw_minus_trafilatura_meta_raw (both with metadata) | +0.0219 [+0.0067, +0.0370] | −0.0176 [−0.0363, +0.0021] | +0.0360 [+0.0054, +0.0658] |
| balanced_raw_minus_trafilatura (as shipped by default) | −0.0061 [−0.0225, +0.0104] | +0.0095 [−0.0087, +0.0283] | +0.0406 [+0.0095, +0.0720] |

Front matter: ChromeRAG writes a block on all 511 pages (mean 42.5 words; keys {'title': 511, 'url': 510, 'description': 420, 'type': 39, 'lastUpdated': 14, 'author': 2}); Trafilatura with `with_metadata=True` writes one on 508 pages (mean 59.9 words; keys {'url': 508, 'hostname': 508, 'sitename': 508, 'title': 507, 'date': 479, 'description': 461, 'author': 256, 'tags': 91, 'categories': 66, 'license': 18}). Trafilatura's body text is identical with and without metadata on 511 pages. Default CLI and API output are the same (note in the file).

**Trafilatura recall and precision options** (added by the author; the run records label them reviewer-requested in error, see Table S1b; source `revision_rows/trafilatura_options.json`, harness `poc/trafilatura_options.py`). Trafilatura 2.2.0 with the same arguments as the default row (Markdown, tables, no comments, no links, no metadata) plus `favor_recall=True` or `favor_precision=True`; each run once on 511 pages; the default configuration was reproduced page by page in the same pass. These options had already been looked at on this split on 1 November with default (plain-text) arguments (baseline reconciliation note: F1 0.842 and 0.782; caveat in `revision_rows/trafilatura_options.md`), so the rows confirm rather than first measure them.

| Output | P | R | F1 | Without | With | Pages F1 < 0.1 | Empty outputs |
|---|---|---|---|---|---|---|---|
| ChromeRAG 0.1.5 balanced | 0.884 | 0.918 | 0.8839 | 0.070 | 0.759 | 10 | 5 |
| Trafilatura 2.2.0 default (reproduced) | 0.890 | 0.868 | 0.8596 | 0.083 | 0.720 | 16 | 3 |
| Trafilatura 2.2.0 favor_recall | 0.893 | 0.852 | 0.8452 | 0.087 | 0.706 | 16 | 3 |
| Trafilatura 2.2.0 favor_precision | 0.895 | 0.767 | 0.7871 | 0.056 | 0.621 | 37 | 14 |

| Paired difference | F1 | Without | With |
|---|---|---|---|
| balanced minus trafilatura favor recall | +0.0387 [+0.0170, +0.0616] | −0.0170 [−0.0354, +0.0017] | +0.0537 [+0.0177, +0.0924] |
| trafilatura favor recall minus default trafilatura 2.2.0 | −0.0144 [−0.0296, +0.0002] | +0.0041 [−0.0053, +0.0138] | −0.0143 [−0.0325, +0.0035] |
| balanced minus trafilatura favor precision | +0.0968 [+0.0694, +0.1252] | +0.0137 [−0.0010, +0.0299] | +0.1383 [+0.1015, +0.1768] |
| trafilatura favor precision minus default trafilatura 2.2.0 | −0.0725 [−0.0943, −0.0511] | −0.0266 [−0.0390, −0.0154] | −0.0989 [−0.1219, −0.0775] |

**Trafilatura versions** (saved files of the 1 November baseline reconciliation, not re-run; values as recorded in `trafilatura_options.json`, key `version_table`; no snippet rates in those files). F1 is the word-F1 mean over the 511-page test split (1,495 dev pages for dev rows) from the saved summaries, same tokenizer as poc.wcxb.word_f1; the version files hold no snippet rates. Config columns: repo = Markdown, tables, no comments, no links; default = library default; favor_* in the version files use default arguments (plain text), not the repo arguments used for the new rows. Not used: wcxb_test_trafilatura-2.2.0_chromerag-0.1.4.json (void run). The 1,495 dev pages are the whole WCXB `dev/` folder; 22 have fewer than 30 reference words, and the strict split keeps 1,238 of the remaining 1,473.

| Trafilatura | Test F1, repo arguments | Test F1, library default | favor_recall (default arguments) | favor_precision (default arguments) |
|---|---|---|---|---|
| 1.12.2 | 0.8292 | 0.8192 | 0.8358 | 0.7785 |
| 2.0.0 | 0.8292 | 0.8193 | 0.8358 | 0.7785 |
| 2.1.0 | 0.8327 | 0.8226 | 0.8390 | 0.7801 |
| 2.3.1 | 0.8625 | 0.8614 | 0.8462 | 0.7903 |

Version 2.2.0, used throughout, is in the table above (F1 0.8596). The highest test F1 of any listed version and configuration is 0.8625, below ChromeRAG balanced (0.8839). The package pins `trafilatura>=1.12.0` only for the optional `[baselines]` extra; all main-text Trafilatura numbers use 2.2.0.

**Old-code control** (all 511 pages; 0.1.5 minus the freeze-0.1.3 code with the 0.1.5 model): F1 −0.0015 [−0.0083, +0.0047], without-rate −0.0219 [−0.0336, −0.0109], with-rate −0.0350 [−0.0490, −0.0219]. The rules added while the split was consulted leave F1 unchanged and lower both snippet rates; the without-rate is the figure most exposed to that use.

**Published values** (WCXB paper, test split, configurations of the benchmark authors): rs-trafilatura 0.903, Trafilatura 0.841, Readability 0.736. The benchmark paper states that rs-trafilatura was developed by its lead author and tested against the development set. BoilerPy3 provenance: CI run 44817203676 (ubuntu-24.04, Python 3.12) on WCXB upstream commit `c039d5e…`, artifact sha256 in `p13_boilerpy3.json`; `gt_upstream_check.json` shows that copy equals ours. rs-trafilatura provenance: CI run 41339838506, outputs re-scored here.

## Table S4. F1 by page type

**WCXB test split** (source `p03_extra_rows.json`, key `iii_per_type`; intervals resample sites within the type).

| Type (n, sites) | chromerag_balanced | chromerag_coverage | chromerag_precision | trafilatura | rs_trafilatura | readability | boilerpy3_default | justext | markitdown | old013_balanced | Balanced − Trafilatura |
|---|---|---|---|---|---|---|---|---|---|---|---|
| article (257, 229) | 0.940 | 0.935 | 0.939 | 0.952 | 0.951 | 0.926 | 0.870 | 0.826 | 0.643 | 0.941 | −0.012 [−0.024, −0.001] |
| collection (34, 33) | 0.704 | 0.718 | 0.655 | 0.626 | 0.775 | 0.450 | 0.460 | 0.379 | 0.284 | 0.729 | +0.078 [−0.002, +0.152] |
| documentation (42, 30) | 0.954 | 0.957 | 0.945 | 0.934 | 0.973 | 0.872 | 0.828 | 0.653 | 0.615 | 0.956 | +0.020 [−0.022, +0.070] |
| forum (51, 38) | 0.866 | 0.841 | 0.849 | 0.717 | 0.836 | 0.616 | 0.543 | 0.752 | 0.443 | 0.865 | +0.149 [+0.092, +0.230] |
| listing (40, 39) | 0.732 | 0.755 | 0.689 | 0.722 | 0.748 | 0.439 | 0.443 | 0.382 | 0.386 | 0.735 | +0.010 [−0.113, +0.140] |
| product (28, 24) | 0.805 | 0.800 | 0.801 | 0.724 | 0.777 | 0.527 | 0.742 | 0.629 | 0.335 | 0.813 | +0.081 [+0.000, +0.181] |
| service (59, 58) | 0.849 | 0.854 | 0.826 | 0.817 | 0.832 | 0.612 | 0.755 | 0.685 | 0.471 | 0.838 | +0.031 [−0.008, +0.071] |

**WCXB test forums by platform** (post hoc; source `posthoc_round2/round2_posthoc.json`, key `wcxb_forum_platforms`; script `poc/rev1_round2_posthoc.py`; same paired site bootstrap). Rule: host on the Stack Exchange network -> stackexchange; else first matching HTML marker in PLATFORM_RULES (poc/rev1_round2_posthoc.py); else not_identified. Seen = the rule finds the platform on at least one strict training page labelled forum. "Seen" means the platform is detected on at least one of the 100 strict training forum pages (detected platforms on 78 of them: xenforo 27, discourse 21, invision 8, phpbb 7, stackexchange 6, nodebb 3, vbulletin 2, smf 1, flarum 1, mybb 1, vanilla 1; the rest match no listed platform). A first version of the rule checked product names that can occur in page text before asset-path markers; it classed the one Vanilla training page (which names other forum products in its text) as Flarum and one XenForo training page as vBulletin. Under that version 15 test forum pages were 'not seen', balanced - Trafilatura +0.111 [-0.014, +0.246]. The rule was reordered after seeing this, so the split is sensitive to the rule; both versions are reported.

| Forum pages | Pages | Sites | ChromeRAG F1 | Trafilatura F1 | Balanced − Trafilatura |
|---|---|---|---|---|---|
| All | 51 | 38 | 0.866 | 0.717 | +0.149 [+0.092, +0.230] |
| Platform seen in training | 34 | 25 | 0.843 | 0.686 | +0.157 [+0.099, +0.249] |
| Seen, without Stack Exchange | 23 | 23 | 0.835 | 0.625 | +0.210 [+0.143, +0.277] |
| Platform not seen | 13 | 9 | 0.895 | 0.836 | +0.059 [−0.071, +0.187] |
| Not identified | 4 | 4 | 0.959 | 0.584 | +0.376 [+0.013, +0.738] |
| Not seen or not identified | 17 | 13 | 0.910 | 0.777 | +0.133 [−0.002, +0.298] |

| Platform (test) | Pages | Sites | Balanced − Trafilatura |
|---|---|---|---|
| xenforo | 14 | 14 | +0.183 [+0.105, +0.265] |
| stackexchange | 11 | 2 | +0.046 [−0.018, +0.052] |
| bbpress | 6 | 3 | +0.049 [+0.006, +0.093] |
| not_identified | 4 | 4 | +0.376 [+0.013, +0.738] |
| vbulletin | 3 | 3 | +0.234 [+0.153, +0.342] |
| phpbb | 2 | 2 | +0.108 [+0.070, +0.147] |
| vanilla | 2 | 2 | +0.451 [+0.396, +0.506] |
| jforum | 2 | 1 | +0.358 [+0.358, +0.358] |
| wpforo | 2 | 2 | −0.054 [−0.062, −0.046] |
| discourse | 1 | 1 | +0.000 [+0.000, +0.000] |
| ubbthreads | 1 | 1 | +0.291 [+0.291, +0.291] |
| gainsight_insided | 1 | 1 | −0.387 [−0.387, −0.387] |
| invision | 1 | 1 | +0.443 [+0.443, +0.443] |
| khoros | 1 | 1 | −0.039 [−0.039, −0.039] |

The split holds out domains, not forum software: two thirds of the test forum pages run a platform also present in training. "Not seen" refers to training forum pages only: 6 of the 13 such pages are bbPress, whose markup occurs on 10 training pages of other types (`results/posthoc_round2/round2_posthoc.json`, key `strict_training_pages_any_type_by_platform`).

**Strict development cross-validation** (1,238 pages, five folds grouped by registrable domain, models never see their test fold; source `evaluations/2026-10-v0.1.3/strict_dev_cv.json`, means computed from the per-page rows; `chromerag` is balanced).

| Type (n) | chromerag | chromerag_coverage | chromerag_precision | trafilatura | readability | markitdown | balanced without |
|---|---|---|---|---|---|---|---|
| all (1238) | 0.859 | 0.858 | 0.851 | 0.828 | 0.709 | 0.526 | 0.055 |
| article (668) | 0.944 | 0.939 | 0.945 | 0.936 | 0.891 | 0.628 | 0.050 |
| collection (77) | 0.643 | 0.657 | 0.625 | 0.581 | 0.390 | 0.240 | 0.089 |
| documentation (74) | 0.928 | 0.927 | 0.911 | 0.907 | 0.825 | 0.667 | 0.034 |
| forum (100) | 0.801 | 0.789 | 0.798 | 0.687 | 0.437 | 0.454 | 0.087 |
| listing (85) | 0.707 | 0.721 | 0.682 | 0.606 | 0.345 | 0.355 | 0.049 |
| product (81) | 0.609 | 0.598 | 0.607 | 0.619 | 0.397 | 0.197 | 0.066 |
| service (153) | 0.819 | 0.829 | 0.785 | 0.771 | 0.566 | 0.473 | 0.046 |

rs-trafilatura was also run once on these development pages (CI run 41345382478). Its outputs and per-page scores are not in the repository, so its development scores are not reported here and are not used for any claim.

## Table S5. Component ablation on strict development pages

Source: `evaluations/2026-10-v0.1.3/strict_ablation_cv.json` (commit `4bebd13`, inside `freeze-0.1.5`; harness `poc/ablation_cv.py`). Protocol: 1,238 pages (poc/wcxb_strict_train_ids.json), the five cross-validation fold models, priority balanced. Balanced mode; each row changes one switch against the full pipeline (F1 0.8593, without 0.0552, median 47.5 ms on that machine). Intervals: site bootstrap, 5,000 draws, seed 0.

Component rows reuse the five fold models, which were trained on blocks left after all cleaning stages; a row that switches a stage off is not retrained, so it measures that stage's contribution to the shipped model. Decision rule, fixed before the runs in the author's dated plan (not in the repository; available to the editor on request): drop a component if removing it does not lower mean F1 (ΔF1 ≥ 0) and does not raise the without-snippet rate; ship the stacked model only if its F1 interval is above zero with acceptable size and speed. Decisions were taken on the runs before the final rebuild (the documentation-framework rules on commit `7ca7e9e`); on this frozen run the consent rules (`no_yaml_consent`), the Trafilatura-derived author and footer groups (`no_tf_author`, `no_tf_footer`), structure rules and table rescue also meet the drop rule (structure and table rescue are the disclosed exceptions), and several other switches change both measures by under 0.0005; all remain as switches. Rows are not additive: a row that removes a stage runs the model on blocks unlike those it was trained on. Dropped: Trafilatura-derived rule groups `tf.related`, `tf.share`, `tf.newsletter`, `tf.ads`, `tf.tools`; the 16 documentation-framework YAML rules; the pager and related-post detectors (switched off by default, so their rows below are zero). Kept as disclosed exceptions: structure rules (removal lowers recall by more than 0.05 on 10 pages and raises it on none) and table rescue (keeps plan tables such as the pricing example). Not shipped: the stacked second model (F1 interval above zero, but 10.3 times the file size, one of about 30 comparisons, and many per-page recall swings).

| Configuration | F1 | ΔF1 | Without | ΔWithout | Median ms |
|---|---|---|---|---|---|
| no_lbc | 0.8296 | −0.0296 [−0.0363, −0.0234] | 0.0762 | +0.0210 [+0.0145, +0.0280] | 41.7 |
| no_lbc_structure | 0.8595 | +0.0003 [−0.0006, +0.0010] | 0.0483 | −0.0069 [−0.0097, −0.0043] | 47.5 |
| no_chrome_prune | 0.8530 | −0.0062 [−0.0105, −0.0019] | 0.1022 | +0.0470 [+0.0400, +0.0546] | 48.2 |
| no_generic_chrome | 0.8584 | −0.0009 [−0.0021, +0.0004] | 0.0617 | +0.0065 [+0.0039, +0.0096] | 36.9 |
| no_rules | 0.8594 | +0.0002 [−0.0003, +0.0009] | 0.0554 | +0.0002 [0.0000, +0.0006] | 45.6 |
| no_trafilatura_ideas | 0.8609 | +0.0017 [−0.0022, +0.0059] | 0.0715 | +0.0164 [+0.0118, +0.0213] | 48.7 |
| no_table_rescue | 0.8593 | +0.0001 [−0.0002, +0.0005] | 0.0552 | 0.0000 [0.0000, 0.0000] | 46.7 |
| filter_only | 0.8404 | −0.0188 [−0.0252, −0.0125] | 0.2043 | +0.1491 [+0.1359, +0.1628] | 37.8 |
| rules_only | 0.8377 | −0.0215 [−0.0281, −0.0153] | 0.0890 | +0.0339 [+0.0267, +0.0413] | 39.7 |
| no_yaml_consent | 0.8596 | +0.0003 [0.0000, +0.0010] | 0.0552 | 0.0000 [0.0000, 0.0000] | 46.5 |
| no_yaml_share_related | 0.8591 | −0.0001 [−0.0003, 0.0000] | 0.0554 | +0.0002 [0.0000, +0.0006] | 47.3 |
| no_yaml_trafilatura_inspired | 0.8592 | 0.0000 [−0.0001, +0.0001] | 0.0552 | 0.0000 [0.0000, 0.0000] | 46.2 |
| chrome_no_toc | 0.8591 | −0.0002 [−0.0006, +0.0001] | 0.0556 | +0.0004 [0.0000, +0.0012] | 46.1 |
| chrome_no_pager | 0.8593 | 0.0000 [0.0000, 0.0000] | 0.0552 | 0.0000 [0.0000, 0.0000] | 46.7 |
| chrome_no_comments | 0.8592 | 0.0000 [−0.0001, 0.0000] | 0.0554 | +0.0002 [0.0000, +0.0006] | 45.5 |
| chrome_no_related | 0.8593 | 0.0000 [0.0000, 0.0000] | 0.0552 | 0.0000 [0.0000, 0.0000] | 47.1 |
| chrome_no_cta | 0.8591 | −0.0002 [−0.0007, +0.0003] | 0.0555 | +0.0003 [−0.0005, +0.0012] | 46.1 |
| chrome_no_share | 0.8593 | 0.0000 [0.0000, 0.0000] | 0.0554 | +0.0002 [0.0000, +0.0006] | 46.2 |
| chrome_no_newsletter | 0.8591 | −0.0002 [−0.0004, 0.0000] | 0.0564 | +0.0013 [+0.0002, +0.0027] | 45.4 |
| chrome_no_author | 0.8593 | 0.0000 [−0.0001, +0.0001] | 0.0556 | +0.0005 [0.0000, +0.0013] | 45.4 |
| chrome_no_tail | 0.8587 | −0.0006 [−0.0016, +0.0005] | 0.0584 | +0.0032 [+0.0015, +0.0054] | 45.4 |
| chrome_no_attr_junk | 0.8593 | 0.0000 [0.0000, +0.0001] | 0.0554 | +0.0002 [0.0000, +0.0006] | 46.4 |
| no_tf_comments | 0.8592 | 0.0000 [0.0000, 0.0000] | 0.0552 | 0.0000 [0.0000, 0.0000] | 47.1 |
| no_tf_sidebar | 0.8592 | 0.0000 [0.0000, 0.0000] | 0.0552 | 0.0000 [0.0000, 0.0000] | 46.8 |
| no_tf_author | 0.8593 | 0.0000 [0.0000, +0.0001] | 0.0552 | 0.0000 [0.0000, 0.0000] | 47.0 |
| no_tf_pagination | 0.8592 | 0.0000 [0.0000, 0.0000] | 0.0552 | 0.0000 [0.0000, 0.0000] | 47.0 |
| no_tf_skip | 0.8592 | 0.0000 [0.0000, 0.0000] | 0.0552 | 0.0000 [0.0000, 0.0000] | 47.3 |
| no_tf_footer | 0.8593 | 0.0000 [0.0000, 0.0000] | 0.0552 | 0.0000 [0.0000, 0.0000] | 46.9 |
| no_tf_tags | 0.8592 | 0.0000 [−0.0001, 0.0000] | 0.0552 | 0.0000 [0.0000, 0.0000] | 46.5 |
| stack_stage2 | 0.8630 | +0.0037 [+0.0009, +0.0065] | 0.0515 | −0.0036 [−0.0067, −0.0007] | 49.1 (1,565,271 bytes) |

Key: `no_lbc` learned filter off (original density scoring runs instead); `rules_only` filter and density scoring off; `filter_only` YAML rules, generic detectors, chrome pruning and Trafilatura-style density passes off; `no_trafilatura_ideas` the Trafilatura-style density passes (`trafilatura_ideas.py`) off; `no_yaml_*` one YAML file off; `chrome_no_*` one generic detector off; `no_tf_*` one Trafilatura-derived YAML rule group off; `stack_stage2` a second-stage model added. Per-type mean ΔF1 for every configuration: key `mean_delta_f1_by_type_sorted` in the same file.

## Table S5b. Feature-group ablation of the learned block filter on strict development pages

Source: `evaluations/2026-11-final/results/revision_rows/feature_group_ablation.json` (script `poc/feature_group_ablation.py`). Added in review; development pages only, no test page used. Same protocol as Table S5: the 1,238 strict pages, five folds grouped by registrable domain, the shipped hyperparameters (300 trees, depth 6), balanced threshold, site bootstrap with 5,000 draws, seed 0. Each row retrains the fold models with the named feature group removed or with only the named groups kept; the rest of the pipeline is unchanged. The full row reproduces Table S5 on every page. `shallow_only` keeps the block's own shallow text statistics and the length and link density of the previous and next block, an approximation of the feature set of Kohlschütter et al. [3] (no wrapped-line text density; neighbours add only length and link density), here trained on the same pages as ChromeRAG. The shipped tree settings (300 trees, depth 6) date from the first learned model of 1 October and were not re-tuned for the strict split.

Groups (features): `shallow_text` 18; `neighbour_shallow` 4; `position` 6; `dom_context` 46; `class_id_hash` 192; `heading_context` 195; `lexical_cues` 68; `page_relations` 6.

| Mode | Row | F1 | ΔF1 | Without | ΔWithout | Article / forum F1 |
|---|---|---|---|---|---|---|
| pipeline | full | 0.8593 | – | 0.0552 | – | 0.944 / 0.801 |
| pipeline | minus_shallow_text | 0.8609 | +0.0016 [−0.0005, +0.0039] | 0.0572 | +0.0020 [−0.0011, +0.0053] | 0.945 / 0.803 |
| pipeline | minus_neighbour_shallow | 0.8590 | −0.0002 [−0.0020, +0.0017] | 0.0573 | +0.0022 [−0.0004, +0.0049] | 0.944 / 0.800 |
| pipeline | minus_position | 0.8570 | −0.0022 [−0.0047, +0.0002] | 0.0590 | +0.0039 [+0.0004, +0.0074] | 0.942 / 0.796 |
| pipeline | minus_dom_context | 0.8517 | −0.0076 [−0.0116, −0.0038] | 0.0657 | +0.0105 [+0.0060, +0.0151] | 0.938 / 0.798 |
| pipeline | minus_class_id_hash | 0.8574 | −0.0019 [−0.0044, +0.0006] | 0.0555 | +0.0004 [−0.0023, +0.0031] | 0.944 / 0.786 |
| pipeline | minus_heading_context | 0.8598 | +0.0005 [−0.0017, +0.0027] | 0.0544 | −0.0008 [−0.0035, +0.0020] | 0.943 / 0.798 |
| pipeline | minus_lexical_cues | 0.8589 | −0.0004 [−0.0021, +0.0016] | 0.0567 | +0.0015 [−0.0011, +0.0043] | 0.944 / 0.800 |
| pipeline | minus_page_relations | 0.8597 | +0.0004 [−0.0013, +0.0024] | 0.0577 | +0.0025 [0.0000, +0.0051] | 0.943 / 0.798 |
| pipeline | shallow_only | 0.8435 | −0.0157 [−0.0206, −0.0113] | 0.0873 | +0.0321 [+0.0259, +0.0384] | 0.926 / 0.781 |
| pipeline | shallow_plus_position | 0.8448 | −0.0145 [−0.0193, −0.0097] | 0.0736 | +0.0184 [+0.0129, +0.0243] | 0.930 / 0.780 |
| pipeline | shallow_plus_context | 0.8573 | −0.0020 [−0.0047, +0.0009] | 0.0596 | +0.0045 [+0.0012, +0.0077] | 0.943 / 0.793 |
| filter only | full | 0.8404 | – | 0.2043 | – | 0.922 / 0.749 |
| filter only | minus_shallow_text | 0.8432 | +0.0028 [−0.0003, +0.0058] | 0.2056 | +0.0013 [−0.0041, +0.0068] | 0.923 / 0.753 |
| filter only | minus_neighbour_shallow | 0.8409 | +0.0005 [−0.0014, +0.0024] | 0.2080 | +0.0038 [−0.0009, +0.0084] | 0.921 / 0.752 |
| filter only | minus_position | 0.8423 | +0.0019 [−0.0013, +0.0052] | 0.2049 | +0.0006 [−0.0058, +0.0070] | 0.924 / 0.744 |
| filter only | minus_dom_context | 0.8152 | −0.0253 [−0.0304, −0.0202] | 0.2719 | +0.0677 [+0.0574, +0.0785] | 0.897 / 0.738 |
| filter only | minus_class_id_hash | 0.8421 | +0.0017 [−0.0022, +0.0061] | 0.2056 | +0.0014 [−0.0050, +0.0078] | 0.924 / 0.736 |
| filter only | minus_heading_context | 0.8401 | −0.0004 [−0.0030, +0.0022] | 0.2085 | +0.0042 [−0.0012, +0.0099] | 0.920 / 0.749 |
| filter only | minus_lexical_cues | 0.8403 | −0.0002 [−0.0022, +0.0019] | 0.2138 | +0.0095 [+0.0042, +0.0150] | 0.922 / 0.744 |
| filter only | minus_page_relations | 0.8417 | +0.0012 [−0.0009, +0.0033] | 0.2030 | −0.0013 [−0.0065, +0.0037] | 0.923 / 0.748 |
| filter only | shallow_only | 0.7996 | −0.0409 [−0.0479, −0.0340] | 0.3898 | +0.1855 [+0.1704, +0.2008] | 0.878 / 0.712 |
| filter only | shallow_plus_position | 0.7920 | −0.0485 [−0.0545, −0.0425] | 0.3404 | +0.1362 [+0.1230, +0.1497] | 0.876 / 0.719 |
| filter only | shallow_plus_context | 0.8413 | +0.0009 [−0.0033, +0.0058] | 0.2104 | +0.0061 [−0.0004, +0.0128] | 0.922 / 0.739 |


## Table S6. Human rating study: full analysis fixed in advance

Source: analysis of the five returned rating files as fixed in advance (plan in `PROTOCOL.md`, "Analysis plan for the human rating set", committed in `70b7d93` on 2 November, with the per-page majority verdict from the section "Human rating set" and its 2 November amendments; all before any rating; not registered with a third party). Unit: page (75 main pages from 48 sites; practice items and repeats excluded from votes). Outcome per page: plurality of rater verdicts; equal top counts give a tie. Pairwise verdict from the set of outputs ticked as best (one tool in the set and the other not = win; otherwise tie). Intervals: site bootstrap, 10,000 draws, seed 20261120. Net = (wins − losses) / pages, from the view of the tool named before "vs". Pseudonymized rating files and the label key are in `evaluations/2026-11-final/human_set_ratings/`; the analysis is `poc/human_set_analysis.py`; rater-level rows are shown without identifiers.

**ChromeRAG vs Trafilatura.** Krippendorff alpha (nominal): all raters 0.42; without the flagged rater 0.36.

| Subset | Pages | Sites | W/L/T | Net [95% CI] |
|---|---|---|---|---|
| All pages (primary outcome) | 75 | 48 | 32/15/28 | +0.23 [+0.01, +0.42] |
| Forums only | 10 | 6 | 8/0/2 | +0.80 [+0.60, +1.00] |
| Without forums | 65 | 43 | 24/15/26 | +0.14 [−0.09, +0.35] |
| Group: ai | 11 | 7 | 5/2/4 | +0.27 [−0.20, +0.73] |
| Group: forum | 10 | 6 | 8/0/2 | +0.80 [+0.60, +1.00] |
| Group: reference | 9 | 6 | 3/3/3 | +0.00 [−0.60, +0.71] |
| Group: technology | 12 | 7 | 6/2/4 | +0.33 [−0.27, +0.75] |
| Sensitivity, without the flagged rater: all | 75 | 48 | 20/6/49 | +0.19 [+0.06, +0.31] |
| Sensitivity, without the flagged rater: without forums | 65 | 43 | 15/6/44 | +0.14 [+0.00, +0.28] |

Per-rater net (no identifiers, sorted): +0.31, +0.29, +0.28, +0.19, +0.14. Page groups with fewer than 8 pages (not analyzed separately): automotive 2, data_center 4, energy 3, finance 6, logistics 2, manufacturing 3, medical 5, retail 5, telecom 3.

**ChromeRAG vs Readability.** Krippendorff alpha (nominal): all raters 0.41; without the flagged rater 0.32.

| Subset | Pages | Sites | W/L/T | Net [95% CI] |
|---|---|---|---|---|
| All pages | 75 | 48 | 38/13/24 | +0.33 [+0.13, +0.52] |
| Forums only | 10 | 6 | 7/1/2 | +0.60 [+0.00, +1.00] |
| Without forums | 65 | 43 | 31/12/22 | +0.29 [+0.08, +0.49] |
| Group: ai | 11 | 7 | 6/1/4 | +0.45 [+0.00, +0.83] |
| Group: forum | 10 | 6 | 7/1/2 | +0.60 [+0.00, +1.00] |
| Group: reference | 9 | 6 | 4/2/3 | +0.22 [−0.30, +0.88] |
| Group: technology | 12 | 7 | 7/1/4 | +0.50 [+0.00, +0.86] |
| Sensitivity, without the flagged rater: all | 75 | 48 | 27/6/42 | +0.28 [+0.14, +0.41] |
| Sensitivity, without the flagged rater: without forums | 65 | 43 | 23/5/37 | +0.28 [+0.13, +0.42] |

Per-rater net (no identifiers, sorted): +0.45, +0.39, +0.35, +0.31, +0.14. Page groups with fewer than 8 pages (not analyzed separately): automotive 2, data_center 4, energy 3, finance 6, logistics 2, manufacturing 3, medical 5, retail 5, telecom 3.

**Trafilatura vs Readability.** Krippendorff alpha (nominal): all raters 0.39; without the flagged rater 0.29.

| Subset | Pages | Sites | W/L/T | Net [95% CI] |
|---|---|---|---|---|
| All pages | 75 | 48 | 22/14/39 | +0.11 [−0.06, +0.27] |
| Forums only | 10 | 6 | 1/3/6 | −0.20 [−0.70, +0.20] |
| Without forums | 65 | 43 | 21/11/33 | +0.15 [−0.02, +0.32] |
| Group: ai | 11 | 7 | 3/1/7 | +0.18 [−0.20, +0.50] |
| Group: forum | 10 | 6 | 1/3/6 | −0.20 [−0.70, +0.20] |
| Group: reference | 9 | 6 | 3/1/5 | +0.22 [+0.00, +0.57] |
| Group: technology | 12 | 7 | 3/1/8 | +0.17 [−0.22, +0.55] |
| Sensitivity, without the flagged rater: all | 75 | 48 | 16/7/52 | +0.12 [+0.01, +0.24] |
| Sensitivity, without the flagged rater: without forums | 65 | 43 | 15/6/44 | +0.14 [+0.01, +0.26] |

Per-rater net (no identifiers, sorted): +0.16, +0.14, +0.11, +0.03, +0.00. Page groups with fewer than 8 pages (not analyzed separately): automotive 2, data_center 4, energy 3, finance 6, logistics 2, manufacturing 3, medical 5, retail 5, telecom 3.

Page groups in the set: technology 12, reference 9, finance 6, energy 3, medical 5, ai 11, data_center 4, forum 10, telecom 3, automotive 2, manufacturing 3, retail 5, logistics 2. Groups were defined by the author-approved site list before rating.

**Mean 1–5 scores** (all ratings of main pages):

| Tool | Ratings | Content kept | Noise left in (5 = none) |
|---|---|---|---|
| chromerag | 231 | 4.23 [4.03, 4.40] | 4.03 [3.88, 4.19] |
| trafilatura | 231 | 3.83 [3.63, 4.03] | 3.94 [3.79, 4.08] |
| readability | 231 | 3.32 [3.00, 3.63] | 3.87 [3.66, 4.07] |

**Score differences** (secondary outcome fixed in advance; ChromeRAG minus baseline, per-page mean over raters, site bootstrap; script `poc/human_set_score_diff.py`):

    trafilatura content all +0.38 [+0.05, +0.67] n=75 sites=48 | no forums +0.25 [-0.10, +0.58] n=65 sites=43
    trafilatura chrome all +0.10 [-0.07, +0.28] n=75 sites=48 | no forums +0.17 [-0.02, +0.35] n=65 sites=43
    readability content all +0.90 [+0.55, +1.24] n=75 sites=48 | no forums +0.93 [+0.52, +1.31] n=65 sites=43
    readability chrome all +0.17 [-0.08, +0.42] n=75 sites=48 | no forums +0.18 [-0.11, +0.48] n=65 sites=43

**Rating-quality checks** (the protocol's careless-rating rules, fixed before rating; no identifiers): median seconds per rated item 99, 87, 80, 71, 42; no rater under 30 s; no rater gave one screen position on 90% or more of items. Repeat check (applies with 4 or more repeat pairs): one full-set rater agreed on 3 of 4; the other agreed on 1 of 5 and was flagged (`inconsistent_repeats`); all four changed repeats of the flagged rater moved one step for ChromeRAG against Trafilatura (win to tie, tie to win, tie to loss, loss to tie), none reversed (author record, checked by hand); against Readability one repeat reversed. Part raters had 1 or 2 repeats (2 of 2, 1 of 1, 0 of 2 agreed). The flagged rater stays in the primary result.

**Anchor pages** (5 pages assigned to every rater, ChromeRAG vs Trafilatura): mean pairwise agreement 0.78, Krippendorff alpha 0.65. Coverage: 67 pages with 3 ratings, 4 with 5 (anchors), 1 with 4, 3 with 2 (after 5 skipped ratings).

**Human majority vs AI judges** (same 75 pages, same outputs; AI verdicts saved before any rating was read; agreement counts ties as their own outcome):

| Pair | Judge | Agreement | Cohen's kappa | Disagreements | AI judge net |
|---|---|---|---|---|---|
| chromerag_vs_trafilatura | gpt | 0.59 [0.46, 0.71] | 0.37 [0.21, 0.53] | 31 (23 human ties) | +0.21 [−0.03, +0.44] |
| chromerag_vs_trafilatura | grok | 0.61 [0.49, 0.73] | 0.41 [0.25, 0.57] | 29 (22 human ties) | +0.25 [+0.03, +0.48] |
| chromerag_vs_trafilatura | gemini | 0.65 [0.53, 0.77] | 0.47 [0.31, 0.63] | 26 (22 human ties) | +0.25 [+0.01, +0.48] |
| chromerag_vs_readability | gpt | 0.56 [0.45, 0.67] | 0.27 [0.13, 0.40] | 33 (24 human ties) | +0.35 [+0.12, +0.56] |
| chromerag_vs_readability | grok | 0.56 [0.43, 0.68] | 0.28 [0.12, 0.44] | 33 (21 human ties) | +0.32 [+0.08, +0.54] |
| chromerag_vs_readability | gemini | 0.60 [0.47, 0.72] | 0.34 [0.17, 0.50] | 30 (22 human ties) | +0.33 [+0.10, +0.55] |

**AI judges by subset** (descriptive, not in the plan; same bootstrap; script `poc/human_set_ai_by_forum.py`):

| Baseline | Judge | All 75 | Forums (10) | Without forums (65) |
|---|---|---|---|---|
| trafilatura | gpt | +0.21 [−0.03, +0.44] | +0.60 [+0.00, +1.00] | +0.15 [−0.09, +0.39] |
| trafilatura | grok | +0.25 [+0.03, +0.48] | +1.00 [+1.00, +1.00] | +0.14 [−0.09, +0.37] |
| trafilatura | gemini | +0.25 [+0.01, +0.48] | +1.00 [+1.00, +1.00] | +0.14 [−0.11, +0.39] |
| readability | gpt | +0.35 [+0.12, +0.56] | +0.10 [−0.56, +0.73] | +0.38 [+0.14, +0.61] |
| readability | grok | +0.32 [+0.08, +0.54] | +0.40 [−0.14, +0.83] | +0.31 [+0.05, +0.55] |
| readability | gemini | +0.33 [+0.10, +0.55] | +0.60 [+0.00, +1.00] | +0.29 [+0.05, +0.53] |

**Length effect on the human set** (method of Table S8; page bootstrap; "similar" = length ratio within 1.1):

| Baseline | Judge | Similar length: pages, net | ChromeRAG longer | Baseline longer | Win probability at equal length |
|---|---|---|---|---|---|
| trafilatura | gpt | 25: +0.00 [−0.36, +0.36] | 32: +0.75 | 18: −0.44 | 0.59 [0.42, 0.72] |
| trafilatura | grok | 25: +0.12 [−0.24, +0.44] | 32: +0.69 | 18: −0.33 | 0.63 [0.46, 0.75] |
| trafilatura | gemini | 25: +0.12 [−0.24, +0.44] | 32: +0.75 | 18: −0.44 | 0.62 [0.46, 0.74] |
| trafilatura | human_majority_exploratory | 25: +0.12 [−0.16, +0.40] | 32: +0.69 | 18: −0.44 | 0.70 [0.48, 0.93] |
| readability | gpt | 27: +0.33 [−0.04, +0.70] | 38: +0.60 | 10: −0.60 | 0.56 [0.42, 0.71] |
| readability | grok | 27: +0.26 [−0.07, +0.59] | 38: +0.58 | 10: −0.50 | 0.55 [0.40, 0.68] |
| readability | gemini | 27: +0.30 [−0.07, +0.63] | 38: +0.58 | 10: −0.50 | 0.57 [0.45, 0.69] |
| readability | human_majority_exploratory | 27: +0.30 [+0.00, +0.59] | 38: +0.50 | 10: −0.20 | 0.64 [0.47, 0.81] |

The exploratory intervals in this table come from the public script, which orders pages by item id; two interval cells differ in the second decimal from an earlier draft of this supplement, and no point value changed.

Ratings used per rater and AI-tool use: all five raters stated that they used no AI tool while rating.

### S6, post hoc (computed after all ratings and after the planned analysis; not in the plan)

Source `results/human_set_analysis/posthoc.json` and `posthoc.md` (script `poc/human_set_posthoc.py`; same site bootstrap, 10,000 draws, seed 20261120). Nothing here changes a rating, page, setting or tool; the planned result above stays the primary result. Leave-one-rater-out numbers use a fixed random order of the rater codes (not the published codes).

| Pair | Check | Result |
|---|---|---|
| vs Trafilatura | Ties excluded | 32 of 47 decided pages; exact two-sided sign test p = 0.0186 |
| vs Trafilatura | Pages with opposite verdicts | 7 of 75; all raters agree 34, only win and tie 22, only loss and tie 12; pooled single ratings W/L/T 99/44/88 |
| vs Trafilatura | Leave one rater out: drop rater 1 | +0.19 [−0.01, +0.38] (28/14/33) |
| vs Trafilatura | Leave one rater out: drop rater 2 | +0.20 [+0.01, +0.37] (26/11/38) |
| vs Trafilatura | Leave one rater out: drop rater 3 | +0.24 [+0.04, +0.42] (30/12/33) |
| vs Trafilatura | Leave one rater out: drop rater 4 | +0.16 [−0.04, +0.35] (26/14/35) |
| vs Trafilatura | Leave one rater out: drop rater 5 | +0.19 [+0.06, +0.31] (20/6/49) |
| vs Trafilatura | Forums weighted at 10% (WCXB test share) | +0.20 [−0.00, +0.40] (forum net +0.80 on 10 pages, other net +0.14 on 65; 12 draws without a forum page dropped) |
| vs Readability | Ties excluded | 38 of 51 decided pages; exact two-sided sign test p = 0.0006 |
| vs Readability | Pages with opposite verdicts | 8 of 75; all raters agree 36, only win and tie 19, only loss and tie 12; pooled single ratings W/L/T 118/42/71 |
| vs Readability | Leave one rater out: drop rater 1 | +0.35 [+0.17, +0.51] (33/7/35) |
| vs Readability | Leave one rater out: drop rater 2 | +0.35 [+0.15, +0.53] (36/10/29) |
| vs Readability | Leave one rater out: drop rater 3 | +0.31 [+0.11, +0.50] (36/13/26) |
| vs Readability | Leave one rater out: drop rater 4 | +0.28 [+0.10, +0.45] (32/11/32) |
| vs Readability | Leave one rater out: drop rater 5 | +0.28 [+0.14, +0.41] (27/6/42) |
| vs Readability | Forums weighted at 10% (WCXB test share) | +0.32 [+0.12, +0.51] (forum net +0.60 on 10 pages, other net +0.29 on 65; 12 draws without a forum page dropped) |

**Training-domain overlap.** 20 of 75 rated pages share a registrable domain with at least one strict training page (13 of 48 sites; 2 of 10 forum pages); exact URL matches with training pages: 0 (Public Suffix List 2026-10-31_14-17-28_UTC; 1,238 strict training pages on 1,065 registrable domains). The 296 new pages were sampled with the domain exclusions of every earlier set (Table S8).

| Pair | Without overlap | With overlap | Without overlap and without forums |
|---|---|---|---|
| chromerag vs trafilatura | 55 pages, 35 sites: +0.20 [−0.05, +0.43] (23/12/20) | 20 pages, 13 sites: +0.30 [−0.11, +0.67] (9/3/8) | 47 pages, 31 sites: +0.11 [−0.17, +0.36] (17/12/18) |
| chromerag vs readability | 55 pages, 35 sites: +0.33 [+0.08, +0.55] (26/8/21) | 20 pages, 13 sites: +0.35 [−0.05, +0.70] (12/5/3) | 47 pages, 31 sites: +0.30 [+0.05, +0.53] (21/7/19) |

**Development domains (round 2, post hoc).** Counting the domains of all WCXB pages used in development (strict training and test split), 34 of 75 rated pages (20 of 48 sites) are on such domains: 14 on test split domain, 41 on no wcxb domain, 20 on strict training domain; test-only domains: amazon.com, docker.com, github.com, microsoft.com, mit.edu, nih.gov, oracle.com; 5 of 10 forum pages. Source `posthoc_round2/round2_posthoc.json`, key `human_set_development_domains`.

| Pair | All | On development domains | Clean (no WCXB domain) | Clean, without forums | Clean forums |
|---|---|---|---|---|---|
| chromerag vs trafilatura | 75 pages, 48 sites: +0.23 [+0.01, +0.42] (32/15/28) | 34 pages, 20 sites: +0.24 [−0.13, +0.54] (15/7/12) | 41 pages, 28 sites: +0.22 [−0.05, +0.46] (17/8/16) | 36 pages, 25 sites: +0.14 [−0.15, +0.41] (13/8/15) | 5 pages, 3 sites: +0.80 [+0.50, +1.00] (4/0/1) |
| chromerag vs readability | 75 pages, 48 sites: +0.33 [+0.13, +0.52] (38/13/24) | 34 pages, 20 sites: +0.38 [+0.06, +0.66] (19/6/9) | 41 pages, 28 sites: +0.29 [+0.03, +0.54] (19/7/15) | 36 pages, 25 sites: +0.28 [+0.00, +0.54] (16/6/14) | 5 pages, 3 sites: +0.40 [−0.50, +1.00] (3/1/1) |


**Agreement among AI judges and earlier evaluation domains (final review, post hoc).** Source `human_set_analysis/review_posthoc.json` (script `poc/human_set_posthoc_review.py`; public files only). AI judge verdicts are the primary (not swapped) verdicts on the 75 pages.

| Pair | All three judges same | Fleiss' kappa | Pairwise Cohen's kappa |
|---|---|---|---|
| chromerag vs trafilatura | 64 of 75 | 0.82 | gpt-grok 0.78, gpt-gemini 0.78, grok-gemini 0.90 |
| chromerag vs readability | 61 of 75 | 0.73 | gpt-grok 0.66, gpt-gemini 0.77, grok-gemini 0.75 |

Earlier ChromeRAG evaluation sets (`evaluations/2026-10-v0.1.3/evaluation_domains.csv`: Landing dev companies (53), Landing heldout companies (47), Documentation/pricing/article corpus, Fresh companies (51)) share registrable domains, but no URL, with some rated pages not on WCXB domains; pages on those domains among the 41 without a WCXB domain: Landing dev companies (53) 4, Landing heldout companies (47) 4, Documentation/pricing/article corpus 7, Fresh companies (51) 0 (a domain can be in two sets).

| Pair | All | No WCXB domain | No WCXB or earlier-set domain |
|---|---|---|---|
| chromerag vs trafilatura | 75 pages, 48 sites: +0.23 [+0.01, +0.42] (32/15/28) | 41 pages, 28 sites: +0.22 [−0.05, +0.46] (17/8/16) | 28 pages, 21 sites: +0.29 [−0.04, +0.55] (12/4/12) |
| chromerag vs readability | 75 pages, 48 sites: +0.33 [+0.13, +0.52] (38/13/24) | 41 pages, 28 sites: +0.29 [+0.02, +0.54] (19/7/15) | 28 pages, 21 sites: +0.39 [+0.11, +0.66] (15/4/9) |

Intervals in this table come from `poc/human_set_posthoc_review.py`, whose resampling differs from the round-2 script, so a bound can differ by 0.01 from the development-domain table above (ChromeRAG against Readability, no WCXB domain: [+0.02, +0.54] here, [+0.03, +0.54] above).

**Without the five pages swapped in after the AI totals were seen** (post hoc; same source): chromerag vs trafilatura: 70 pages, 44 sites, +0.24 [+0.02, +0.45] (30/13/27); swapped-in pages W/L/T 2/2/1; chromerag vs readability: 70 pages, 44 sites, +0.31 [+0.09, +0.51] (35/13/22); swapped-in pages W/L/T 3/0/2.

**History of the set.** The set fixed in the protocol on 2026-11-01 was a draw of 75 pages from the 296 new pages (seed 20261101; article 31, collection 1, forum 10, landing 2, listing 6, product 2, service 23); the builder skipped 35 candidates with short tool output. GPT verdicts on all 296 pages, and their totals, already existed. On 2026-11-02, before any rater received a page, the set was replaced for rater safety (a site reached in the first collection was flagged as unsafe, and saved pages could still load live images) by pages from an author-approved site list, with forums fixed at 10 of 75. After the three AI judges had judged that set and their totals had been seen, two tool-blind rules (all three outputs under 80 words; page text over 8,000 words) swapped 5 pages one for one; the verdicts on the 5 pages swapped out remain in the `*.progress.jsonl` files. Full dated record in `posthoc.md`.

| Judge | Pair | Set before swaps (W-L-T) | 5 swapped out | 5 swapped in | Final set |
|---|---|---|---|---|---|
| gpt | chromerag vs trafilatura | 42-27-6 | 2-2-1 | 3-2-0 | 43-27-5 |
| gpt | chromerag vs readability | 48-24-3 | 2-1-2 | 4-1-0 | 50-24-1 |
| grok | chromerag vs trafilatura | 42-24-9 | 3-1-1 | 4-1-0 | 43-24-8 |
| grok | chromerag vs readability | 47-24-4 | 3-1-1 | 4-1-0 | 48-24-3 |
| gemini | chromerag vs trafilatura | 43-24-8 | 2-1-2 | 3-2-0 | 44-25-6 |
| gemini | chromerag vs readability | 47-25-3 | 2-2-1 | 4-1-0 | 49-24-2 |
| gpt (first draw, post hoc) | chromerag vs trafilatura | 34-32-9 |  |  |  |
| gpt (first draw, post hoc) | chromerag vs readability | 47-25-3 |  |  |  |

**Coded error analysis** (post hoc, descriptive; one coder, a Claude model (Claude Opus 5.5), after unblinding, with a scheme committed before coding; no second coder, so the counts describe these pages and are not a test). Pages: every page the human majority gave to Trafilatura or to Readability, and 15 randomly drawn pages ChromeRAG won against Trafilatura. Primary code per page, from `results/human_set_analysis/error_analysis.md` (codes, rules and per-page notes there):

| Primary code | ChromeRAG lost to Trafilatura (15) | ChromeRAG lost to Readability (13) | Contrast: Trafilatura lost to ChromeRAG (15) |
|---|---|---|---|
| MISSING_BLOCK | 6 | 2 | 7 |
| MISSING_STRUCTURE | 3 | 0 | 3 |
| TRUNCATED_END | 0 | 0 | 2 |
| KEPT_CHROME | 0 | 2 | 0 |
| KEPT_COMMENTS | 0 | 0 | 0 |
| METADATA | 0 | 5 | 3 |
| NEAR_IDENTICAL | 4 | 4 | 0 |
| OTHER | 2 | 0 | 0 |

Against Trafilatura the clearest losses are ChromeRAG keeping too little on short hub, landing and product pages; against Readability most losses are a missing title line or near-identical outputs; where ChromeRAG won, Trafilatura had dropped main content (on forums, the question or the replies after the first post). No page was coded as kept comments.

## Table S7. CRAG answer test

Pipeline (`poc/crag_answer_eval.py`): for each question, each tool extracts the up to five pages supplied with it, and a separate BM25 index is built per question from those pages only; outputs (ChromeRAG front matter removed) are cut into 200-word chunks; BM25 retrieves the top 5 chunks (context cap 1,200 words); gpt-5.6-luna answers from that context only ("I don't know" if insufficient); the same model labels the answer accurate, missing or incorrect against the gold answer. Score = accurate − incorrect. Paired intervals: question bootstrap, 2,000 draws (per-question labels were not kept, so intervals cannot be recomputed from public files; point values can). Question filter (same for both splits; `filter_web_static`, metadata only, fixed before scoring): records with a non-empty `popularity` field are excluded (the author's plan treated them as knowledge-graph template questions and kept the web questions; this reading was not checked against the CRAG documentation), then false-premise, fast-changing and real-time questions and questions answered "invalid question" (split 1: 1,335 loaded, 582 with `popularity`, 115 false-premise, 81 fast or real-time, 0 invalid; 557 kept). No site model was passed; `enable_stce: true` in the run files has no effect without one.

**Split 1 (locked, run once on frozen code; planned result).** Source `answer_test_locked_planned/crag_split1.json`; model gpt-5.6-luna; spend $0.754706; commit `ed5dc92`; question filter counts {'split0_loaded': 1335, 'kept': 557, 'excluded_nonempty_popularity': 582, 'excluded_fast_or_realtime': 81, 'excluded_false_premise': 115} (the key `split0_loaded` is a fixed label in the harness; here it counts split-1 records).

| Tool | Accurate | Missing | Incorrect | Score | Indexed BM25 tokens per page | Empty pages |
|---|---|---|---|---|---|---|
| markitdown | 0.402 | 0.456 | 0.142 | 0.260 | 6,948 | 135 |
| trafilatura | 0.456 | 0.386 | 0.158 | 0.298 | 2,335 | 139 |
| chromerag_precision | 0.456 | 0.408 | 0.136 | 0.320 | 1,813 | 138 |
| chromerag_balanced | 0.454 | 0.398 | 0.148 | 0.306 | 1,948 | 138 |
| chromerag_coverage | 0.446 | 0.402 | 0.152 | 0.294 | 2,096 | 138 |

Paired differences: markitdown - trafilatura −0.038 [−0.090, +0.012]; chromerag_precision - trafilatura +0.022 [−0.026, +0.068]; chromerag_balanced - trafilatura +0.008 [−0.040, +0.054]; chromerag_coverage - trafilatura −0.004 [−0.054, +0.042]; chromerag_coverage - chromerag_balanced −0.012 [−0.040, +0.016].

**Split 1, post hoc regrade under rubric v2 (stricter; same saved answers).** Source `answer_test_regrade_posthoc/crag_split1_rubric.json`; model gpt-5.6-luna; spend $0.269647.

| Tool | Accurate | Missing | Incorrect | Score | Indexed BM25 tokens per page | Empty pages |
|---|---|---|---|---|---|---|
| markitdown | 0.386 | 0.448 | 0.166 | 0.220 | 6,948 | 135 |
| trafilatura | 0.436 | 0.382 | 0.182 | 0.254 | 2,335 | 139 |
| chromerag_precision | 0.432 | 0.402 | 0.166 | 0.266 | 1,813 | 138 |
| chromerag_balanced | 0.436 | 0.396 | 0.168 | 0.268 | 1,948 | 138 |
| chromerag_coverage | 0.426 | 0.392 | 0.182 | 0.244 | 2,096 | 138 |

Label changes from the original grader: markitdown: {'accurate->incorrect': 9, 'missing->incorrect': 4, 'incorrect->accurate': 1}; trafilatura: {'accurate->incorrect': 11, 'missing->incorrect': 2, 'incorrect->accurate': 1}; chromerag_precision: {'accurate->incorrect': 13, 'missing->incorrect': 3, 'incorrect->accurate': 1}; chromerag_balanced: {'accurate->incorrect': 10, 'missing->incorrect': 1, 'incorrect->accurate': 1}; chromerag_coverage: {'accurate->incorrect': 10, 'missing->incorrect': 5}. Regrade interval for balanced − Trafilatura on split 1: +0.014 [−0.038, +0.064] (author record; no public file, not recomputable).

**Split 0 (practice; consulted during development and used to choose the default mode).** Source `answer_test_practice/crag_split0.json`; model gpt-5.6-luna; spend $0.76021; commit `602590f`; question filter counts {'split0_loaded': 1371, 'kept': 578, 'excluded_fast_or_realtime': 79, 'excluded_nonempty_popularity': 609, 'excluded_false_premise': 105}.

| Tool | Accurate | Missing | Incorrect | Score | Indexed BM25 tokens per page | Empty pages |
|---|---|---|---|---|---|---|
| markitdown | 0.446 | 0.380 | 0.174 | 0.272 | 6,973 | 157 |
| trafilatura | 0.458 | 0.358 | 0.184 | 0.274 | 2,222 | 157 |
| chromerag_precision | 0.478 | 0.378 | 0.144 | 0.334 | 1,678 | 154 |
| chromerag_balanced | 0.478 | 0.374 | 0.148 | 0.330 | 1,807 | 154 |
| chromerag_coverage | 0.456 | 0.394 | 0.150 | 0.306 | 1,942 | 154 |

Paired differences: markitdown - trafilatura −0.002 [−0.056, +0.054]; chromerag_precision - trafilatura +0.060 [+0.008, +0.110]; chromerag_balanced - trafilatura +0.056 [+0.006, +0.106]; chromerag_coverage - trafilatura +0.032 [−0.018, +0.080]; chromerag_coverage - chromerag_balanced −0.024 [−0.054, +0.006].

**Split 0, post hoc regrade under rubric v2.** Source `answer_test_regrade_posthoc/crag_split0_rubric.json`; model gpt-5.6-luna; spend $0.27863.

| Tool | Accurate | Missing | Incorrect | Score | Indexed BM25 tokens per page | Empty pages |
|---|---|---|---|---|---|---|
| markitdown | 0.428 | 0.368 | 0.204 | 0.224 | 6,973 | 157 |
| trafilatura | 0.434 | 0.350 | 0.216 | 0.218 | 2,222 | 157 |
| chromerag_precision | 0.458 | 0.372 | 0.170 | 0.288 | 1,678 | 154 |
| chromerag_balanced | 0.458 | 0.368 | 0.174 | 0.284 | 1,807 | 154 |
| chromerag_coverage | 0.442 | 0.388 | 0.170 | 0.272 | 1,942 | 154 |

Label changes from the original grader: markitdown: {'missing->incorrect': 5, 'accurate->incorrect': 11, 'incorrect->accurate': 1, 'missing->accurate': 1}; trafilatura: {'accurate->incorrect': 14, 'missing->incorrect': 3, 'missing->accurate': 1, 'incorrect->accurate': 1}; chromerag_precision: {'accurate->incorrect': 10, 'missing->incorrect': 3}; chromerag_balanced: {'accurate->incorrect': 10, 'missing->incorrect': 3}; chromerag_coverage: {'accurate->incorrect': 9, 'incorrect->accurate': 2, 'missing->incorrect': 3}.

Planned retrieval measure on split 1 (share of the 175 questions with a short gold answer whose answer appears in the top 5 chunks, key `gold_in_top5_short`): ChromeRAG balanced 0.543, Trafilatura 0.549, no difference. Words per page: indexed 1,948 against 2,335 (17% fewer), extracted 2,061 against 2,419 (15% fewer).

Void run: an earlier split-0 run (commit `2263988`, $0.7569) had a chunking bug (long single lines kept whole and dropped by the context cap); it was voided and rerun. Planned but not run: Readability and the share of retrieved chrome. `RUBRIC.md` was written after the split 1 run had been seen (`PROTOCOL.md`), so the regrade is post hoc. A blind re-grade of 30 answers, made during the pre-freeze cross-checks, agreed with the grader on 25 (author record; who re-graded is not recorded; no public file). Grader agreement with 101 fixture cases: 96.0% on labels (`PROTOCOL.md`).

## Table S8. GPT page judging on 296 new pages

Pages: 307 fetched once from a frozen list sampled from the Tranco top 200,000 domains with domain exclusions of every earlier set (`PROTOCOL.md`, `seed_page_list.json`); 11 removed by a mechanical filter (8 non-English, 2 JSON bodies, 1 duplicate URL; `page_filter.json`), 296 judged. Disclosed: one Danish page and four non-content pages (template, login, CSS, empty) remain in the set. Judge: gpt-5.6-luna, rubric `RUBRIC.md` (Table S2). Primary verdict is the judge's own choice; the fixed-order verdict is a sensitivity row computed from the same scores (content score, then chrome score). Source `new_pages/new_pages_judge.json`; length analysis `new_pages/length_analysis_posthoc.json` (post hoc). The raw HTML of these pages was not retained: URLs (`seed_page_list.json`), HTML and output hashes and lengths (`new_pages/new_pages_extract.json`) and all judgments are published, but the pages cannot be re-extracted, and a new fetch would return different pages.

| Baseline | Judge verdict W/L/T | Unclipped pairs W/L/T | Fixed-order W/L/T | Net, judge verdict | Similar length: W/L/T, net | ChromeRAG longer: net | Baseline longer: net | Win probability at equal length |
|---|---|---|---|---|---|---|---|---|
| trafilatura | 158/114/24 | 157/110/23 | 74/74/148 | +0.149 [+0.044, +0.253] | 49/40/20, +0.083 [−0.083, +0.257] | +0.421 | −0.242 | 0.577 [0.513, 0.641] |
| readability | 182/97/17 | 181/94/15 | 123/53/120 | +0.287 [+0.179, +0.395] | 47/42/13, +0.049 [−0.137, +0.235] | +0.575 | −0.353 | 0.523 [0.449, 0.601] |
| markitdown | 143/151/2 | 105/109/2 | 131/154/11 | −0.027 [−0.139, +0.081] | 0/0/1, +0.000 [+0.000, +0.000] | n/a | −0.027 | 0.683 [0.587, 0.780] |

Longer output wins 177/272 = 65% of decided ChromeRAG–Trafilatura pairs and 196/279 = 70% of ChromeRAG–Readability pairs, whichever tool is longer (audit recomputation from the stored judgments). Position check: 65 of 75 swapped pairs gave the same verdict. MarkItDown output is always longer, so length cannot be separated for it. Reading: against Trafilatura the AI-judge preference is not robust (fixed-order 74–74); it is weak evidence and not used for claims beyond that.

## Table S9. Rater instructions (summary)

| Item | What raters were told or shown |
|---|---|
| Task | Imagine a search assistant that can only read the extracted text; which labeled output (A, B, C) would give right answers most reliably to questions the page should answer? Same task text as the AI judges. |
| Content and noise | Content: what the page exists to give (main text, facts, prices, steps, tables; on forums the question and answers). Noise: menus, footers, cookie and sign-up notices, share buttons, ads, links or teasers for other pages. No fixed trade-off; length alone never decides. |
| Scores | Tick every output that is equally best, or "all about the same", or "none are good"; score each output 1–5 for content kept and noise left in, with anchor descriptions behind a Guide button; optional note; skip allowed. |
| Practice | 5 practice items before the main set, each followed by a short note on what a careful rater would notice; not analyzed. |
| Blinding | Outputs labeled A, B, C in random order; tool names, page addresses and word counts hidden; repeats unmarked; saved offline copies with links, images and remote styles removed; app connects to no website. |
| Aids | Difference highlighting (on by default; can be switched off): blue text is only in that output, yellow text is in that output and one other; colors mark differences only, not which text is content. |
| Rules | Rate alone; do not use AI tools to decide scores; do not look pages up online; do not read project results before finishing; do not discuss items until all have submitted. |
| Consent and data | Each rating package contained a study note, to be read first, that explained the task and withdrawal and stated that ratings would be published under a neutral code. The note asked raters to confirm by email before starting; instead, each rater's confirmation that they agreed to take part and to be named in the acknowledgments was recorded after that rater had finished rating, so consent was not recorded in writing before rating. No rater withdrew. All five stated, by email or text message, that they used no AI tool while rating. Raters were recruited from the author's professional network and were unpaid volunteers (author record). Raters were asked about their background and experience; the answers (missing for two raters) are kept private. The practice notes were written by the author, who knew which tool produced each practice output. A self-chosen rater name was replaced by a neutral code before publication; published files hold no start or end times. |
| Sources | `evaluators/HANDOUT.md`, `evaluators/ABOUT_THIS_STUDY.txt`, app `evaluators/static/index.html` (version 1.1.0), `PROTOCOL.md` amendments of 2 and 3 November. |

