#!/usr/bin/env bash
# Cold-install smoke test: clone-style install into a fresh venv and extract a fixture.
# Usage: ./scripts/verify_cold_install.sh
# Requires Python ≥3.11 (set PYTHON=... if needed).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="${TMPDIR:-/tmp}/chromerag-cold-$$"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

if [[ -z "${PYTHON:-}" ]]; then
  if command -v python3.14 >/dev/null 2>&1; then PYTHON=python3.14
  elif command -v python3.13 >/dev/null 2>&1; then PYTHON=python3.13
  elif command -v python3.12 >/dev/null 2>&1; then PYTHON=python3.12
  elif command -v python3.11 >/dev/null 2>&1; then PYTHON=python3.11
  else PYTHON=python3
  fi
fi

"$PYTHON" -c 'import sys; assert sys.version_info >= (3, 11), sys.version'
"$PYTHON" -m venv "$TMP/venv"
# shellcheck disable=SC1091
source "$TMP/venv/bin/activate"
python -m pip install -q -U pip setuptools wheel
PIP_ARGS=()
if [[ -n "${PYPI_INDEX_URL:-}" ]]; then
  PIP_ARGS+=(--index-url "$PYPI_INDEX_URL")
  [[ -n "${PIP_TRUSTED_HOST:-}" ]] && PIP_ARGS+=(--trusted-host "$PIP_TRUSTED_HOST")
fi
pip install -q -e "$ROOT" "${PIP_ARGS[@]}"
chromerag extract "$ROOT/tests/fixtures/docs_page.html" -o "$TMP/out.md" --priority balanced
PYVER="$("$PYTHON" -V 2>&1)"
python - <<PY
from pathlib import Path
md = Path("$TMP/out.md").read_text(encoding="utf-8")
assert "bandwidth" in md.lower() or "sla" in md.lower(), md[:400]
print("COLD_INSTALL_OK", "$PYVER", "bytes=", len(md))
PY
