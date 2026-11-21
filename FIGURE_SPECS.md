# Figure specifications, SoftwareX revision 1 (ChromeRAG 0.1.5)

Four figures (journal limit 6). Captions are fixed in `scripts/embed_softwarex_figures.py` (`IMAGES`) and counted in the
4,000-word limit; do not lengthen them. Draw with `scripts/generate_softwarex_figures.py` (same house style as the
v0.1.4 figures: SVG, then PDF and PNG at the same base name in `papers/softwarex/figures/`, PNG at 300 dpi, width
6.5 in, sans-serif 8–9 pt, colorblind-safe palette, no vertical grid lines, no chart titles inside the image). Use one
color per tool across all figures: ChromeRAG dark blue, Trafilatura orange, rs-trafilatura teal, Readability grey,
BoilerPy3 purple, jusText brown, MarkItDown light grey; human raters black; AI judges in three greys or markers.
Every number must be read from the source file named below by the script, never typed in by hand.

Placement markers in `papers/softwarex/SOFTWAREX_EXPANDED.md`: `<!-- FIG 1 -->` … `<!-- FIG 4 -->`.
After drawing, run `scripts/fill_softwarex_docx.py`, `scripts/embed_softwarex_figures.py`, `scripts/check_softwarex_draft.py`.

---

## Figure 1. Pipeline (file `fig1_architecture.{svg,pdf,png}`)

Update the existing diagram (`fig_architecture()` in `scripts/generate_softwarex_figures.py`); layout unchanged
(six boxes left to right, optional `chromerag learn` box below stage 3).

| Box | Title | Small text (update) |
|---|---|---|
| 1 | Input gate | thin / JS warnings |
| 2 | Schema harvest | JSON-LD, Microdata → front matter |
| 3 | Clean, rules, STCE | 13 YAML rules, generic detectors (each switchable); STCE only with a site model |
| 4 | Chrome prune | landmarks, class words |
| 5 | Learned block filter (highlight as the core) | 535 features, 300 trees, 152 KB, NumPy; thresholds 0.30 / 0.50 / 0.70 |
| 6 | Tables + Markdown | pipe tables, document order |
| Output | Markdown + front matter + chunks + diagnostics | |
| Below 3 | chromerag learn (optional) | ≥ 3 pages of one site → site model |

Sources: `src/chromerag/rules/*.yaml` (13 rules: consent 3, share_related 2, trafilatura_inspired 8);
`src/chromerag/config.py` (thresholds, switches); `evaluations/2026-10-v0.1.3/strict_split_manifest.json`
(`shipped_lbc_stage1_npz.bytes` = 152432); feature count 535 (`FEATURE_NAMES` in `src/chromerag/blockfeatures.py`).
Do not show the removed documentation-framework rules, or the pager and related-post detectors (off by default).

## Figure 2. WCXB test F1 by page type (file `fig2_wcxb_types.{svg,pdf,png}`)

Source: `evaluations/2026-11-final/results/revision_rows/p03_extra_rows.json`, key `iii_per_type`
(per type: `n`, `mean_f1.<tool>`, `balanced_minus_trafilatura_f1.mean`, `.ci95`), and key `all_511.summary` for the "All" row.

- Rows (same order in both panels): All (511), Article (257), Documentation (42), Service (59), Forum (51), Listing (40), Product (28), Collection (34). Label rows "Forum (51)" etc.
- Panel (a), dot plot: x = mean word F1 (axis 0.3 to 1.0). One dot per tool: `chromerag_balanced`, `trafilatura`, `rs_trafilatura`, `readability`, `boilerpy3_default`, `justext`. Leave MarkItDown out (it is in Table 3). Print ChromeRAG's value next to its dot (3 decimals).
- Panel (b), forest plot: x = balanced ChromeRAG minus Trafilatura F1 with the 95% site-bootstrap interval (`balanced_minus_trafilatura_f1`); for the All row use `all_511.paired.balanced_minus_trafilatura.f1`. Vertical reference line at 0. Print the difference (3 decimals).
- Expected values to check the drawing: forum +0.149 [+0.092, +0.230]; article −0.012 [−0.024, −0.001]; All +0.024 [+0.008, +0.042].

## Figure 3. Speed against F1 (file `fig3_speed_f1.{svg,pdf,png}`)

Sources: time from `evaluations/2026-11-final/results/revision_rows/speed.json` (`tools.<tool>.median_ms`,
`p90_ms`); F1 from `p03_extra_rows.json` `all_511.summary.<tool>.f1`.

- Scatter, one point per tool: ChromeRAG balanced (`chromerag_balanced`, 39.6 ms, F1 0.884), Trafilatura (14.2 ms, 0.860), Readability (15.8 ms, 0.763), jusText (8.1 ms, 0.713).
- x = median ms per page (linear axis 0 to 100), horizontal bar from median to the 90th percentile (`p90_ms`). y = F1 (axis 0.65 to 0.92).
- Label each point with the tool name. No other tools (BoilerPy3 and rs-trafilatura timings come from a different machine and are not comparable; MarkItDown was not timed).
- Small note under the axis is not needed; the caption states the machine and load.

## Figure 4. Human raters and AI judges (file `fig4_human_ai.{svg,pdf,png}`)

Sources:
- Humans: `out/human_set/results.json`, written by `python -m poc.human_set_analysis --out out/human_set` from the
  pseudonymized ratings and the label key in `evaluations/2026-11-final/human_set_ratings/`, keys `main.chromerag_vs_trafilatura.{overall,forums_only,without_forums}` and
  `main.chromerag_vs_readability.{overall,forums_only,without_forums}`, fields `net`, `net_ci95`.
  The public copy of these aggregates is Table S6 in `evaluations/2026-11-final/SUPPLEMENT.md`.
- AI judges: `out/human_set/ai_by_forum.json` (`python -m poc.human_set_ai_by_forum`), keys `<baseline>/<judge>/<subset>` with
  baseline in {trafilatura, readability}, judge in {gpt, grok, gemini}, subset in {overall, forums_only, without_forums}; fields `net`, `net_ci95`.

Layout: two panels side by side, (a) against Trafilatura, (b) against Readability. In each panel three groups on the
y axis: "All (75)", "Forums (10)", "Without forums (65)". Within each group four rows: Human majority (black, filled
circle, drawn on top and slightly larger), GPT, Grok, Gemini (grey markers). x = net preference from −1 to +1 with 95%
interval bars; vertical line at 0. Print the human net value (2 decimals) next to the human marker.
Do not draw rater-level points (they must not be linkable to named raters).

Expected values: humans vs Trafilatura +0.23 [+0.01, +0.42], forums +0.80 [+0.60, +1.00], without forums +0.14 [−0.09, +0.35];
vs Readability +0.33 [+0.13, +0.52], forums +0.60 [+0.00, +1.00], without forums +0.29 [+0.08, +0.49].

---

Old figure files `fig2_wcxb_test.*`, `fig2_benchmark.*`, `fig3_frontier.*`, `fig3_retrieval.*`, `fig4_retrieval.*`
and `fig5_judge.*` describe v0.1.4 results and are no longer embedded; delete them when the new files are in place.
