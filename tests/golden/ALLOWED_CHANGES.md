# Allowed golden hash changes (WP2)

1. **Per-call config** — multi-page ChromeRAG instances no longer leak inferred page type across calls.
2. **Hidden nodes** — drop `hidden`, `display:none`, guarded `aria-hidden` subtrees before scoring.
3. **Skip links** — remove `#` skip-navigation anchors and empty wrappers.
4. **Content-root ladder** — prefer validated `main` / `article` / content-class candidates over blind `main` lookup.
5. **Collapse fallback** — retry with `<body>` root and coverage thresholds when output is too thin.

Regenerated after reviewing sample diffs on dev corpus pages.
