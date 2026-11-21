"""Generate evaluations/2026-11-final/SUPPLEMENT.md (Tables S1-S9) from result files. Run from the repository root.

Inputs besides the committed result files: the output of the human rating analysis, which runs from the public
rating files and label key in evaluations/2026-11-final/human_set_ratings/:

  PYTHONPATH=src:. python -m poc.human_set_analysis --out H/
  PYTHONPATH=src:. python -m poc.human_set_ai_by_forum --out H/ai_by_forum.json
  PYTHONPATH=src:. python -m poc.human_set_score_diff > H/score_diff_output.txt
  python poc/gen_supplement.py H/results.json H/ai_by_forum.json H/score_diff_output.txt [OUT.md]

Post hoc files read directly: results/human_set_analysis/posthoc.json and error_analysis.md,
results/revision_rows/trafilatura_options.json, results/posthoc_round2/round2_posthoc.json.

The text is kept as it was when the supplement was generated for the revision; values are read from the files.
"""
# ruff: noqa: E401, E701, E702, E731, E741, F541, I001
import csv, json, sys, collections
R = 'evaluations/2026-11-final/results/'
O = 'evaluations/2026-10-v0.1.3/'
H = json.load(open(sys.argv[1])); AIF = json.load(open(sys.argv[2])); SD = open(sys.argv[3]).read().strip().splitlines()
P2 = json.load(open(R + 'posthoc_round2/round2_posthoc.json'))
OUT = sys.argv[4] if len(sys.argv) > 4 else 'evaluations/2026-11-final/SUPPLEMENT.md'
L = []
w = L.append
def sg(x, d=3): return (f"{x:+.{d}f}").replace('-', '−')
def f(x, d=3): return (f"{x:.{d}f}").replace('-', '−')
def ci(c, d=3): return f"[{sg(c[0], d)}, {sg(c[1], d)}]"
def tbl(header, rows):
    w('| ' + ' | '.join(header) + ' |'); w('|' + '---|' * len(header))
    for r in rows: w('| ' + ' | '.join(str(x) for x in r) + ' |')
    w('')

w('# Supplementary material: ChromeRAG 0.1.5 (SoftwareX revision 1, SOFTX-D-26-01378)')
w('')
w('Tables S1–S9 support the revised manuscript. Values are read by script (`poc/gen_supplement.py`) from the file named in each table '
  'note. Values marked "author record" come from the author\'s dated audit record and have no public file. Intervals are 95% percentile bootstrap intervals; "site" means registrable domain '
  '(Public Suffix List, `poc/psl.py`). Lower without-snippet ("without") rates are better; higher with-snippet rates are better. '
  'Code under test is tag `freeze-0.1.5` (commit `04cbb05`; model sha256 `2e2fecb9…c265c8e`, 152,432 bytes) unless a row says otherwise. '
  'Commits cited here are public through the tags `freeze-0.1.5`, `protocol-2026-11`, `protocol-2026-11a`, `pages-2026-11`, '
  '`rubric-2026-11`, `human-set-plan-2026-11` and `rater-kit-2026-11` and the release `v0.1.5`, except commit `3b4f43d` (AI verdicts '
  'on the human set, 2 November), the six protocol amendments made before rating (2 November: `841867c`, `f7f99f4`, `f00d5d5` careless-rating rule, '
  '`c93d0e4`, `1a6c1e6`; 3 November: `6da13d2` difference highlighting), the ablation harness commit `54477c5` and the 20 November harness commits `99c6612` and `cf380e5` '
  'recorded in result files; these belong to the author\'s private development history and are available to the editor on request. '
  'The amended protocol text itself is public in `PROTOCOL.md`, and the rating-kit side of these amendments (layout, three parts with '
  'shared anchor pages, task explanation, difference highlighting) is public through `rater-kit-2026-11` (commit `69981e8`, app 1.1.0 as sent to raters).')
w('')

# ---------------- S1
w('## Table S1. Held-out ledger')
w('')
w('### S1a. Runs on held-out or later-held-out sets during v0.1.3 and v0.1.4 development (October 2026)')
w('')
w('Source: `evaluations/2026-10-v0.1.3/HELD_OUT_LEDGER.csv` (53 rows, all shown), with output hashes per round in '
  '`held_out_round_hashes.json`. "uncommitted tree" means the code was a working tree that was not kept; the nearest '
  'commit is a lower bound. Prompt hash `6f502417…` is the v0.1.4 judge prompt (`poc/claude_judge_build.py`). '
  'Temperatures of these rounds were not recorded. Claude rounds ran through sub-agents (no fixed API configuration). '
  'Rows with result "deleted" are batches whose files were deleted; their summary values were recovered from git history.')
w('')
rows = list(csv.DictReader(open(O + 'HELD_OUT_LEDGER.csv')))
tbl(['#', 'Time (Pacific)', 'Set', 'Pages', 'Code', 'Judge', 'Route', 'Prompt', 'Net', 'Result file', 'Note'],
    [[i + 1, r['run_time'], r['set'], r['n_pages'].replace(';', '; '), r['tool_version_or_commit'], r['judge_model'],
      r['access_route'], (r['prompt_hash'][:8] + '…') if len(r['prompt_hash']) > 20 else r['prompt_hash'],
      r['net_overall'], r['result_file'], r['notes'].replace('|', '/')] for i, r in enumerate(rows)])
rh = json.load(open(O + 'held_out_round_hashes.json'))
w('Between the 328-page rounds, ChromeRAG output changed on most pages: see `held_out_round_hashes.json` '
  '(per-round output hashes; caveat recorded there: ' + rh['caveat_uncommitted_window'] + ')')
w('')
LC = P2['ledger_counts']
w(f"**Counts after the freeze-0.1.3 run (row {LC['freeze_run_row']})** (post hoc count from the ledger; `posthoc_round2/round2_posthoc.json`, key `ledger_counts`): "
  f"{LC['full_511_page_f1_scorings_after_freeze_run']['count']} full scorings of the 511 test pages (rows {', '.join(map(str, LC['full_511_page_f1_scorings_after_freeze_run']['rows']))}); "
  f"{LC['subset_f1_rescorings_after_freeze_run']['count']} subset re-scorings (rows {', '.join(map(str, LC['subset_f1_rescorings_after_freeze_run']['rows']))}; {LC['subset_f1_rescorings_after_freeze_run']['note']}); "
  f"{LC['ai_judge_runs_on_test_pages_only']['count']} AI-judge runs on test pages only (rows {', '.join(map(str, LC['ai_judge_runs_on_test_pages_only']['rows']))}) and "
  f"{LC['ai_judge_runs_on_mixed_sets_including_test_pages']['count']} on mixed sets that include test pages (rows {', '.join(map(str, LC['ai_judge_runs_on_mixed_sets_including_test_pages']['rows']))}), "
  "by judge " + ', '.join(f'{k} {v}' for k, v in LC['ai_judge_runs_including_test_pages_by_judge'].items()) + f"; row {', '.join(map(str, LC['derived_subsets_not_separate_runs']))} is a subset derived from row 3, not a separate run.")
w('')
w('### S1b. November 2026 runs (version 0.1.5 frozen, plus third-party and void runs)')
w('')
w('Sources: `evaluations/2026-11-final/results/held_out_runs.jsonl` (rows with run ids) and, for rows marked "author record", '
  'the author-held audit record of the revision (kept privately because it names private paths and raters); '
  'result files are in `evaluations/2026-11-final/results/` unless stated.')
