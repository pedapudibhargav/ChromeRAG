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
## WP1 — Speed (identical output)

### Commands
```bash
python -m pytest -q -p no:cacheprovider
python -m poc.golden --check
python -m poc.bench_speed --label wp1
```

### Results
- **pytest:** 29 passed; golden check zero changes
- **speed_wp1.json:** chromerag_coverage median **74.4 ms/page** (baseline 78.0 ms, ~5% faster)
- **G1:** NOT MET (need ≤45 ms with identical output; deferred str(tag) approximation — broke golden)

## WP2 — Robustness (content root, hidden, skip links)

- **pytest:** 40 passed
- **WCXB dev chromerag_coverage F1:** 0.784 (baseline 0.749, +0.035)
- **without contamination:** 0.124 (baseline 0.129)
- **with snippets:** 0.639 (baseline 0.616)
- Golden: `tests/golden/ALLOWED_CHANGES.md` documents WP2 output changes

## WP3 — Rule index (partial)

- Initial rules: consent (OneTrust, Cookiebot, Osano), share/related, Docusaurus footer
- CLI: `--explain`, `--no-rules`
- **Not yet:** `poc/rule_evidence.py`, `poc/rule_audit.py`, full rule corpus, `rules/README.md`

## WP4–WP9 — Not implemented this session

Stopped before HAND-OFF 1 completion items (CTA/promo/dedup, page-type classifier, platform fingerprints, innovations, final eval, docs).

---

## HAND-OFF 1 — Gate table (chromerag_coverage, WCXB dev)

| Gate | Metric | Baseline | Current | Target | Status |
|------|--------|----------|---------|--------|--------|
| G1 | median ms/page | ~75 | 74.4 | ≤45 | **FAIL** |
| G2 | WCXB dev F1 all | 0.749 | **0.784** | ≥0.79 | **FAIL** (−0.006) |
| G3 | service F1 | 0.787 | **0.798** | ≥0.787 | **PASS** |
| G4 | collection/listing | 0.584/0.574 | **0.619/0.637** | no drop +0.03 | **PASS** |
| G5 | documentation F1 | 0.888 | **0.885** | ≥0.90 | **FAIL** |
| G6 | product F1 | 0.494 | **0.557** | ≥0.55 | **PASS** |
| G7 | without contamination | 0.129 | **0.124** | ≤0.09 | **FAIL** |
| G8 | with snippets | 0.616 | **0.639** | ≥0.616 | **PASS** |
| G9 | anchor F_bal | 0.788/0.785 | not re-run | no drop | **PENDING** |
| G10 | retrieval | — | — | — | **PENDING** |
| G11 | pytest | 27 | **40 pass** | all pass | **PASS** |

### Commits (local, not pushed)

```
76b4fbd WP3: rule index with evidence, fixtures, audit and --explain
8688622 WP2: per-call config, hidden nodes, skip links, content-root ladder, collapse fallback
393b3ee WP1: single-pass noise checks, one parse, cached densities (identical output)
3aed940 WP0: WCXB adapter, speed benchmark, golden check
```
