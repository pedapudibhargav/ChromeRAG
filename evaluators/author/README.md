# Author tools (build + analyse)

These scripts are for the person who prepares the blind bundle and analyses returned ratings. They may import `chromerag` and `poc` and need the project’s usual Python environment. Raters never run these.

## Build a bundle

Prepare a pages list JSON (array of objects):

```json
[
  {"id": "page1", "url": "https://example.com/a", "html": "path/to/a.html", "page_type": "article"}
]
```

Optional calibration pages use the same shape.

```bash
python -m evaluators.author.build_bundle \
  --pages pages.json \
  --calibration cal_pages.json \
  --tools chromerag trafilatura readability \
  --seed 20261002 \
  --repeats 5 \
  --out evaluators/bundle/bundle.json \
  --out-key "$HOME/private/rating_key.json"
```

- Writes **bundle.json** (no tool names) for raters.
- Writes **key.json** mapping each item’s labels (A, B, …) to tools. **Never** put `key.json` under `evaluators/bundle/` or `evaluators/results/`; the builder refuses those paths.
- Skips pages where any tool output is under 15 words (logged).
- `--repeats` duplicates each page under new item ids so raters do not notice repeats.
- All tool outputs are normalised the same way (front matter, link targets, images, emphasis removed).

Send `bundle.json` privately. Keep `key.json` on your machine only.

## Analyse results

Collect each rater’s `evaluators/results/<rater>_<bundle_id>.json` into a folder, then:

```bash
python -m evaluators.author.analyze \
  --results path/to/results_dir \
  --bundle path/to/bundle.json \
  --key path/to/key.json \
  --out report.json
```

Optional `--judges path/to/judge.json` compares majority human pairwise verdicts with an LM-judge file that has `judgements[]` entries with `pid` and `winner` (`ours` / `traf` / `tie`), reporting Cohen’s kappa for chromerag vs trafilatura.

The report includes, per tool pair (focus: chromerag vs trafilatura): per-rater and majority net preference with page-level bootstrap 95% CI, Krippendorff’s alpha, repeat consistency, mean content/chrome scores, time per item, and exclusions. Calibration items are excluded.