w('')
jl = [json.loads(x) for x in open(R + 'held_out_runs.jsonl')]
PH = json.load(open(R + 'human_set_analysis/posthoc.json')); HIS = PH['history']
def wlt(x): return '-'.join(str(v) for v in x)
nov = [
 ('2026-11-01 ~09:25 and ~09:41', 'WCXB test (511)', 'ChromeRAG 0.1.4 (`ec56321`), 3 modes; Trafilatura version and metadata variants', 'Adoption-strategy work; **void**: ChromeRAG numbers never reported and no change derived from them; Trafilatura-only variants used for the version sensitivity in Table S3', 'author record'),
 ('2026-11-01 11:04', 'WCXB test (511)', 'rs-trafilatura 0.1.1, CI run 41339838506 (Linux)', 'one run, third-party tool only; outputs re-scored with our scorer (Table S3)', 'author record; scores in `revision_rows/p03_extra_rows.json`'),
 ('2026-11-01', 'strict dev (1,238)', 'rs-trafilatura 0.1.1, CI run 41345382478', 'development comparison (not held out)', 'author record'),
 ('2026-11-01 (commit 2263988)', 'CRAG split 0 (500)', 'ChromeRAG candidate code, gpt-5.6-luna', '**void**: harness chunking bug (long single lines dropped); $0.7569; results deleted', 'author record'),
 ('2026-11-01 (commit 602590f)', 'CRAG split 0 (500)', 'ChromeRAG candidate code, gpt-5.6-luna', 'practice run, used to choose the default mode; $0.7602', '`answer_test_practice/crag_split0.json`'),
]
for r in jl:
    if r.get('set') == 'new_pages' and 'purpose' not in r:
        nov.append(('2026-11-01', 'new pages (307 fetched)', 'run ' + r['run_id'][:8] + '; 7 tools listed, freeze-0.1.5 (rs-trafilatura not installed: no output on any page)', 'single extraction run of the frozen page list (tag pages-2026-11)', '`new_pages/new_pages_extract.json`'))
    elif 'purpose' in r:
        purpose = r['purpose'].replace('reviewer-requested robustness row', 'author-added robustness row (ledger says "reviewer-requested" in error)')
        nov.append((r['date_time'], f"{r['set']} ({r['n']})", 'run ' + r['run_id'][:8] + '; ' + r['commit'], purpose, '`' + r['result_file'].replace('evaluations/2026-11-final/results/', '') + '`'))
nov += [
 ('2026-11-01', 'new pages (296)', 'GPT page judge, gpt-5.6-luna', '**crashed** on an API timeout at 630 of 643 jobs (author log; this run judged two baselines; MarkItDown was added before the rerun, which had 963 jobs, 888 pairs and 75 swapped re-judgments); $0.642; no result kept or seen', 'author record'),
 ('2026-11-01', 'new pages (296)', 'GPT page judge, gpt-5.6-luna, rubric-2026-11', 'complete run, 963 judgments (888 primary, 75 swapped); $1.2267', '`new_pages/new_pages_judge.json`'),
 ('2026-11-01', 'CRAG splits 0 and 1', 'regrade of saved answers under rubric v2', 'post hoc; split 1 $0.2696, split 0 $0.2786', '`answer_test_regrade_posthoc/`'),
 ('2026-11-01', 'first human-set draw (75 of the 296 new pages; never sent to raters; replaced 2026-11-02)', 'no separate judge run: GPT verdicts on these pages were part of the 296-page run above, whose totals had been seen', 'post hoc on the 75 drawn pages (ChromeRAG-baseline-tie): ' + wlt(HIS['first_draw']['gpt_on_first_draw_pages_posthoc']['chromerag_vs_trafilatura']) + ' vs Trafilatura, ' + wlt(HIS['first_draw']['gpt_on_first_draw_pages_posthoc']['chromerag_vs_readability']) + ' vs Readability', '`human_set_analysis/posthoc.json` (history)'),
 ('2026-11-02 (judge plan 4f5ce3a, 18:52)', 'approved-site human set before 5 length swaps (75)', 'GPT, Grok, Gemini judges', 'totals seen; then two tool-blind length rules swapped 5 pages (850cf98, 5ebf4fb); GPT ' + wlt(HIS['ai_judges_on_approved_site_set']['gpt']['set_before_length_swaps']['chromerag_vs_trafilatura']) + ' before and ' + wlt(HIS['ai_judges_on_approved_site_set']['gpt']['final_set']['chromerag_vs_trafilatura']) + ' after the swaps vs Trafilatura (Table S6)', '`human_set_ai_judges/*.progress.jsonl`; `human_set_analysis/posthoc.json`'),
 ('2026-11-02 19:21 (commit 3b4f43d)', 'human set (75)', 'GPT, Grok, Gemini judges, 163 judgments each', '5 swapped-in pages judged; all verdicts frozen before any human rating was returned', '`human_set_ai_judges/`'),
 ('2026-11-04 to 2026-11-19', 'human set (75)', '5 raters, app 1.1.0', 'analysis fixed before rating, commit 70b7d93 (Table S6)', '`evaluations/2026-11-final/human_set_ratings/` (pseudonymized files and `label_key.json`)'),
 ('2026-11-20', 'human set (75)', 'post hoc analyses, no new data', 'robustness, training-domain overlap, set history, coded error analysis (Table S6)', '`human_set_analysis/`'),
 ('2026-11-20', 'WCXB test (upstream copy)', 'hash check, CI run 44818754399', 'local test split equals the upstream copy (1,022 files)', '`revision_rows/gt_upstream_check.json`'),
]
tbl(['When', 'Set', 'Code or tool', 'Purpose and status', 'Source'], nov)
w('Two rows of `held_out_runs.jsonl` (the planned WCXB test run and CRAG split 1, both on 1 November) were missing and were reconstructed on 20 November from the result files and git history (field `added`). Of the 20 November WCXB test rows, the raw and stripped output, subsets, old code and BoilerPy3 were requested in review; jusText, the Trafilatura options and speed were added by the author. The `purpose` field of the two Trafilatura option rows says "reviewer-requested"; that label is wrong, and the rows were added by the author. Ledger rows are kept as written.')
w('')
w('Code changed after a test-split result was seen (before the freeze): on 1 November rs-trafilatura was scored on the test split at 11:04; four ideas described for it were then implemented without reading its source and tested on the strict development pages only, and one passed (a richer collapse signal for the coverage retry, +0.00017 F1 on 5 development pages; commit `f1de490`, 16:57, public through `freeze-0.1.5`; credited in the acknowledgements). The test split was not used for that decision (author record). Other `src/` commits that day also followed the morning test-split runs and preceded the freeze: `6629eda` (09:34, rule groups and detectors dropped by the strict development rule), `af8ff55` (12:23, table rescue and model refit), `b1ba63e` (14:31) and `5a66bb5` (15:50, output and review fixes) and `602590f` (17:35, answer-test and output fixes). Their messages record development-page measurements only; no record links them to a test-split result, but the history alone cannot show that.')
w('')
w('The BoilerPy3 ledger row keeps the `ground_truth_check` text written before the upstream digest was checked; the later check, in a separate CI run, matched (`ci/README.md`).')
w('')
w('Not done: the planned continuity rejudge of the 328 v0.1.4 pages; rs-trafilatura on the 296 new pages and on the human set.')
w('')
w('The protocol section "Sets scored exactly once" held for the new pages and CRAG split 1. The WCXB test split was scored once as planned on 1 November and re-scored on 20 November with the same frozen code for rows requested in review and rows added by the author; this is recorded as a dated amendment in `PROTOCOL.md` ("Re-scoring of the WCXB test split for review"). Ledger times are local time with UTC offset.')
w('')

