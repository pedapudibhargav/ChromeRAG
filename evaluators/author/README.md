# Author tools (build + analyse)

These scripts are for the person who prepares the blind bundle and analyses returned ratings. They may import project libraries and need the project’s usual Python environment. Raters never run these.

## Build a bundle from a prepared folder

Corpus layout:

```text
corpus/
  pages.json          # [{id, url, page_type, html}, ...]
  html/               # page HTML files
  outputs/<tool>/<id>.md
```

Default sample: **75** stratified main pages, **5** repeat items, **5** calibration pages, **three** blinded outputs. Same folder + seed → same bundle.

```bash
python -m evaluators.author.build_bundle \
  --from-dir path/to/corpus \
  --tools chromerag trafilatura readability \
  --seed 20261002 \
  --n-pages 75 \
  --n-repeats 5 \
  --n-calibration 5 \
  --raters alice bob carol \
  --out evaluators/bundle/bundle.json \
  --out-key path/outside/evaluators/key.json \
  --out-orders path/outside/evaluators/orders.json \
  --pages-out data/human_eval/html
```

- Writes **bundle.json** (no tool names) for raters.
- Writes **key.json** (label → tool) and **orders.json** (per-rater item and label order). Never put either under `evaluators/bundle/` or `evaluators/results/`.
- Sanitised page copies under `--pages-out` stay local (git-ignored); the bundle also embeds HTML so raters need only `bundle.json`.
- Skips pages with a missing or short (<15 word) output.

## Legacy: extract while building

```bash
python -m evaluators.author.build_bundle \
  --pages pages.json \
  --calibration cal_pages.json \
  --tools chromerag trafilatura readability \
  --seed 20261002 \
  --repeats 5 \
  --out evaluators/bundle/bundle.json \
  --out-key path/outside/evaluators/key.json
```

`--repeats` here duplicates **each** page under new item ids (older behaviour).

Send `bundle.json` privately. Keep `key.json` and `orders.json` on your machine only.

## Analyse results

```bash
python -m evaluators.author.analyze \
  --results path/to/results_dir \
  --bundle path/to/bundle.json \
  --key path/to/key.json \
  --out report.json
```

Optional `--judges path/to/judge.json` compares majority human pairwise verdicts with an LM-judge file that has `judgements[]` entries with `pid` and `winner` (`ours` / `traf` / `tie`), reporting Cohen’s kappa for chromerag vs trafilatura.

The report includes, per tool pair (focus: chromerag vs trafilatura): per-rater and majority net preference with page-level bootstrap 95% CI, Krippendorff’s alpha, repeat consistency, mean content/chrome scores, missing-content notes, time per item, and exclusions. Calibration items are excluded.
