#!/usr/bin/env bash
# Build docs artifacts that GitHub Pages will publish (from gh-pages branch).
# Runs unit tests, writes docs/data/test_report.json + docs/tests.html, exports corpus results.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-}"
[[ -z "$PYTHON" && -x .venv/bin/python ]] && PYTHON=".venv/bin/python"
PYTHON="${PYTHON:-python3}"

mkdir -p docs/data
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

echo "==> Export corpus comparison into docs/data"
"$PYTHON" -m poc.export_site_results

echo "==> Run pytest"
JUNIT="docs/data/pytest_junit.xml"
set +e
"$PYTHON" -m pytest tests/ -q --junitxml="$JUNIT"
PYTEST_RC=$?
set -e

echo "==> Render docs/tests.html from JUnit"
PYTEST_RC="$PYTEST_RC" JUNIT_PATH="$JUNIT" ROOT="$ROOT" "$PYTHON" <<'PY'
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

root = Path(os.environ["ROOT"])
junit = Path(os.environ["JUNIT_PATH"])
pytest_rc = int(os.environ.get("PYTEST_RC", "1"))
out = root / "docs" / "data" / "test_report.json"
html_path = root / "docs" / "tests.html"

suites: list[dict] = []
total = failed = skipped = errors = 0
if junit.exists():
    tree_root = ET.parse(junit).getroot()
    if tree_root.tag == "testsuites":
        nodes = list(tree_root.findall("testsuite"))
    elif tree_root.tag == "testsuite":
        nodes = [tree_root]
    else:
        nodes = []
    for ts in nodes:
        total += int(ts.attrib.get("tests", 0) or 0)
        failed += int(ts.attrib.get("failures", 0) or 0)
        errors += int(ts.attrib.get("errors", 0) or 0)
        skipped += int(ts.attrib.get("skipped", 0) or 0)
        for case in ts.findall("testcase"):
            status = "passed"
            msg = ""
            fail = case.find("failure")
            err = case.find("error")
            skip = case.find("skipped")
            if fail is not None:
                status = "failed"
                msg = (fail.attrib.get("message") or "")[:300]
            elif err is not None:
                status = "error"
                msg = (err.attrib.get("message") or "")[:300]
            elif skip is not None:
                status = "skipped"
            suites.append(
                {
                    "classname": case.attrib.get("classname", ""),
                    "name": case.attrib.get("name", ""),
                    "time": float(case.attrib.get("time", 0) or 0),
                    "status": status,
                    "message": msg,
                }
            )

payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "pytest_exit_code": pytest_rc,
    "totals": {
        "tests": total,
        "passed": max(0, total - failed - errors - skipped),
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
    },
    "cases": suites,
}
out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

rows = []
for c in suites:
    rows.append(
        "<tr class='{status}'><td><code>{classname}</code></td>"
        "<td>{name}</td><td>{status}</td>"
        "<td>{time:.3f}s</td><td>{message}</td></tr>".format(**c)
    )
t = payload["totals"]
status_line = (
    f"{t['passed']} passed · {t['failed']} failed · {t['errors']} errors · "
    f"{t['skipped']} skipped · exit {payload['pytest_exit_code']}"
)
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Tests — ChromeRAG</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=IBM+Plex+Mono:wght@400;500&family=Source+Sans+3:wght@400;600&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="./assets/site.css" />
</head>
<body>
  <header class="site">
    <div class="wrap nav">
      <a class="brand" href="./index.html">Chrome<span>RAG</span></a>
      <ul class="nav-links">
        <li><a href="./index.html">Home</a></li>
        <li><a href="./metrics.html">Metrics</a></li>
        <li><a href="./results.html">Results</a></li>
        <li><a href="./tests.html">Tests</a></li>
        <li><a href="./quickstart.html">Quickstart</a></li>
      </ul>
    </div>
  </header>
  <main class="wrap" style="padding:2rem 1.25rem 3rem">
    <h1 style="font-family:var(--font-display)">Automated test report</h1>
    <p style="color:var(--muted)">Generated at {payload['generated_at']}</p>
    <p><strong>{status_line}</strong></p>
    <div class="note">
      Published by GitHub Actions on every push to <code>main</code>
      (site files deployed to the <code>gh-pages</code> branch).
    </div>
    <table>
      <thead><tr><th>Suite</th><th>Test</th><th>Status</th><th>Time</th><th>Detail</th></tr></thead>
      <tbody>
{chr(10).join(rows)}
      </tbody>
    </table>
    <h2 style="margin-top:2rem">Corpus benchmark</h2>
    <p>See <a href="./results.html">Results</a> for the ~200-URL HTML→Markdown comparison (Recall / Noise / Fbal).</p>
  </main>
  <footer class="site"><div class="wrap">ChromeRAG documentation</div></footer>
  <script src="./assets/site.js"></script>
</body>
</html>
"""
html_path.write_text(html, encoding="utf-8")
print(f"wrote {out}")
print(f"wrote {html_path}")
print(status_line)
raise SystemExit(pytest_rc)
PY