# ---------------- S2
w('## Table S2. Judge and grader settings')
w('')
gptj = json.load(open(R + 'human_set_ai_judges/gpt.json')); grok = json.load(open(R + 'human_set_ai_judges/grok.json')); gem = json.load(open(R + 'human_set_ai_judges/gemini.json'))
c1 = json.load(open(R + 'answer_test_locked_planned/crag_split1.json')); npj = json.load(open(R + 'new_pages/new_pages_judge.json'))
tbl(['Use', 'Model id (as recorded)', 'Access route', 'Temperature', 'Other settings', 'Source'], [
 ['Page judge, 296 new pages', npj['model'], 'OpenAI API, chat completions', 'not sent (API default)', f"JSON mode; reasoning effort low; A/B order seed {npj['seed']}; {npj['budget_chars']:,} characters per text; cost ${npj['cost_usd']}", '`new_pages/new_pages_judge.json`, `poc/final_page_judge.py`, `poc/openai_client.py`'],
 ['Page judge, human set', gptj['model'], 'OpenAI API, chat completions', 'not sent (API default)', f"as above; seed {gptj['seed']}; the file records cost 0.0 because cost was not tracked (author record: $0.208; no public file)", '`human_set_ai_judges/gpt.json`'],
 ['Page judge, human set', grok['model'], 'third-party agent tool', 'unknown, not controllable', grok['access'], '`human_set_ai_judges/grok.json`'],
 ['Page judge, human set', gem['model'], 'third-party agent tool', 'unknown, not controllable', gem['access'], '`human_set_ai_judges/gemini.json`'],
 ['CRAG answers and grading', c1['model'], 'OpenAI API, chat completions', f"0 requested; dropped by the API (generate {c1['temperature_dropped_generate']}, judge {c1['temperature_dropped_judge']})", 'question sample seed 0; top 5 BM25 chunks of 200 words; context cap 1,200 words', '`answer_test_locked_planned/crag_split1.json`, `poc/crag_answer_eval.py`'],
 ['v0.1.4 rounds (superseded)', 'Claude Sonnet 5.5; gpt-5.6-luna; Gemini 3.7 Flash', 'Claude sub-agents; OpenAI API; not recorded', 'not recorded', 'prompt hash 6f502417…', 'Table S1a'],
])
w('All page judges use the same rubric (`RUBRIC.md`, tag `rubric-2026-11`), see tool outputs labeled A and B only, and re-judge each pair with A and B swapped with probability 0.1 (realized: 75 of 888 pairs on the 296 new pages; 13 of 150 per judge on the human set). Model ids are the ids requested (no returned model snapshot string was saved); for Grok and Gemini, as recorded in the third-party agent tool; "medium" (Grok\'s reasoning level, and part of the Gemini model id) was selected in that tool and could not be verified. Both ran as coding agents; the public files do not record what the agent tool could read besides the job file, so their blinding rests on the job file and cannot be shown. The access-route label in `human_set_ai_judges/grok.json` was reworded to a neutral label on 20 November (private history); no verdict changed. Outside judging, a Claude model (Claude Opus 5.5) was used throughout development, for the address and page safety reviews together with Grok, and for coding the error analysis; Grok wrote and reviewed code and reviewed the practice notes; Gemini reviewed code, the protocol and the CRAG harness; a coding model offered in a third-party coding-agent tool wrote part of the code; GPT judged repeatedly, and Gemini 3.7 Flash twice, during v0.1.4 development (Table S1a). No Claude model is used as a judge in this version.')
w('')

# ---------------- S3
p03 = json.load(open(R + 'revision_rows/p03_extra_rows.json')); p07 = json.load(open(R + 'revision_rows/p07_front_matter.json'))
w('## Table S3. WCXB test split: all rows')
w('')
w('Sources: `revision_rows/p03_extra_rows.json` (subsets, baselines, old code), `revision_rows/p07_front_matter.json` (raw and stripped output), `revision_rows/p13_justext.json`, `revision_rows/p13_boilerpy3.json`. ChromeRAG rows remove one leading YAML front-matter block unless marked raw. Scorer: `poc.wcxb.word_f1` and `snippet_rate` (same tokenizer as WCXB `evaluate.py`; an empty snippet list scores 1.0; this holds for 5 pages in the without list and 6 in the with list, the same for every tool). Paired intervals resample 444 sites, 5,000 draws, seed 0.')
w('')
names = [('chromerag_balanced', 'ChromeRAG 0.1.5 balanced'), ('chromerag_coverage', 'ChromeRAG 0.1.5 coverage'), ('chromerag_precision', 'ChromeRAG 0.1.5 precision'),
         ('old013_balanced', 'freeze-0.1.3 code + 0.1.5 model, balanced'), ('old013_coverage', 'freeze-0.1.3 code + 0.1.5 model, coverage'), ('old013_precision', 'freeze-0.1.3 code + 0.1.5 model, precision'),
         ('trafilatura', 'Trafilatura 2.2.0 (no metadata)'), ('rs_trafilatura', 'rs-trafilatura 0.1.1'), ('readability', 'Readability (readability-lxml 0.9)'),
         ('boilerpy3_default', 'BoilerPy3 1.0.7 DefaultExtractor'), ('boilerpy3_article', 'BoilerPy3 1.0.7 ArticleExtractor'), ('justext', 'jusText 3.0.2'), ('markitdown', 'MarkItDown 0.1.7')]
for key, title in [('all_511', 'All 511 pages'), ('i_clean_372', '372 pages not duplicated in dev/ (primary set of v0.1.4)'), ('ii_domain_absent_from_original_dev', '311 pages whose domain is absent from the original dev/ folder')]:
    blk = p03[key]
    w(f"**{title}** (n = {blk['n']}, sites = {blk['n_sites']}).")
    w('')
    tbl(['Tool', 'P', 'R', 'F1', 'Without', 'With', 'Pages F1 < 0.1', 'Empty outputs'],
        [[t, f(blk['summary'][k]['p']), f(blk['summary'][k]['r']), f(blk['summary'][k]['f1'], 4), f(blk['summary'][k]['without']), f(blk['summary'][k]['with']), blk['summary'][k]['under_0_1'], blk['summary'][k]['empty_outputs']] for k, t in names])
    w('Paired differences: ' + '; '.join(f"{k.replace('_', ' ')}: F1 {sg(v['f1']['mean'], 4)} {ci(v['f1']['ci95'], 4)}, without {sg(v['without']['mean'], 4)} {ci(v['without']['ci95'], 4)}, with {sg(v['with']['mean'], 4)} {ci(v['with']['ci95'], 4)}" for k, v in blk['paired'].items()) + '.')
    w('')
w('**Raw and stripped output (all 511 pages).** Source `p07_front_matter.json`.')
w('')
tbl(['Output', 'P', 'R', 'F1', 'Without', 'With'], [[k, f(v['p']), f(v['r']), f(v['f1'], 4), f(v['without']), f(v['with'])] for k, v in p07['summary'].items()])
tbl(['Paired difference', 'F1', 'Without', 'With'], [[k, f"{sg(v['f1']['mean'], 4)} {ci(v['f1']['ci95'], 4)}", f"{sg(v['without']['mean'], 4)} {ci(v['without']['ci95'], 4)}", f"{sg(v['with']['mean'], 4)} {ci(v['with']['ci95'], 4)}"] for k, v in p07['paired'].items()])
fm = p07['front_matter']
w(f"Front matter: ChromeRAG writes a block on all 511 pages (mean {fm['chromerag_balanced']['mean_front_matter_words']:.1f} words; keys {fm['chromerag_balanced']['key_counts']}); Trafilatura with `with_metadata=True` writes one on {fm['trafilatura_meta']['pages_with_front_matter']} pages (mean {fm['trafilatura_meta']['mean_front_matter_words']:.1f} words; keys {fm['trafilatura_meta']['key_counts']}). Trafilatura's body text is identical with and without metadata on {p07['trafilatura_meta_body_equal_to_without_metadata_pages']} pages. Default CLI and API output are the same (note in the file).")
w('')
TO = json.load(open(R + 'revision_rows/trafilatura_options.json'))
w('**Trafilatura recall and precision options** (added by the author; the run records label them reviewer-requested in error, see Table S1b; source `revision_rows/trafilatura_options.json`, harness `poc/trafilatura_options.py`). Trafilatura ' + TO['versions']['trafilatura'] + ' with the same arguments as the default row (Markdown, tables, no comments, no links, no metadata) plus `favor_recall=True` or `favor_precision=True`; each run once on ' + str(TO['n_pages']) + ' pages; the default configuration was reproduced page by page in the same pass. These options had already been looked at on this split on 1 November with default (plain-text) arguments (baseline reconciliation note: F1 0.842 and 0.782; caveat in `revision_rows/trafilatura_options.md`), so the rows confirm rather than first measure them.')
w('')
tbl(['Output', 'P', 'R', 'F1', 'Without', 'With', 'Pages F1 < 0.1', 'Empty outputs'], [[lab, f(TO['summary'][k]['p']), f(TO['summary'][k]['r']), f(TO['summary'][k]['f1'], 4), f(TO['summary'][k]['without']), f(TO['summary'][k]['with']), TO['summary'][k]['under_0_1'], TO['summary'][k]['empty_outputs']] for k, lab in [('chromerag_balanced', 'ChromeRAG 0.1.5 balanced'), ('trafilatura_default_repro', 'Trafilatura 2.2.0 default (reproduced)'), ('trafilatura_favor_recall', 'Trafilatura 2.2.0 favor_recall'), ('trafilatura_favor_precision', 'Trafilatura 2.2.0 favor_precision')]])
tbl(['Paired difference', 'F1', 'Without', 'With'], [[k.replace('_', ' ').replace('2 2 0', '2.2.0'), f"{sg(v['f1']['mean'], 4)} {ci(v['f1']['ci95'], 4)}", f"{sg(v['without']['mean'], 4)} {ci(v['without']['ci95'], 4)}", f"{sg(v['with']['mean'], 4)} {ci(v['with']['ci95'], 4)}"] for k, v in TO['paired'].items()])
vt = [v for v in TO['version_table'].values() if v.get('split') == 'test']
w('**Trafilatura versions** (saved files of the 1 November baseline reconciliation, not re-run; values as recorded in `trafilatura_options.json`, key `version_table`; no snippet rates in those files). ' + TO['version_table_note'] + ' The 1,495 dev pages are the whole WCXB `dev/` folder; 22 have fewer than 30 reference words, and the strict split keeps 1,238 of the remaining 1,473.')
w('')
tbl(['Trafilatura', 'Test F1, repo arguments', 'Test F1, library default', 'favor_recall (default arguments)', 'favor_precision (default arguments)'],
    [[v['trafilatura'], f(v['f1_repo_config'], 4) if v.get('f1_repo_config') is not None else 'n/a', f(v['f1_default_config'], 4) if v.get('f1_default_config') is not None else 'not rerun', f(v['f1_favor_recall_default_args'], 4) if v.get('f1_favor_recall_default_args') is not None else 'n/a', f(v['f1_favor_precision_default_args'], 4) if v.get('f1_favor_precision_default_args') is not None else 'n/a'] for v in vt])
