# Contributing to ChromeRAG

Thanks for helping. Bug reports with a small HTML sample are the most useful contribution.

## Set up

```bash
git clone https://github.com/pedapudibhargav/ChromeRAG.git && cd ChromeRAG
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,baselines]"
pytest -q
```

## Reporting a page that extracts badly

Open an issue with: the URL (or a saved HTML file), the Markdown you got, what you expected, and the
priority you used. Please do not paste pages that contain personal data.

## Changing behaviour

* Add or update a test in `tests/`. Behaviour changes need a line in `tests/golden/ALLOWED_CHANGES.md`
  and a regenerated manifest (`python -m poc.golden --write`, needs the corpus in `data/raw/`).
* Run `ruff check src tests` and `pytest -q`.
* A removal rule (`src/chromerag/rules/*.yaml`) needs `evidence` (a vendor document, or at least three
  sites where the markup occurs) and a fixture under `tests/rules/` marking `data-chrome` and `data-keep`.
* A change to the learned filter needs cross-validated numbers (`poc/wcxb_cv_report.py`), never numbers
  from pages the model was trained on.

## Retraining the model

See "Learned block filter" in the README. Keep the test splits of WCXB and the held-out landing
companies out of training and tuning.

## Conduct

Be kind and specific. Disagree about code, not people.
