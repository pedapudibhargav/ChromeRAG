"""Export QA/comparison summaries into docs/data for the static site."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "outputs"
DOCS_DATA = ROOT / "docs" / "data"


def main() -> None:
    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    mapping = {
        "qa_loop_summary.md": "qa_loop_summary.md",
        "qa_loop_report.json": "qa_loop_report.json",
        "comparison_summary.md": "comparison_summary.md",
        "comparison_report.json": "comparison_report.json",
        "corpus_comparison_summary.md": "corpus_comparison_summary.md",
        "corpus_comparison_report.json": "corpus_comparison_report.json",
    }
    copied = []
    for src_name, dst_name in mapping.items():
        src = OUT / src_name
        if src.exists():
            shutil.copy2(src, DOCS_DATA / dst_name)
            copied.append(dst_name)
    # compact leaderboard for the site
    for report_name in ("corpus_comparison_report.json", "qa_loop_report.json", "comparison_report.json"):
        path = OUT / report_name
        if not path.exists():
            continue
        report = json.loads(path.read_text(encoding="utf-8"))
        summary = (
            report.get("summary_ours_scoreable")
            or report.get("metrics", {}).get("summary")
            or report.get("summary")
            or {}
        )
        if summary:
            (DOCS_DATA / "leaderboard.json").write_text(
                json.dumps({"source": report_name, "summary": summary}, indent=2),
                encoding="utf-8",
            )
            copied.append("leaderboard.json")
            break
    print("Exported:", ", ".join(copied) or "(nothing yet)")


if __name__ == "__main__":
    main()