best_v = max(max(x for x in (v.get('f1_repo_config'), v.get('f1_default_config')) if x is not None) for v in vt)
w(f"Version 2.2.0, used throughout, is in the table above (F1 {TO['summary']['trafilatura_default_repro']['f1']:.4f}). The highest test F1 of any listed version and configuration is {best_v:.4f}, " + ('below' if best_v < TO['summary']['chromerag_balanced']['f1'] else 'not below') + f" ChromeRAG balanced ({TO['summary']['chromerag_balanced']['f1']:.4f}). The package pins `trafilatura>=1.12.0` only for the optional `[baselines]` extra; all main-text Trafilatura numbers use 2.2.0.")
w('')
oc = P2['old_code_control']['difference_0_1_5_minus_old']
w(f"**Old-code control** (all 511 pages; 0.1.5 minus the freeze-0.1.3 code with the 0.1.5 model): F1 {sg(oc['f1']['mean'], 4)} {ci(oc['f1']['ci95'], 4)}, without-rate {sg(oc['without']['mean'], 4)} {ci(oc['without']['ci95'], 4)}, with-rate {sg(oc['with']['mean'], 4)} {ci(oc['with']['ci95'], 4)}. The rules added while the split was consulted leave F1 unchanged and lower both snippet rates; the without-rate is the figure most exposed to that use.")
w('')
w('**Published values** (WCXB paper, test split, configurations of the benchmark authors): rs-trafilatura 0.903, Trafilatura 0.841, Readability 0.736. The benchmark paper states that rs-trafilatura was developed by its lead author and tested against the development set. BoilerPy3 provenance: CI run 44817203676 (ubuntu-24.04, Python 3.12) on WCXB upstream commit `c039d5e…`, artifact sha256 in `p13_boilerpy3.json`; `gt_upstream_check.json` shows that copy equals ours. rs-trafilatura provenance: CI run 41339838506, outputs re-scored here.')
w('')

# ---------------- S4
w('## Table S4. F1 by page type')
w('')
w('**WCXB test split** (source `p03_extra_rows.json`, key `iii_per_type`; intervals resample sites within the type).')
w('')
pt = p03['iii_per_type']
tools = ['chromerag_balanced', 'chromerag_coverage', 'chromerag_precision', 'trafilatura', 'rs_trafilatura', 'readability', 'boilerpy3_default', 'justext', 'markitdown', 'old013_balanced']
tbl(['Type (n, sites)'] + tools + ['Balanced − Trafilatura'], [[f"{t} ({v['n']}, {v['n_sites']})"] + [f(v['mean_f1'][k]) for k in tools] + [f"{sg(v['balanced_minus_trafilatura_f1']['mean'])} {ci(v['balanced_minus_trafilatura_f1']['ci95'])}"] for t, v in pt.items()])
FP = P2['wcxb_forum_platforms']; FB = FP['balanced_minus_trafilatura_f1']
w('**WCXB test forums by platform** (post hoc; source `posthoc_round2/round2_posthoc.json`, key `wcxb_forum_platforms`; script `poc/rev1_round2_posthoc.py`; same paired site bootstrap). Rule: ' + FP['rule'] + ' "Seen" means the platform is detected on at least one of the ' + str(FP['strict_training_forum_pages']) + ' strict training forum pages (detected platforms on ' + str(sum(FP['strict_training_forum_pages_by_platform'].values())) + ' of them: ' + ', '.join(f'{k} {v}' for k, v in FP['strict_training_forum_pages_by_platform'].items()) + '; the rest match no listed platform). ' + FP['rule_history'])
w('')
tbl(['Forum pages', 'Pages', 'Sites', 'ChromeRAG F1', 'Trafilatura F1', 'Balanced − Trafilatura'], [[lab, FB[k]['n_pages'], FB[k]['n_sites'], f(FB[k]['chromerag_mean_f1']), f(FB[k]['trafilatura_mean_f1']), f"{sg(FB[k]['mean'])} {ci(FB[k]['ci95'])}"] for k, lab in [('all_forum_pages', 'All'), ('seen_in_training_forum_pages', 'Platform seen in training'), ('seen_without_stackexchange', 'Seen, without Stack Exchange'), ('not_seen_in_training', 'Platform not seen'), ('not_identified', 'Not identified'), ('not_seen_or_not_identified', 'Not seen or not identified')]])
tbl(['Platform (test)', 'Pages', 'Sites', 'Balanced − Trafilatura'], [[k, v['n_pages'], v['n_sites'], f"{sg(v['mean'])} {ci(v['ci95'])}"] for k, v in FP['by_platform'].items()])
w('The split holds out domains, not forum software: two thirds of the test forum pages run a platform also present in training. "Not seen" refers to training forum pages only: 6 of the 13 such pages are bbPress, whose markup occurs on 10 training pages of other types (`results/posthoc_round2/round2_posthoc.json`, key `strict_training_pages_any_type_by_platform`).')
w('')
w('**Strict development cross-validation** (1,238 pages, five folds grouped by registrable domain, models never see their test fold; source `evaluations/2026-10-v0.1.3/strict_dev_cv.json`, means computed from the per-page rows; `chromerag` is balanced).')
w('')
dev = json.load(open(O + 'strict_dev_cv.json'))
by = collections.defaultdict(list)
for r in dev: by[r['type']].append(r); by['all'].append(r)
dt = ['chromerag', 'chromerag_coverage', 'chromerag_precision', 'trafilatura', 'readability', 'markitdown']
tbl(['Type (n)'] + dt + ['balanced without'], [[f"{t} ({len(rs)})"] + [f(sum(x[k]['f1'] for x in rs) / len(rs)) for k in dt] + [f(sum(x['chromerag']['without'] for x in rs) / len(rs))] for t, rs in sorted(by.items(), key=lambda kv: (kv[0] != 'all', kv[0]))])
w('rs-trafilatura was also run once on these development pages (CI run 41345382478). Its outputs and per-page scores are not in the repository, so its development scores are not reported here and are not used for any claim.')
w('')

