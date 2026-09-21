# ChromeRAG site (GitHub Pages)

This folder is a **static** site. Enable GitHub Pages with:

- Source: Deploy from a branch  
- Folder: `/docs`

## Routing notes

GitHub project pages serve under `https://<user>.github.io/<repo>/`. Absolute paths like `/assets/...` break. This site uses **relative** links only (`./assets/...`, `./metrics.html`).

There is **no** client-side History API router — each page is a real HTML file so refresh and deep links work.

## Updating results

```bash
python -m poc.run_corpus_comparison
python -m poc.export_site_results
```

That writes `docs/data/leaderboard.json` for `results.html`.
