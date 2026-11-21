#!/usr/bin/env bash
# Follow README.md on a clean machine: install the released package from PyPI into a fresh
# virtual environment and run every quick-start command against the repository's examples.
# Expectations match the 0.1.5 output on examples/site/ (checked locally against the frozen code).
# Usage (from the repository root): bash scripts/readme_smoke.sh [version]
#   SMOKE_LOCAL=1 bash scripts/readme_smoke.sh   # install the working tree instead of PyPI (no network for the
#                                                # package itself; pip may still fetch dependencies)
set -euo pipefail
VERSION="${1:-}"
PYTHON="${PYTHON:-python3}"
step() { printf '\n==> %s\n' "$*"; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
"$PYTHON" -m venv "$WORK/venv"
BIN="$WORK/venv/bin"
[[ -d "$WORK/venv/Scripts" ]] && BIN="$WORK/venv/Scripts"

if [[ -n "${SMOKE_LOCAL:-}" ]]; then
  step "pip install . (working tree, fresh venv)"
  "$BIN/python" -m pip install -q .
else
  step "pip install chromerag${VERSION:+==$VERSION} (from PyPI, fresh venv)"
  "$BIN/python" -m pip install -q --upgrade pip
  "$BIN/python" -m pip install -q "chromerag${VERSION:+==$VERSION}"
fi
"$BIN/chromerag" --version
OUT="$WORK/out"

step "Quick start 1: one page"
"$BIN/chromerag" extract examples/site/pricing.html -o "$OUT/pricing.md" --priority balanced --json-meta > /dev/null
grep -q "title: Plans and pricing" "$OUT/pricing.md"
grep -q "type: TechArticle" "$OUT/pricing.md"
grep -q "^# Plans and pricing" "$OUT/pricing.md"
grep -q "| Team | 20,000 | 49 |" "$OUT/pricing.md"
for chrome in "Widget Summit" "Accept all cookies" "Talk to sales"; do
  if grep -q "$chrome" "$OUT/pricing.md"; then echo "chrome left in single-page output: $chrome"; exit 1; fi
done

step "Quick start 2: chunks as JSON lines"
"$BIN/chromerag" extract examples/site/pricing.html --chunks > "$OUT/chunks.jsonl"
"$BIN/python" - "$OUT/chunks.jsonl" <<'PY2'
import json, sys
rows = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8") if line.strip()]
assert rows and rows[0]["heading_path"] == ["Plans and pricing", "Reference table"], rows
assert rows[0]["embed_text"].startswith("Plans and pricing > Reference table\n"), rows[0]["embed_text"][:80]
PY2

step "Quick start 3: learn the site model, then batch with and without it"
"$BIN/chromerag" learn examples/site -o "$OUT/site_chrome.json" --min-pages 3 > "$OUT/learn.json" 2>&1
grep -q '"docs.example.com/docs": 6' "$OUT/learn.json"
"$BIN/chromerag" batch examples/site -o "$OUT/batch" --chrome-model "$OUT/site_chrome.json"
"$BIN/chromerag" batch examples/site -o "$OUT/batch_plain"
test -f "$OUT/batch/batch_summary.json"
grep -q "| Team | 20,000 | 49 |" "$OUT/batch/pricing/chromerag.md"
for page in configuration getting-started pricing troubleshooting; do
  if grep -q "Widget Summit" "$OUT/batch/$page/chromerag.md"; then echo "repeated event paragraph left in $page"; exit 1; fi
  # 0.1.5: the learned filter already removes the repeated paragraph, so the site model changes nothing here
  cmp -s "$OUT/batch/$page/chromerag.md" "$OUT/batch_plain/$page/chromerag.md" \
    || { echo "$page differs with and without the site model"; exit 1; }
done

step "Thin / JavaScript-shell input"
echo '<html><body><div id="root"></div><script src="app.js"></script></body></html>' > "$WORK/spa.html"
"$BIN/chromerag" extract "$WORK/spa.html" -o "$OUT/spa.md"
set +e
"$BIN/chromerag" extract "$WORK/spa.html" -o "$OUT/spa.md" --fail-on-thin
rc=$?
set -e
[[ "$rc" -eq 3 ]] || { echo "--fail-on-thin exited with $rc, expected 3"; exit 1; }

step "Python API"
"$BIN/python" - <<'PY'
from chromerag import ChromeRAG, ContentPriority, PipelineConfig

html = open("examples/site/pricing.html", encoding="utf-8").read()
result = ChromeRAG(config=PipelineConfig.from_priority(ContentPriority.BALANCED)).extract(
    html, url="https://docs.example.com/docs/pricing"
)
assert result.front_matter["title"] == "Plans and pricing", result.front_matter
assert "| Team | 20,000 | 49 |" in result.markdown
print("front_matter:", result.front_matter)
PY

printf '\nREADME smoke test passed for chromerag %s\n' "$("$BIN/chromerag" --version)"
