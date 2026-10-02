# Allowed golden hash changes (WP2)

1. **Per-call config** — multi-page ChromeRAG instances no longer leak inferred page type across calls.
2. **Hidden nodes** — drop `hidden`, `display:none`, guarded `aria-hidden` subtrees before scoring.
3. **Skip links** — remove `#` skip-navigation anchors and empty wrappers.
4. **Content-root ladder** — prefer validated `main` / `article` / content-class candidates over blind `main` lookup.
5. **Collapse fallback** — retry with `<body>` root and coverage thresholds when output is too thin.

Regenerated after reviewing sample diffs on dev corpus pages.

# Allowed golden hash changes (WP3 and review)

6. **Rule index** — YAML rules (consent managers, share/related blocks, Docusaurus footer) drop matching subtrees before scoring.
7. **Crash fix** — pages that used to raise in skip-link removal now produce output.
8. **Config switches** — page-type inference and the coverage fallback keep caller switches such as `enable_rules`.

Performance work (single-pass statistics, cached densities) is output-identical: with rules disabled, old and new code give the same hashes on 631 pages.

# Allowed golden hash changes (learned block classifier)

9. **Learned block classifier** replaces the density/DVDF block filter. Blocks are scored by gradient-boosted trees (`assets/lbc_stage1.npz`, trained on WCXB dev).
10. **Link targets** are no longer written by default (`include_links`).
11. **Markdown order** follows the document (depth first); it used to be breadth first.
12. **Layout tables** are unwrapped; nested layout tables no longer repeat their text.
13. **Wrappers** — a page-wide `<form>`, unclosed `<button>` or large `<noscript>` is unwrapped instead of dropped; content after a stray `</html>` is adopted into `<body>`; large hidden blocks of running text are kept.
