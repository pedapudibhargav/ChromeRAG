#!/usr/bin/env bash
# Follow README.md on a clean machine: install the released package from PyPI into a fresh
# virtual environment and run every quick-start command against the repository's examples.
# Usage (from the repository root): bash scripts/readme_smoke.sh [version]
set -euo pipefail
VERSION="${1:-}"
PYTHON="${PYTHON:-python3}"
step() { printf '\n==> %s\n' "$*"; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
"$PYTHON" -m venv "$WORK/venv"
BIN="$WORK/venv/bin"
[[ -d "$WORK/venv/Scripts" ]] && BIN="$WORK/venv/Scripts"

step "pip install chromerag${VERSION:+==$VERSION} (from PyPI, fresh venv)"
"$BIN/python" -m pip install -q --upgrade pip
"$BIN/python" -m pip install -q "chromerag${VERSION:+==$VERSION}"
"$BIN/chromerag" --version
OUT="$WORK/out"

step "Quick start 1: one page"
"$BIN/chromerag" extract examples/site/pricing.html -o "$OUT/pricing.md" --priority balanced --json-meta > /dev/null
grep -q "title: Plans and pricing" "$OUT/pricing.md"
grep -q "Monthly price (USD): 49" "$OUT/pricing.md"

step "Quick start 2: learn the site template, then batch"
"$BIN/chromerag" learn examples/site -o "$OUT/site_chrome.json" --min-pages 3
"$BIN/chromerag" batch examples/site -o "$OUT/batch" --chrome-model "$OUT/site_chrome.json"
grep -q "Monthly price (USD): 49" "$OUT/batch/pricing/chromerag.md"
if grep -q "Widget Summit" "$OUT/batch/pricing/chromerag.md"; then
  echo "repeated promo strip was not removed by the site model"; exit 1
fi

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
assert "Monthly price (USD): 49" in result.markdown
print("front_matter:", result.front_matter)
PY

printf '\nREADME smoke test passed for chromerag %s\n' "$("$BIN/chromerag" --version)"