# ---------------- S5
ab = json.load(open(O + 'strict_ablation_cv.json'))
w('## Table S5. Component ablation on strict development pages')
w('')
w(f"Source: `evaluations/2026-10-v0.1.3/strict_ablation_cv.json` (commit `4bebd13`, inside `freeze-0.1.5`; harness `poc/ablation_cv.py`). Protocol: {ab['protocol']['pages']:,} pages ({ab['protocol']['ids_file']}), the five cross-validation fold models, priority {ab['protocol']['priority']}. Balanced mode; each row changes one switch against the full pipeline (F1 {ab['summary']['baseline']['mean_f1']:.4f}, without {ab['summary']['baseline']['mean_without']:.4f}, median {ab['summary']['baseline']['median_ms']:.1f} ms on that machine). Intervals: site bootstrap, 5,000 draws, seed 0.")
w('')
w('Component rows reuse the five fold models, which were trained on blocks left after all cleaning stages; a row that switches a stage off is not retrained, so it measures that stage\'s contribution to the shipped model. Decision rule, fixed before the runs in the author\'s dated plan (not in the repository; available to the editor on request): drop a component if removing it does not lower mean F1 (ΔF1 ≥ 0) and does not raise the without-snippet rate; ship the stacked model only if its F1 interval is above zero with acceptable size and speed. Decisions were taken on the runs before the final rebuild (the documentation-framework rules on commit `7ca7e9e`); on this frozen run the consent rules (`no_yaml_consent`), the Trafilatura-derived author and footer groups (`no_tf_author`, `no_tf_footer`), structure rules and table rescue also meet the drop rule (structure and table rescue are the disclosed exceptions), and several other switches change both measures by under 0.0005; all remain as switches. Rows are not additive: a row that removes a stage runs the model on blocks unlike those it was trained on. Dropped: Trafilatura-derived rule groups `tf.related`, `tf.share`, `tf.newsletter`, `tf.ads`, `tf.tools`; the 16 documentation-framework YAML rules; the pager and related-post detectors (switched off by default, so their rows below are zero). Kept as disclosed exceptions: structure rules (removal lowers recall by more than 0.05 on 10 pages and raises it on none) and table rescue (keeps plan tables such as the pricing example). Not shipped: the stacked second model (F1 interval above zero, but 10.3 times the file size, one of about 30 comparisons, and many per-page recall swings).')
w('')
def s4(x): return sg(x, 4) if abs(x) >= 0.00005 else '0.0000'
def ci4(c): return '[' + ', '.join(s4(z) for z in c) + ']'
rowsS5 = []
for k, v in ab['summary'].items():
    if k == 'baseline': continue
    rowsS5.append([k, f"{v['mean_f1']:.4f}", f"{s4(v['delta_f1']['mean'])} {ci4(v['delta_f1']['ci95'])}", f"{v['mean_without']:.4f}", f"{s4(v['delta_without']['mean'])} {ci4(v['delta_without']['ci95'])}", f"{v['median_ms']:.1f}" + (f" ({v['stack_model_bytes']:,} bytes)" if 'stack_model_bytes' in v else '')])
tbl(['Configuration', 'F1', 'ΔF1', 'Without', 'ΔWithout', 'Median ms'], rowsS5)
w('Key: `no_lbc` learned filter off (original density scoring runs instead); `rules_only` filter and density scoring off; `filter_only` YAML rules, generic detectors, chrome pruning and Trafilatura-style density passes off; `no_trafilatura_ideas` the Trafilatura-style density passes (`trafilatura_ideas.py`) off; `no_yaml_*` one YAML file off; `chrome_no_*` one generic detector off; `no_tf_*` one Trafilatura-derived YAML rule group off; `stack_stage2` a second-stage model added. Per-type mean ΔF1 for every configuration: key `mean_delta_f1_by_type_sorted` in the same file.')
w('')

# ---------------- S5b
fg = json.load(open(R + 'revision_rows/feature_group_ablation.json'))
w('## Table S5b. Feature-group ablation of the learned block filter on strict development pages')
w('')
w("Source: `evaluations/2026-11-final/results/revision_rows/feature_group_ablation.json` (script `poc/feature_group_ablation.py`). Added in review; development pages only, no test page used. Same protocol as Table S5: the 1,238 strict pages, five folds grouped by registrable domain, the shipped hyperparameters (300 trees, depth 6), balanced threshold, site bootstrap with 5,000 draws, seed 0. Each row retrains the fold models with the named feature group removed or with only the named groups kept; the rest of the pipeline is unchanged. The full row reproduces Table S5 on every page. `shallow_only` keeps the block's own shallow text statistics and the length and link density of the previous and next block, an approximation of the feature set of Kohlschütter et al. [3] (no wrapped-line text density; neighbours add only length and link density), here trained on the same pages as ChromeRAG. The shipped tree settings (300 trees, depth 6) date from the first learned model of 1 October and were not re-tuned for the strict split.")
w('')
grp = fg['groups']
w('Groups (features): ' + '; '.join(f"`{g}` {v['n_features']}" for g, v in grp.items()) + '.')
w('')
rowsS5b = []
for mode in ('pipeline', 'filter_only'):
    for k, v in fg['rows'][mode].items():
        d1 = v.get('delta_f1_vs_full'); d2 = v.get('delta_without_vs_full')
        rowsS5b.append([mode.replace('_', ' '), k, f"{v['mean_f1']:.4f}",
                        (f"{s4(d1['mean'])} {ci4(d1['ci95'])}" if d1 else '–'),
                        f"{v['mean_without']:.4f}",
                        (f"{s4(d2['mean'])} {ci4(d2['ci95'])}" if d2 else '–'),
                        f"{v['f1_by_type']['article']:.3f} / {v['f1_by_type']['forum']:.3f}"])
tbl(['Mode', 'Row', 'F1', 'ΔF1', 'Without', 'ΔWithout', 'Article / forum F1'], rowsS5b)
w('')

# ---------------- S6
w('## Table S6. Human rating study: full analysis fixed in advance')
w('')
w('Source: analysis of the five returned rating files as fixed in advance (plan in `PROTOCOL.md`, "Analysis plan for the human rating set", committed in `70b7d93` on 2 November, with the per-page majority verdict from the section "Human rating set" and its 2 November amendments; all before any rating; not registered with a third party). Unit: page (75 main pages from 48 sites; practice items and repeats excluded from votes). Outcome per page: plurality of rater verdicts; equal top counts give a tie. Pairwise verdict from the set of outputs ticked as best (one tool in the set and the other not = win; otherwise tie). Intervals: site bootstrap, 10,000 draws, seed 20261120. Net = (wins − losses) / pages, from the view of the tool named before "vs". Pseudonymized rating files and the label key are in `evaluations/2026-11-final/human_set_ratings/`; the analysis is `poc/human_set_analysis.py`; rater-level rows are shown without identifiers.')
w('')
def nrow(label, o): return [label, o['n'], o.get('n_sites', ''), f"{o['wins']}/{o['losses']}/{o['ties']}", f"{sg(o['net'], 2)} {ci(o['net_ci95'], 2)}"]
for pair, title in [('chromerag_vs_trafilatura', 'ChromeRAG vs Trafilatura'), ('chromerag_vs_readability', 'ChromeRAG vs Readability'), ('trafilatura_vs_readability', 'Trafilatura vs Readability')]:
    m = H['main'][pair]; s = H['sensitivity_without_flagged_raters']['results'][pair]
    rows6 = [nrow('All pages' + (' (primary outcome)' if pair == 'chromerag_vs_trafilatura' else ''), m['overall']), nrow('Forums only', m['forums_only']), nrow('Without forums', m['without_forums'])]
    for g, o in m['by_page_group'].items(): rows6.append(nrow(f'Group: {g}', o))
    rows6 += [nrow('Sensitivity, without the flagged rater: all', s['overall']), nrow('Sensitivity, without the flagged rater: without forums', s['without_forums'])]
    w(f'**{title}.** Krippendorff alpha (nominal): all raters {m["krippendorff_alpha_nominal"]:.2f}; without the flagged rater {s["krippendorff_alpha_nominal"]:.2f}.')
    w('')
    tbl(['Subset', 'Pages', 'Sites', 'W/L/T', 'Net [95% CI]'], rows6)
    pr = sorted((v['net'] for v in m['per_rater'].values()), reverse=True)
    w('Per-rater net (no identifiers, sorted): ' + ', '.join(sg(x, 2) for x in pr) + f". Page groups with fewer than 8 pages (not analyzed separately): " + ', '.join(f'{k} {v}' for k, v in m['page_groups_below_8'].items()) + '.')
    w('')
