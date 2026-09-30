# ChromeRAG 0.1.3 work log

## WP0 — Evaluation harness, speed benchmark, golden check

### Commands
```bash
export PYTHONPATH=src:. PYTHONWARNINGS=ignore
python -m pytest -q -p no:cacheprovider
python -m poc.golden --write
python -m poc.bench_speed --label baseline
python -m poc.run_wcxb_eval --split dev --out evaluations/2026-10-v0.1.3/wcxb_dev_wp0.json \
  --compare evaluations/2026-09-v0.1.2-baseline/wcxb_dev_v012_per_page.json
```

### Results
- **pytest:** 28 passed (27 existing + test_golden)
- **speed_baseline.json:** chromerag_coverage median 78.0 ms/page (baseline target ~75)
- **WCXB dev chromerag_coverage F1:** 0.754 (baseline 0.749, delta +0.0006 ALL — within ±0.002)
- **Golden:** manifest.json written (300 corpus pages × 3 modes + 4 fixtures)

### Gates (WP0 baseline)
| Gate | Metric | Value | Target | Status |
|------|--------|------:|--------|--------|
| G1 | median ms/page | 78.0 | ≤45 | FAIL |
| G2 | WCXB dev F1 | 0.754 | ≥0.79 | FAIL |
| G11 | pytest | 28 pass | all pass | PASS |
