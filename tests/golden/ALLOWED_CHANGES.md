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

14. **Loose text** — runs of text between block elements are wrapped in `<p>` so they reach the classifier and the output.
15. **Confidence** — `diagnostics["lbc"]` reports the model's expected precision, recall and F1 for the page.

16. **Corpus refresh** — `awesome-python` and `awesome-selfhosted` in `data/raw` were re-fetched by the 2026-10-02 corpus run (live pages change); their hashes changed, the code did not.

# Allowed golden hash changes (v0.1.4 output quality)

17. **Code blocks** keep their line breaks; **lists** keep ordered numbering (`start`) and nesting.
18. **Page title** — the page's own `h1` is kept by the block classifier; a section heading above kept content is kept (`lbc_rescue_headings`), and the lead paragraph under the title is kept (`lbc_rescue_lead`).
19. **Shallow-div writer** — a `div` that wraps custom elements but holds blocks below no longer collapses into one text blob.
20. **`<header>` of an `<article>`** that holds the page `h1` is content, not chrome.
21. **Tables** render as GitHub pipe tables when the grid is rectangular (`table_format="markdown"`); other tables keep the key-value form.
22. **Documentation-framework rules** (table of contents, feedback and pagination widgets of Docusaurus, MkDocs, Starlight, VitePress, Mintlify, Cloudflare, Grafana, DigitalOcean docs) in `rules/docs_generators.yaml`.
23. **Generic chrome** (`generic_chrome.py`) drops in-page tables of contents, previous/next pagers, article comment sections, related-post blocks and unrendered template placeholders before the classifier sees them.
24. **Residual chrome** — standalone call-to-action blocks, share strips, newsletter blocks, post-article author boxes, back-to-top links and language switchers are dropped by `generic_chrome.py` (flags `chrome_drop_cta`, `chrome_drop_share`, `chrome_drop_newsletter`, `chrome_drop_author_bio`, `chrome_drop_nav_misc`).
25. **Tail trim and attribute residue** — footer-zone and short link-dense tails after the last substantive block, and blocks that are serialised attributes or repeated words, are dropped (`chrome_trim_tail`, `chrome_drop_attr_junk`).
26. **Trafilatura-inspired rules** — 16 discard rules adapted from Trafilatura's patterns (`rules/trafilatura_inspired.yaml`) and two density passes (`trafilatura_link_blocks`, `trafilatura_micro`) remove share bars, teasers, comment forms, newsletter and sidebar widgets, bylines, pagination, footers and tag clouds.