w('Page groups in the set: ' + ', '.join(f"{k} {v}" for k, v in H['page_groups'].items()) + '. Groups were defined by the author-approved site list before rating.')
w('')
ms = H['mean_scores_main']
w('**Mean 1–5 scores** (all ratings of main pages):')
w('')
tbl(['Tool', 'Ratings', 'Content kept', 'Noise left in (5 = none)'], [[t, v['n_ratings'], f"{v['content']:.2f} {ci(v['content_ci95'], 2).replace('+', '')}", f"{v['chrome']:.2f} {ci(v['chrome_ci95'], 2).replace('+', '')}"] for t, v in ms.items()])
w('**Score differences** (secondary outcome fixed in advance; ChromeRAG minus baseline, per-page mean over raters, site bootstrap; script `poc/human_set_score_diff.py`):')
w('')
for line in SD: w('    ' + line)
w('')
cc = H['careless_checks']
w('**Rating-quality checks** (the protocol\'s careless-rating rules, fixed before rating; no identifiers): median seconds per rated item ' + ', '.join(f"{v['median_seconds']:.0f}" for v in sorted(cc.values(), key=lambda v: -v['median_seconds'])) + '; no rater under 30 s; no rater gave one screen position on 90% or more of items. Repeat check (applies with 4 or more repeat pairs): one full-set rater agreed on 3 of 4; the other agreed on 1 of 5 and was flagged (`inconsistent_repeats`); all four changed repeats of the flagged rater moved one step for ChromeRAG against Trafilatura (win to tie, tie to win, tie to loss, loss to tie), none reversed (author record, checked by hand); against Readability one repeat reversed. Part raters had 1 or 2 repeats (2 of 2, 1 of 1, 0 of 2 agreed). The flagged rater stays in the primary result.')
w('')
aa = H['anchor_agreement']['chromerag_vs_trafilatura']
w(f"**Anchor pages** (5 pages assigned to every rater, ChromeRAG vs Trafilatura): mean pairwise agreement {aa['mean_pairwise_agreement']:.2f}, Krippendorff alpha {aa['krippendorff_alpha_nominal_anchors']:.2f}. Coverage: 67 pages with 3 ratings, 4 with 5 (anchors), 1 with 4, 3 with 2 (after 5 skipped ratings).")
w('')
w('**Human majority vs AI judges** (same 75 pages, same outputs; AI verdicts saved before any rating was read; agreement counts ties as their own outcome):')
w('')
r6 = []
for pair, js in H['human_vs_ai_judges'].items():
    for j, v in js.items():
        dis = v['disagreements_human_to_ai']; tie = sum(c for k, c in dis.items() if k.startswith('tie'))
        r6.append([pair, j, f"{v['agreement']:.2f} {ci(v['agreement_ci95'], 2).replace('+', '')}", f"{v['cohen_kappa']:.2f} {ci(v['cohen_kappa_ci95'], 2).replace('+', '')}", f"{sum(dis.values())} ({tie} human ties)", f"{sg(v['ai_net_preference']['net'], 2)} {ci(v['ai_net_preference']['net_ci95'], 2)}"])
tbl(['Pair', 'Judge', 'Agreement', "Cohen's kappa", 'Disagreements', 'AI judge net'], r6)
w('**AI judges by subset** (descriptive, not in the plan; same bootstrap; script `poc/human_set_ai_by_forum.py`):')
w('')
tbl(['Baseline', 'Judge', 'All 75', 'Forums (10)', 'Without forums (65)'], [[b, j] + [f"{sg(AIF[f'{b}/{j}/{s}']['net'], 2)} {ci(AIF[f'{b}/{j}/{s}']['net_ci95'], 2)}" for s in ('overall', 'forums_only', 'without_forums')] for b in ('trafilatura', 'readability') for j in ('gpt', 'grok', 'gemini')])
w('**Length effect on the human set** (method of Table S8; page bootstrap; "similar" = length ratio within 1.1):')
w('')
la = H['ai_judge_length_analysis']; r6 = []
for b in ('trafilatura', 'readability'):
    for j, v in la[b].items():
        if not isinstance(v, dict) or 'similar_length' not in v: continue
        r6.append([b, j, f"{v['similar_length']['pairs']}: {sg(v['similar_length']['net'], 2)} {ci(v['similar_length']['ci95'], 2)}", f"{v['chromerag_longer']['pairs']}: {sg(v['chromerag_longer']['net'], 2)}", f"{v['baseline_longer']['pairs']}: {sg(v['baseline_longer']['net'], 2)}", f"{v['win_probability_at_equal_length']['estimate']:.2f} {ci(v['win_probability_at_equal_length']['ci95'], 2).replace('+', '')}"])
tbl(['Baseline', 'Judge', 'Similar length: pages, net', 'ChromeRAG longer', 'Baseline longer', 'Win probability at equal length'], r6)
w('The exploratory intervals in this table come from the public script, which orders pages by item id; two interval cells differ in the second decimal from an earlier draft of this supplement, and no point value changed.')
w('')
w('Ratings used per rater and AI-tool use: all five raters stated that they used no AI tool while rating.')
w('')
# ---- S6, post hoc part
w('### S6, post hoc (computed after all ratings and after the planned analysis; not in the plan)')
w('')
w('Source `results/human_set_analysis/posthoc.json` and `posthoc.md` (script `poc/human_set_posthoc.py`; same site bootstrap, ' + f"{PH['bootstrap']['iterations']:,} draws, seed {PH['bootstrap']['seed']}" + '). Nothing here changes a rating, page, setting or tool; the planned result above stays the primary result. Leave-one-rater-out numbers use a fixed random order of the rater codes (not the published codes).')
w('')
def rr(o): return f"{sg(o['net'], 2)} {ci(o['net_ci95'], 2)} ({o['wins']}/{o['losses']}/{o['ties']})"
r6 = []
for pair, lab in [('chromerag_vs_trafilatura', 'vs Trafilatura'), ('chromerag_vs_readability', 'vs Readability')]:
    rb = PH['robustness'][pair]; a = rb['a_ties_excluded']; b = rb['b_opposite_verdicts']; d = rb['d_forums_reweighted']
    r6.append([lab, 'Ties excluded', f"{a['wins']} of {a['decided_pages']} decided pages; exact two-sided sign test p = {a['sign_test_two_sided_p']:.4f}"])
    r6.append([lab, 'Pages with opposite verdicts', f"{b['pages_with_at_least_one_vote_each_way']} of {b['pages']}; all raters agree {b['pages_all_raters_same_verdict']}, only win and tie {b['pages_win_and_tie_only']}, only loss and tie {b['pages_loss_and_tie_only']}; pooled single ratings W/L/T " + '/'.join(str(x) for x in b['pooled_ratings_win_loss_tie'])])
    for k, v in rb['c_leave_one_rater_out'].items():
        r6.append([lab, 'Leave one rater out: ' + k, rr(v)])
    r6.append([lab, 'Forums weighted at 10% (WCXB test share)', f"{sg(d['net'], 2)} {ci(d['net_ci95'], 2)} (forum net {sg(d['net_forum_pages'], 2)} on {d['forum_pages']} pages, other net {sg(d['net_other_pages'], 2)} on {d['other_pages']}; {d['bootstrap_draws_dropped_no_forum_or_no_other']} draws without a forum page dropped)"])
