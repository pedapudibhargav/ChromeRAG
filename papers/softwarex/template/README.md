# SoftwareX manuscript files

**[`ChromeRAG_SoftwareX_OSP.docx`](../ChromeRAG_SoftwareX_OSP.docx)** is generated from the official
Elsevier SoftwareX Original Software Publication template (Version 6, March 2026) and
[`../SOFTWAREX_EXPANDED.md`](../SOFTWAREX_EXPANDED.md).

```bash
# Template: https://legacyfileshare.elsevier.com/promis_misc/softwarex-osp-template.docx
python -m poc.run_corpus_comparison --no-fetch      # benchmark numbers
python scripts/generate_softwarex_figures.py        # figures (Playwright or local Chrome)
SOFTWAREX_TEMPLATE=path/to/softwarex-osp-template.docx python scripts/fill_softwarex_docx.py
python scripts/embed_softwarex_figures.py
```

Journal limits: ≤ 4,000 words (abstract + body + captions), ≤ 6 figures, abstract ≈ 100 words,
≤ 6 keywords, public GitHub repository with `README.md` and a licence file.
