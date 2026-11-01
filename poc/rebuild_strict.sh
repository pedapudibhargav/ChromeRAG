#!/usr/bin/env bash
# Rebuild strict-dev LBC artifacts and evaluation JSON from WCXB in data/wcxb/.
# Prerequisite: pip install -e ".[train,baselines,dev]" and PYTHONPATH=src:.
#
# strict_split loads WCXB test URLs only to collect registrable domains to exclude
# from the train id set (domain leakage / near-dup gates). It never scores test pages.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-python3}"
export PYTHONPATH="${PYTHONPATH:-src:.}"
export PYTHONWARNINGS="${PYTHONWARNINGS:-ignore}"
REBUILD_JOBS="${REBUILD_JOBS:-6}"
LOG="${REBUILD_LOG:-data/outputs/rebuild_strict.log}"
mkdir -p data/outputs/lbc data/outputs/ablation_cv

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" | tee -a "$LOG"; }

log "=== 1 strict train ids (optional refresh; preserves manifest provenance fields) ==="
"$PY" -m poc.strict_split --write 2>&1 | tee -a "$LOG"

log "=== 2 feature table ==="
"$PY" -m poc.lbc_data --split dev --jobs "$REBUILD_JOBS" 2>&1 | tee -a "$LOG"

log "=== 3 five fold models (site-grouped CV) ==="
rm -rf data/outputs/lbc/cv_stack data/outputs/ablation_cv
for k in 0 1 2 3 4; do
  log "train fold $k"
  "$PY" -m poc.train_lbc --data data/outputs/lbc/lbc_strict.npz --holdout-fold "$k" \
    --out-dir "data/outputs/lbc/cv/fold_$k" 2>&1 | tee -a "$LOG"
done

log "=== 4 full model (fit-all) + ship assets before manifest/golden ==="
rm -rf data/outputs/lbc/verify_a data/outputs/lbc/verify_b
"$PY" -m poc.train_lbc --data data/outputs/lbc/lbc_strict.npz --fit-all --out-dir data/outputs/lbc/verify_a 2>&1 | tee -a "$LOG"
"$PY" -m poc.train_lbc --data data/outputs/lbc/lbc_strict.npz --fit-all --out-dir data/outputs/lbc/verify_b 2>&1 | tee -a "$LOG"
cmp data/outputs/lbc/verify_a/lbc_stage1.npz data/outputs/lbc/verify_b/lbc_stage1.npz
mkdir -p src/chromerag/assets
cp -f data/outputs/lbc/verify_a/lbc_stage1.npz src/chromerag/assets/lbc_stage1.npz
log "copied verify_a/lbc_stage1.npz -> src/chromerag/assets/lbc_stage1.npz"
"$PY" -m poc.update_strict_manifest --verify-npz data/outputs/lbc/verify_a/lbc_stage1.npz 2>&1 | tee -a "$LOG"

log "=== 5 strict dev CV scores ==="
"$PY" -m poc.run_strict_dev_cv --jobs "$REBUILD_JOBS" 2>&1 | tee -a "$LOG"
"$PY" - <<'PY' | tee -a "$LOG"
import json
from pathlib import Path
allow = set(json.loads(Path("poc/wcxb_strict_train_ids.json").read_text()))
rows = json.loads(Path("evaluations/2026-10-v0.1.3/strict_dev_cv.json").read_text())
ids = {r["id"] for r in rows}
assert ids <= allow and allow <= ids, (ids - allow, allow - ids)
print("strict_dev_cv id check OK", len(rows))
PY

log "=== 6 ablation CV ==="
"$PY" -m poc.ablation_cv --no-cache --train-stack --jobs "$REBUILD_JOBS" 2>&1 | tee -a "$LOG"

log "=== 7 golden fixtures ==="
"$PY" -m poc.golden --write 2>&1 | tee -a "$LOG"

log "=== DONE ==="