tbl(['Pair', 'Check', 'Result'], r6)
ov = PH['training_domain_overlap']
w(f"**Training-domain overlap.** {ov['rated_pages_on_training_domain']} of {ov['rated_pages']} rated pages share a registrable domain with at least one strict training page ({ov['rated_registrable_domains_on_training_domain']} of {ov['rated_registrable_domains_total']} sites; {ov['forum_pages_on_training_domain']} of {ov['forum_pages_total']} forum pages); exact URL matches with training pages: {ov['exact_url_matches_with_training']} (Public Suffix List {ov['psl_version']}; {ov['strict_training_pages']:,} strict training pages on {ov['strict_training_registrable_domains']:,} registrable domains). The 296 new pages were sampled with the domain exclusions of every earlier set (Table S8).")
w('')
tbl(['Pair', 'Without overlap', 'With overlap', 'Without overlap and without forums'], [[pair.replace('_', ' ')] + [f"{o['n']} pages, {o['n_sites']} sites: {rr(o)}" for o in (v['without_overlap'], v['with_overlap'], v['without_overlap_without_forums'])] for pair, v in ov['nets'].items()])
HD = P2['human_set_development_domains']; HN = HD['nets']
w(f"**Development domains (round 2, post hoc).** Counting the domains of all WCXB pages used in development (strict training and test split), {HD['pages_on_development_domains']} of {HD['pages']} rated pages ({HD['registrable_domains_on_development_domains']} of {HD['sites_registrable']} sites) are on such domains: " + ', '.join(f'{v} on {k.replace("_", " ")}' for k, v in HD['pages_by_category'].items()) + f"; test-only domains: {', '.join(HD['registrable_domains_on_test_split_only'])}; {HD['forum_pages_on_development_domains']} of {HD['forum_pages_total']} forum pages. Source `posthoc_round2/round2_posthoc.json`, key `human_set_development_domains`.")
w('')
tbl(['Pair', 'All', 'On development domains', 'Clean (no WCXB domain)', 'Clean, without forums', 'Clean forums'], [[pair.replace('_', ' ')] + [f"{v[k]['n']} pages, {v[k]['n_sites']} sites: {rr(v[k])}" for k in ('all_pages', 'pages_on_development_domains', 'clean_pages_no_wcxb_domain', 'clean_pages_without_forums', 'clean_forum_pages')] for pair, v in HN.items()])
RV = json.load(open(R + 'human_set_analysis/review_posthoc.json'))
w('')
w('**Agreement among AI judges and earlier evaluation domains (final review, post hoc).** Source `human_set_analysis/review_posthoc.json` (script `poc/human_set_posthoc_review.py`; public files only). AI judge verdicts are the primary (not swapped) verdicts on the 75 pages.')
w('')
tbl(['Pair', 'All three judges same', "Fleiss' kappa", "Pairwise Cohen's kappa"], [[k.replace('_', ' '), f"{v['all_three_same']} of {v['n_pages']}", f"{v['fleiss_kappa']:.2f}", ', '.join(f"{a} {x:.2f}" for a, x in v['pairwise_cohen_kappa'].items())] for k, v in RV['ai_judge_agreement'].items()])
EO = RV['earlier_set_overlap']
w('Earlier ChromeRAG evaluation sets (`evaluations/2026-10-v0.1.3/evaluation_domains.csv`: ' + ', '.join(EO['earlier_sets']) + ') share registrable domains, but no URL, with some rated pages not on WCXB domains; pages on those domains among the ' + str(EO['chromerag_vs_trafilatura']['no_wcxb_domain']['n']) + ' without a WCXB domain: ' + ', '.join(f"{k} {v}" for k, v in EO['chromerag_vs_trafilatura']['earlier_set_pages_among_no_wcxb'].items()) + ' (a domain can be in two sets).')
w('')
tbl(['Pair', 'All', 'No WCXB domain', 'No WCXB or earlier-set domain'], [[pair.replace('_', ' ')] + [f"{v[k]['n']} pages, {v[k]['n_sites']} sites: {rr(v[k])}" for k in ('all', 'no_wcxb_domain', 'no_wcxb_or_earlier_set_domain')] for pair, v in EO.items() if isinstance(v, dict)])
w('Intervals in this table come from `poc/human_set_posthoc_review.py`, whose resampling differs from the round-2 script, so a bound can differ by 0.01 from the development-domain table above (ChromeRAG against Readability, no WCXB domain: [+0.02, +0.54] here, [+0.03, +0.54] above).')
w('')
WS = RV['without_length_swapped_in_pages']
w('**Without the five pages swapped in after the AI totals were seen** (post hoc; same source): ' + '; '.join(f"{k.replace('_', ' ')}: {v['without_swapped_in']['n']} pages, {v['without_swapped_in']['n_sites']} sites, {rr(v['without_swapped_in'])}; swapped-in pages W/L/T {v['swapped_in_outcomes'].get('a', 0)}/{v['swapped_in_outcomes'].get('b', 0)}/{v['swapped_in_outcomes'].get('tie', 0)}" for k, v in WS.items() if k != 'swapped_in_pages') + '.')
w('')
fd = HIS['first_draw']
w(f"**History of the set.** The set fixed in the protocol on 2026-11-01 was a draw of {fd['main_pages']} pages from the 296 new pages (seed {fd['seed']}; " + ', '.join(f'{k} {v}' for k, v in fd['page_groups'].items()) + f"); the builder skipped {fd['candidates_skipped_for_short_tool_output']} candidates with short tool output. GPT verdicts on all 296 pages, and their totals, already existed. On 2026-11-02, before any rater received a page, the set was replaced for rater safety (a site reached in the first collection was flagged as unsafe, and saved pages could still load live images) by pages from an author-approved site list, with forums fixed at 10 of 75. After the three AI judges had judged that set and their totals had been seen, two tool-blind rules (all three outputs under 80 words; page text over 8,000 words) swapped 5 pages one for one; the verdicts on the 5 pages swapped out remain in the `*.progress.jsonl` files. Full dated record in `posthoc.md`.")
w('')
r6 = []
for j, v in HIS['ai_judges_on_approved_site_set'].items():
    for pair in ('chromerag_vs_trafilatura', 'chromerag_vs_readability'):
        r6.append([j, pair.replace('_', ' ')] + [wlt(v[s][pair]) for s in ('set_before_length_swaps', 'five_pages_swapped_out', 'five_pages_swapped_in', 'final_set')])
r6.append(['gpt (first draw, post hoc)', 'chromerag vs trafilatura', wlt(fd['gpt_on_first_draw_pages_posthoc']['chromerag_vs_trafilatura']), '', '', ''])
r6.append(['gpt (first draw, post hoc)', 'chromerag vs readability', wlt(fd['gpt_on_first_draw_pages_posthoc']['chromerag_vs_readability']), '', '', ''])
tbl(['Judge', 'Pair', 'Set before swaps (W-L-T)', '5 swapped out', '5 swapped in', 'Final set'], r6)
# coded error analysis, counts parsed from the committed report
EA = open(R + 'human_set_analysis/error_analysis.md', encoding='utf-8').read()
cnt = EA.split('### Counts', 1)[1].split('###', 1)[0]
crow = [ln for ln in cnt.splitlines() if ln.startswith('|')]
w('**Coded error analysis** (post hoc, descriptive; one coder, a Claude model (Claude Opus 5.5), after unblinding, with a scheme committed before coding; no second coder, so the counts describe these pages and are not a test). Pages: every page the human majority gave to Trafilatura or to Readability, and 15 randomly drawn pages ChromeRAG won against Trafilatura. Primary code per page, from `results/human_set_analysis/error_analysis.md` (codes, rules and per-page notes there):')
w('')
for ln in crow: w(ln)
w('')
w('Against Trafilatura the clearest losses are ChromeRAG keeping too little on short hub, landing and product pages; against Readability most losses are a missing title line or near-identical outputs; where ChromeRAG won, Trafilatura had dropped main content (on forums, the question or the replies after the first post). No page was coded as kept comments.')
w('')

# ---------------- S7
w('## Table S7. CRAG answer test')
w('')
w('Pipeline (`poc/crag_answer_eval.py`): for each question, each tool extracts the up to five pages supplied with it, and a separate BM25 index is built per question from those pages only; outputs (ChromeRAG front matter removed) are cut into 200-word chunks; BM25 retrieves the top 5 chunks (context cap 1,200 words); gpt-5.6-luna answers from that context only ("I don\'t know" if insufficient); the same model labels the answer accurate, missing or incorrect against the gold answer. Score = accurate − incorrect. Paired intervals: question bootstrap, 2,000 draws (per-question labels were not kept, so intervals cannot be recomputed from public files; point values can). Question filter (same for both splits; `filter_web_static`, metadata only, fixed before scoring): records with a non-empty `popularity` field are excluded (the author\'s plan treated them as knowledge-graph template questions and kept the web questions; this reading was not checked against the CRAG documentation), then false-premise, fast-changing and real-time questions and questions answered "invalid question" (split 1: 1,335 loaded, 582 with `popularity`, 115 false-premise, 81 fast or real-time, 0 invalid; 557 kept). No site model was passed; `enable_stce: true` in the run files has no effect without one.')
w('')
for path, title in [('answer_test_locked_planned/crag_split1.json', 'Split 1 (locked, run once on frozen code; planned result)'), ('answer_test_regrade_posthoc/crag_split1_rubric.json', 'Split 1, post hoc regrade under rubric v2 (stricter; same saved answers)'),
                    ('answer_test_practice/crag_split0.json', 'Split 0 (practice; consulted during development and used to choose the default mode)'), ('answer_test_regrade_posthoc/crag_split0_rubric.json', 'Split 0, post hoc regrade under rubric v2')]:
    d = json.load(open(R + path))
    w(f"**{title}.** Source `{path}`; model {d['model']}; spend ${d['spend_usd']}" + (f"; commit `{d['git_commit'][:7]}`; question filter counts {d['exclusion_counts']}" if 'git_commit' in d else '') + (' (the key `split0_loaded` is a fixed label in the harness; here it counts split-1 records)' if 'split1.json' in path else '') + '.')
    w('')
    tbl(['Tool', 'Accurate', 'Missing', 'Incorrect', 'Score', 'Indexed BM25 tokens per page', 'Empty pages'], [[t, f(v['accurate']), f(v['missing']), f(v['incorrect']), f(v['crag_score']), f"{v['mean_words_indexed_per_page']:,.0f}", v['n_pages_empty']] for t, v in d['tools'].items()])
    if 'paired_bootstrap_crag' in d:
        w('Paired differences: ' + '; '.join(f"{x['comparison']} {sg(x['mean_diff'])} {ci(x['ci95'])}" for x in d['paired_bootstrap_crag']) + '.')
        w('')
    if 'label_changes_v1_v2_by_tool' in d:
        w('Label changes from the original grader: ' + '; '.join(f"{t}: {v}" for t, v in d['label_changes_v1_v2_by_tool'].items()) + '.' + (' Regrade interval for balanced − Trafilatura on split 1: +0.014 [−0.038, +0.064] (author record; no public file, not recomputable).' if 'split1' in path else ''))
        w('')
