# Final evaluation artifacts (v0.1.3 campaign)

Frozen outputs used by `poc/export_final_results.py`, the GitHub Pages site, and the SoftwareX manuscript.
Every file currently in this folder is listed below.

## WCXB word-level F1

| File | Description |
|------|-------------|
| `wcxb_test.json` | Full WCXB test split (511 pages), all tools, per-page scores. |
| `wcxb_test_deduplicated.json` | Clean test split (372 pages): test pages whose HTML also appears in development are removed. Primary held-out result. |
| `wcxb_test_v014_final.json` | Per-page WCXB scores re-run under the 0.1.4 pipeline. |
| `wcxb_clean_f1_v014_final.json` | Aggregate F1 by page type on the clean WCXB test split under the 0.1.4 pipeline. |

## Landing-page anchor benchmark

| File | Description |
|------|-------------|
| `landing_comparison_heldout_report.json` | Per-page anchor metrics on held-out landing URLs. |
| `landing_comparison_heldout_summary.md` | Human-readable summary of held-out landing comparison. |
| `landing_comparison_fresh_report.json` | Per-page anchor metrics on freshly crawled landing URLs. |
| `landing_comparison_fresh_summary.md` | Human-readable summary of fresh landing comparison. |
| `landing_unseen_domain.json` | Landing held-out and fresh results restricted to registrable domains not present in WCXB development. |

## LLM-as-judge (OpenAI GPT, early freeze runs)

| File | Description |
|------|-------------|
| `llm_judge_final.json` | Pairwise preferences on landing held-out + fresh companies (gpt-5.6-luna). |
| `llm_judge_wcxb_test.json` | Judge sample on 105 WCXB test pages (15 per page type). |
| `llm_judge_wcxb_test_deduplicated.json` | Same sample with the 33 duplicate pages excluded (aggregate only). |

## LLM-as-judge (Claude, final v0.1.4 runs)

| File | Description |
|------|-------------|
| `claude_judge_final_final2.json` | Claude judge on the extra-corpus final2 page set (328 pages). |
| `claude_judge_final_wcxb_clean.json` | Claude judge on the clean WCXB test split. |
| `claude_judge_v014d_final2.json` | Claude judge on final2 (v014d round). |
| `claude_judge_v014d_wcxb_clean.json` | Claude judge on the clean WCXB test split (v014d round). |

## LLM-as-judge (GPT, v0.1.4 runs)

| File | Description |
|------|-------------|
| `gpt_judge_v014c_final2.json` | GPT judge on final2 (v014c round). |
| `gpt_judge_v014c_final2_readability.json` | GPT judge on final2 vs Readability (v014c). |
| `gpt_judge_v014c_docs_final.json` | GPT judge on documentation-corpus pages (v014c). |
| `gpt_judge_v014c_products_final.json` | GPT judge on product pages (v014c). |
| `gpt_judge_v014c_wcxb_clean.json` | GPT judge on the clean WCXB test split (v014c). |
| `gpt_judge_v014d_final2.json` | GPT judge on final2 (v014d round; 250-page subset). |
| `gpt_judge_final_final2.json` | GPT judge on final2 (final round). |
| `gpt_judge_final_final2_readability.json` | GPT judge on final2 vs Readability (final round). |
| `gpt_judge_final_docs_final.json` | GPT judge on documentation-corpus pages (final round). |
| `gpt_judge_final_products_final.json` | GPT judge on product pages (final round). |
| `gpt_judge_final_wcxb_clean.json` | GPT judge on the clean WCXB test split (final round). |

## LLM-as-judge (Gemini)

| File | Description |
|------|-------------|
| `gemini_judge_v014d_final2.json` | Gemini judge on final2 (v014d round). |
| `gemini_judge_final_final2.json` | Gemini judge on final2 (final round). |

## Mixed-baseline Claude judge runs (kept for ablation)

| File | Description |
|------|-------------|
| `claude_judge_v014b_mix_markitdown.json` | Claude judge with MarkItDown mixed into the comparison pool. |
| `claude_judge_v014b_mix_readability.json` | Claude judge with Readability mixed into the comparison pool. |

## Retrieval and context

| File | Description |
|------|-------------|
| `fresh_retrieval_eval_report.json` | BM25 and dense retrieval on freshly crawled pages. |
| `heading_context_retrieval.json` | Heading-context retrieval experiment on held-out documentation pages. |

## Cost tracking

| File | Description |
|------|-------------|
| `openai_spend.json` | Token and cost totals for OpenAI judge and embedding API calls. |

## This file

| File | Description |
|------|-------------|
| `README.md` | This inventory. |

## Superseded intermediate judge runs (deleted)

The following were exploratory Claude judge batches superseded by later files. They are no longer in this folder (`result_file = deleted` in the held-out ledger). Git still has some blobs under `4259080^`:

- `claude_judge_v014_docs.json`, `claude_judge_v014_products.json`, `claude_judge_v014b_docs.json` (deleted in commit 4259080)
- `claude_judge_v014_wcxb_clean.json`, `claude_judge_v014b_wcxb_clean.json`, `claude_judge_v014b_docs_final.json`, `claude_judge_v014b_products_final.json`, `claude_judge_wcxb_clean.json` (renamed or replaced in 4259080)
- `claude_judge_v014c_*.json` (listed historically; no path found in git history)
- other `claude_judge_v014b_*.json` except the `mix_*` ablations kept above
