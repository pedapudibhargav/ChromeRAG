# ChromeRAG site

The public site is a single page, [`index.html`](index.html). It has no build step of its own:
it loads the published results from [`data/`](data/) at runtime, so the numbers on the page are
always the ones in the repository.

| File in `data/` | Written by |
|---|---|
| `corpus_comparison_report.json`, `corpus_comparison_summary.md` | `python -m poc.run_corpus_comparison` |
| `leaderboard.json` | `python -m poc.export_site_results` (compact copy of the report summary) |
| `corpus_revalidation.json` | `python scripts/revalidate_corpus.py` |
| `retrieval_eval_report.json` | `python -m poc.run_retrieval_eval` |
| `stce_eval_report.json`, `stce_eval_stce_crawl_report.json` | `python -m poc.run_stce_eval [--raw data/stce_crawl]` |
| `stce_summary.json` | `python -m poc.export_site_results` (the STCE reports without per-page rows; what the page loads) |
| `test_report.json` | `scripts/build_docs.sh` (pytest) |

## Publishing

`.github/workflows/pages.yml` runs the tests, then `scripts/build_docs.sh`, which copies
`index.html` and the JSON files it loads into `_site/`, and publishes `_site/` to the `gh-pages` branch on
every push to `main`. In the repository settings, set **Pages → Source: Deploy from a branch →
Branch: `gh-pages` / (root)**. The site is served at https://pedapudibhargav.github.io/ChromeRAG/.

To preview locally:

```bash
bash scripts/build_docs.sh
python -m http.server -d _site 8000
```

Links inside the page are relative (`data/...`), so it works under the `/ChromeRAG/` project path.
