"""Run BoilerPy3 (Boilerpipe port) on WCXB pages; one text file per page and extractor.

    python extract_bp.py <wcxb_root> <split> <out_dir>
Third-party tool only. Errors are recorded and the output is left empty.
"""
import gzip
import json
import sys
import time
from importlib.metadata import version
from pathlib import Path

from boilerpy3 import extractors

root, split, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
names = {"default": extractors.DefaultExtractor, "article": extractors.ArticleExtractor}
meta = {"boilerpy3": version("boilerpy3"), "split": split, "ms": {}, "errors": {}}
for name in names:
    (out / name).mkdir(parents=True, exist_ok=True)
n = 0
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
    n += 1
    for name, cls in names.items():
        t0 = time.perf_counter()
        try:
            text = cls(raise_on_failure=False).get_content(html) or ""
        except Exception as exc:  # noqa: BLE001
            text = ""
            meta["errors"].setdefault(name, {})[gt_path.stem] = repr(exc)[:200]
        meta["ms"].setdefault(name, {})[gt_path.stem] = round((time.perf_counter() - t0) * 1000, 2)
        (out / name / f"{gt_path.stem}.txt").write_text(text, encoding="utf-8")
(out / "_meta.json").write_text(json.dumps(meta), encoding="utf-8")
print(n, "pages", meta["boilerpy3"], {k: len(v) for k, v in meta["errors"].items()})
