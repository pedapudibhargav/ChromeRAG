# AI judges on the human rating set

GPT, Grok and Gemini judged the same 75 pages and the same three outputs as the human raters, with the same
rubric, before any human rating was returned (163 judgments each: ChromeRAG balanced against Trafilatura and
against Readability, plus the five pages later swapped out, which the summaries leave out).

- Jobs and prompt: `poc/final_page_judge.py --bundle ... --key ...` builds the jobs; the system prompt is
  `poc/eval_rubric.py` (`page_judge_prompt`) and is also stored verbatim in `gpt.json` (`system_prompt`).
  A/B order is random per page with the stored seed (20261101), and tool names are hidden.
- GPT (`gpt.json`): `gpt-5.6-luna` through the OpenAI API, run by `poc/final_page_judge.py`.
- Grok (`grok.json`) and Gemini (`gemini.json`): the same jobs and the same prompt were given to each model
  through a third-party agent tool. Its sampling settings (temperature, reasoning effort) could not be
  controlled or recorded beyond what the `model` and `access` fields state.
- `*.progress.jsonl`: one line per judgment as it was returned, including the swapped-out pages.

The analysis (`poc/human_set_analysis.py`) compares each judge with the human majority (Cohen's kappa) and
reports each judge's net preference with the same site bootstrap as the human result.
