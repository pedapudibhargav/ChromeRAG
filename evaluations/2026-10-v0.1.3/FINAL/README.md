# Final evaluation artifacts (v0.1.3 campaign)

Frozen outputs used by `poc/export_final_results.py`, the GitHub Pages site, and the SoftwareX manuscript.

## WCXB word-level F1

| File | Description |
|------|-------------|
| `wcxb_test.json` | Full WCXB test split (511 pages), all tools, per-page scores. |
| `wcxb_test_deduplicated.json` | Clean test split (372 pages): test pages whose HTML also appears in development are removed. Primary held-out result. |

## Landing-page anchor benchmark

| File | Description |
|------|-------------|
| `landing_comparison_heldout_report.json` | Per-page anchor metrics on held-out landing URLs. |
| `landing_comparison_heldout_summary.md` | Human-readable summary of held-out landing comparison. |
| `landing_comparison_fresh_report.json` | Per-page anchor metrics on freshly crawled landing URLs. |
| `landing_comparison_fresh_summary.md` | Human-readable summary of fresh landing comparison. |
| `landing_unseen_domain.json` | Landing results restricted to registrable domains not present in WCXB development. |

## LLM-as-judge (OpenAI GPT)

| File | Description |
|------|-------------|
| `llm_judge_final.json` | Pairwise preferences on the documentation corpus benchmark. |
| `llm_judge_wcxb_test.json` | Judge sample on all 511 WCXB test pages. |
| `llm_judge_wcxb_test_deduplicated.json` | Judge sample on the 372-page clean WCXB test split. |

## LLM-as-judge (Claude, final v0.1.4 runs)

| File | Description |
|------|-------------|
| `claude_judge_v014d_final2.json` | Claude judge on the extra-corpus final2 page set. |
| `claude_judge_v014d_wcxb_clean.json` | Claude judge on the clean WCXB test split. |

## LLM-as-judge (GPT, v0.1.4 runs)

| File | Description |
|------|-------------|
| `gpt_judge_v014c_final2.json` | GPT judge on the extra-corpus final2 page set. |
| `gpt_judge_v014c_final2_readability.json` | GPT judge on final2 with Readability in the comparison set. |
| `gpt_judge_v014c_docs_final.json` | GPT judge on documentation-corpus pages. |
| `gpt_judge_v014c_products_final.json` | GPT judge on product pages. |
| `gpt_judge_v014c_wcxb_clean.json` | GPT judge on the clean WCXB test split. |
| `gpt_judge_v014d_final2.json` | GPT judge rerun on final2 (v014d prompt/settings). |

## LLM-as-judge (Gemini)

| File | Description |
|------|-------------|
| `gemini_judge_v014d_final2.json` | Gemini judge on the extra-corpus final2 page set. |

## Mixed-baseline Claude judge runs (kept for ablation)

| File | Description |
|------|-------------|
| `claude_judge_v014b_mix_markitdown.json` | Claude judge with MarkItDown mixed into the comparison pool. |
| `claude_judge_v014b_mix_readability.json` | Claude judge with Readability mixed into the comparison pool. |

## Retrieval and context

| File | Description |
|------|-------------|
| `fresh_retrieval_eval_report.json` | BM25 and dense retrieval on freshly crawled pages. |
| `heading_context_retrieval.json` | Heading-context retrieval experiment on benchmark pages. |

## Cost tracking

| File | Description |
|------|-------------|
| `openai_spend.json` | Token and cost totals for OpenAI judge API calls. |

## Superseded intermediate judge runs (deleted)

The following were exploratory Claude judge batches superseded by the `v014d` files above:

- `claude_judge_v014_*.json`
- `claude_judge_v014b_*.json` (except the `mix_*` ablations listed above)
- `claude_judge_v014c_*.json`
- `claude_judge_wcxb_clean.json`
