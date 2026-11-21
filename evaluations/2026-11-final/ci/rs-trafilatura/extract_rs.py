"""Run rs-trafilatura on WCXB pages and write one text file per page. Third-party tool only; ChromeRAG is not involved.

    python extract_rs.py <wcxb_root> <split> <out_dir>
"""
import gzip
import json
import sys
import time
from importlib.metadata import version
from pathlib import Path

import rs_trafilatura

root, split, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
meta = {"rs_trafilatura": version("rs-trafilatura"), "split": split, "ms": {}}
for gt_path in sorted((root / split / "ground-truth").glob("*.json")):
    data = json.loads(gt_path.read_text(encoding="utf-8"))
    gt = data.get("ground_truth", {})
    if not isinstance(gt, dict) or "main_content" not in gt:
        continue
    html_path = root / split / "html" / f"{gt_path.stem}.html.gz"
    if not html_path.exists():
        continue
    with gzip.open(html_path, "rt", encoding="utf-8", errors="ignore") as fh:
        html = fh.read()
    t0 = time.perf_counter()
    res = rs_trafilatura.extract(html, url=data.get("url") or None)
    meta["ms"][gt_path.stem] = round((time.perf_counter() - t0) * 1000, 2)
    (out / f"{gt_path.stem}.txt").write_text((res.main_content if res is not None else "") or "", encoding="utf-8")
(out / "_meta.json").write_text(json.dumps(meta), encoding="utf-8")
print(len(meta["ms"]), "pages", meta["rs_trafilatura"])
