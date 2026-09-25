"""Copy the published evaluation results from data/outputs into docs/data.

docs/index.html (the GitHub Pages site) and the paper figures read these files.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "outputs"
DOCS_DATA = ROOT / "docs" / "data"

PUBLISHED = (
    "corpus_comparison_report.json",
    "corpus_comparison_summary.md",
    "corpus_revalidation.json",
    "retrieval_eval_report.json",
    "stce_eval_report.json",
    "stce_eval_stce_crawl_report.json",
)


def main() -> None:
    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in PUBLISHED:
        src = OUT / name
        if src.exists():
            shutil.copy2(src, DOCS_DATA / name)
            copied.append(name)
    report = DOCS_DATA / "corpus_comparison_report.json"
    if report.exists():
        payload = json.loads(report.read_text(encoding="utf-8"))
        leaderboard = {
            "source": report.name,
            "n_scoreable": payload.get("n_scoreable"),
            "n_fetched": payload.get("n_fetched"),
            "corpus_urls_listed": payload.get("corpus_urls_listed"),
            "summary": payload.get("summary", {}),
            "summary_all_fetched": payload.get("summary_all_fetched", {}),
            "paired_bootstrap": payload.get("paired_bootstrap", []),
        }
        (DOCS_DATA / "leaderboard.json").write_text(json.dumps(leaderboard, indent=2), encoding="utf-8")
        copied.append("leaderboard.json")
    # The site shows only the STCE summaries; the full per-page reports stay in docs/data.
    stce = {}
    for key, name in (("benchmark", "stce_eval_report.json"), ("crawl", "stce_eval_stce_crawl_report.json")):
        path = DOCS_DATA / name
        if path.exists():
            full = json.loads(path.read_text(encoding="utf-8"))
            stce[key] = {k: v for k, v in full.items() if k != "pages"}
    if stce:
        (DOCS_DATA / "stce_summary.json").write_text(json.dumps(stce, indent=2), encoding="utf-8")
        copied.append("stce_summary.json")
    print("Exported:", ", ".join(copied) or "(nothing yet)")


if __name__ == "__main__":
    main()
