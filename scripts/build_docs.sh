#!/usr/bin/env bash
# Build the GitHub Pages site into _site/ (published to the gh-pages branch by CI).
# The site is one page, docs/index.html, which reads the JSON results in docs/data/.
# Steps: export local results (if any) into docs/data, run pytest and record the
# outcome in docs/data/test_report.json, then assemble _site/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-}"
[[ -z "$PYTHON" && -x .venv/bin/python ]] && PYTHON=".venv/bin/python"
PYTHON="${PYTHON:-python3}"
export PYTHONPATH="${ROOT}/src:${ROOT}${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p docs/data

echo "==> Export evaluation results into docs/data"
"$PYTHON" -m poc.export_site_results

echo "==> Run pytest"
JUNIT="$(mktemp -t chromerag-junit.XXXXXX)"
set +e
"$PYTHON" -m pytest tests/ -q --junitxml="$JUNIT"
PYTEST_RC=$?
set -e

JUNIT_PATH="$JUNIT" PYTEST_RC="$PYTEST_RC" "$PYTHON" - <<'PY'
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

root = ET.parse(os.environ["JUNIT_PATH"]).getroot()
suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
cases, totals = [], {"tests": 0, "failed": 0, "errors": 0, "skipped": 0}
for ts in suites:
    for case in ts.findall("testcase"):
        status = "passed"
        for tag, label in (("failure", "failed"), ("error", "error"), ("skipped", "skipped")):
            if case.find(tag) is not None:
                status = label
        totals["tests"] += 1
        if status != "passed":
            totals[{"failed": "failed", "error": "errors", "skipped": "skipped"}[status]] += 1
        cases.append({"classname": case.get("classname", ""), "name": case.get("name", ""), "status": status})
totals["passed"] = totals["tests"] - totals["failed"] - totals["errors"] - totals["skipped"]
payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "pytest_exit_code": int(os.environ["PYTEST_RC"]),
    "totals": totals,
    "cases": cases,
}
Path("docs/data/test_report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(f"{totals['passed']}/{totals['tests']} tests passed")
PY
rm -f "$JUNIT"

echo "==> Assemble _site/"
rm -rf _site
mkdir -p _site/data
cp docs/index.html _site/index.html
# The page needs only these; full per-page STCE reports stay in the repository.
for f in leaderboard corpus_comparison_report retrieval_eval_report stce_summary test_report; do
  cp "docs/data/$f.json" _site/data/
done
touch _site/.nojekyll
echo "Site ready in _site/ ($(du -sh _site | cut -f1))"
exit "$PYTEST_RC"