c1t = c1['tools']
def hk(t): return c1t[t].get('gold_in_top5_short')
if hk('chromerag_balanced') is not None:
    ib, it = c1t['chromerag_balanced']['mean_words_indexed_per_page'], c1t['trafilatura']['mean_words_indexed_per_page']
    eb, et = c1t['chromerag_balanced']['mean_words_per_page_including_failed'], c1t['trafilatura']['mean_words_per_page_including_failed']
    w(f"Planned retrieval measure on split 1 (share of the {c1t['chromerag_balanced']['gold_in_top5_short_n']} questions with a short gold answer whose answer appears in the top 5 chunks, key `gold_in_top5_short`): ChromeRAG balanced {hk('chromerag_balanced'):.3f}, Trafilatura {hk('trafilatura'):.3f}, no difference. Words per page: indexed {ib:,.0f} against {it:,.0f} ({(1 - ib / it) * 100:.0f}% fewer), extracted {eb:,.0f} against {et:,.0f} ({(1 - eb / et) * 100:.0f}% fewer).")
    w('')
w('Void run: an earlier split-0 run (commit `2263988`, $0.7569) had a chunking bug (long single lines kept whole and dropped by the context cap); it was voided and rerun. Planned but not run: Readability and the share of retrieved chrome. `RUBRIC.md` was written after the split 1 run had been seen (`PROTOCOL.md`), so the regrade is post hoc. A blind re-grade of 30 answers, made during the pre-freeze cross-checks, agreed with the grader on 25 (author record; who re-graded is not recorded; no public file). Grader agreement with 101 fixture cases: 96.0% on labels (`PROTOCOL.md`).')
w('')

# ---------------- S8
w('## Table S8. GPT page judging on 296 new pages')
w('')
nj = npj['summary']; la8 = json.load(open(R + 'new_pages/length_analysis_posthoc.json'))
w('Pages: 307 fetched once from a frozen list sampled from the Tranco top 200,000 domains with domain exclusions of every earlier set (`PROTOCOL.md`, `seed_page_list.json`); 11 removed by a mechanical filter (8 non-English, 2 JSON bodies, 1 duplicate URL; `page_filter.json`), 296 judged. Disclosed: one Danish page and four non-content pages (template, login, CSS, empty) remain in the set. Judge: gpt-5.6-luna, rubric `RUBRIC.md` (Table S2). Primary verdict is the judge\'s own choice; the fixed-order verdict is a sensitivity row computed from the same scores (content score, then chrome score). Source `new_pages/new_pages_judge.json`; length analysis `new_pages/length_analysis_posthoc.json` (post hoc). The raw HTML of these pages was not retained: URLs (`seed_page_list.json`), HTML and output hashes and lengths (`new_pages/new_pages_extract.json`) and all judgments are published, but the pages cannot be re-extracted, and a new fetch would return different pages.')
w('')
tbl(['Baseline', 'Judge verdict W/L/T', 'Unclipped pairs W/L/T', 'Fixed-order W/L/T', 'Net, judge verdict', 'Similar length: W/L/T, net', 'ChromeRAG longer: net', 'Baseline longer: net', 'Win probability at equal length'],
    [[b, '/'.join(str(nj[b]['judge_verdict'][k]) for k in ('chromerag', 'baseline', 'tie')), '/'.join(str(nj[b]['judge_verdict_unclipped_pairs'][k]) for k in ('chromerag', 'baseline', 'tie')), '/'.join(str(nj[b]['fixed_order_sensitivity'][k]) for k in ('chromerag', 'baseline', 'tie')),
      f"{sg(la8[b]['all']['net'])} {ci(la8[b]['all']['ci95'])}", f"{la8[b]['similar_length']['chromerag']}/{la8[b]['similar_length']['baseline']}/{la8[b]['similar_length']['tie']}, {sg(la8[b]['similar_length']['net'])}" + (f" {ci(la8[b]['similar_length']['ci95'])}" if la8[b]['similar_length']['ci95'] else ''),
      (f"{sg(la8[b]['chromerag_longer']['net'])}" if la8[b]['chromerag_longer']['net'] is not None else 'n/a'), f"{sg(la8[b]['baseline_longer']['net'])}", f"{la8[b]['win_probability_at_equal_length']['estimate']:.3f} {ci(la8[b]['win_probability_at_equal_length']['ci95']).replace('+', '')}"] for b in ('trafilatura', 'readability', 'markitdown')])
lw = lambda b: la8[b]
w(f"Longer output wins {177}/{272} = 65% of decided ChromeRAG–Trafilatura pairs and {196}/{279} = 70% of ChromeRAG–Readability pairs, whichever tool is longer (audit recomputation from the stored judgments). Position check: {nj['position_check']['same_verdict']} of 75 swapped pairs gave the same verdict. MarkItDown output is always longer, so length cannot be separated for it. Reading: against Trafilatura the AI-judge preference is not robust (fixed-order 74–74); it is weak evidence and not used for claims beyond that.")
w('')

# ---------------- S9
w('## Table S9. Rater instructions (summary)')
w('')
tbl(['Item', 'What raters were told or shown'], [
 ['Task', 'Imagine a search assistant that can only read the extracted text; which labeled output (A, B, C) would give right answers most reliably to questions the page should answer? Same task text as the AI judges.'],
 ['Content and noise', 'Content: what the page exists to give (main text, facts, prices, steps, tables; on forums the question and answers). Noise: menus, footers, cookie and sign-up notices, share buttons, ads, links or teasers for other pages. No fixed trade-off; length alone never decides.'],
 ['Scores', 'Tick every output that is equally best, or "all about the same", or "none are good"; score each output 1–5 for content kept and noise left in, with anchor descriptions behind a Guide button; optional note; skip allowed.'],
 ['Practice', '5 practice items before the main set, each followed by a short note on what a careful rater would notice; not analyzed.'],
 ['Blinding', 'Outputs labeled A, B, C in random order; tool names, page addresses and word counts hidden; repeats unmarked; saved offline copies with links, images and remote styles removed; app connects to no website.'],
 ['Aids', 'Difference highlighting (on by default; can be switched off): blue text is only in that output, yellow text is in that output and one other; colors mark differences only, not which text is content.'],
 ['Rules', 'Rate alone; do not use AI tools to decide scores; do not look pages up online; do not read project results before finishing; do not discuss items until all have submitted.'],
 ['Consent and data', 'Each rating package contained a study note, to be read first, that explained the task and withdrawal and stated that ratings would be published under a neutral code. The note asked raters to confirm by email before starting; instead, each rater\'s confirmation that they agreed to take part and to be named in the acknowledgments was recorded after that rater had finished rating, so consent was not recorded in writing before rating. No rater withdrew. All five stated, by email or text message, that they used no AI tool while rating. Raters were recruited from the author\'s professional network and were unpaid volunteers (author record). Raters were asked about their background and experience; the answers (missing for two raters) are kept private. The practice notes were written by the author, who knew which tool produced each practice output. A self-chosen rater name was replaced by a neutral code before publication; published files hold no start or end times.'],
 ['Sources', '`evaluators/HANDOUT.md`, `evaluators/ABOUT_THIS_STUDY.txt`, app `evaluators/static/index.html` (version 1.1.0), `PROTOCOL.md` amendments of 2 and 3 November.'],
])
open(OUT, 'w').write('\n'.join(L) + '\n')
print('lines', len(L))
