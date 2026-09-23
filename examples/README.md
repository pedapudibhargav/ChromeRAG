# Examples

`site/` holds four small synthetic pages from a fictional documentation site
(`docs.example.com`). They share the same header navigation, cookie banner,
sales call-to-action and footer — the kind of site-template chrome ChromeRAG
removes. Each page has a `*.meta.json` sidecar with its URL so `chromerag learn`
can group pages by site.

```bash
chromerag extract examples/site/pricing.html -o out/pricing.md --json-meta
chromerag learn examples/site -o out/site_chrome.json --min-pages 3
chromerag batch examples/site -o out/batch --chrome-model out/site_chrome.json
```

The pages are hand-written for this repository; no third-party content is included.
