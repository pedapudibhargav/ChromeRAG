"""Score every extractor on the landing-page corpus (company marketing sites).

Same harness, metrics and tool-independent scoreable rule as poc.run_corpus_comparison;
the pages come from poc/landing_urls.json (see poc.landing_corpus). Writes
data/outputs/landing/landing_comparison_report.json and per-tool Markdown per page.

Usage:
  python -m poc.landing_corpus --plan --fetch    # network
  python -m poc.run_landing_eval
"""

from __future__ import annotations

import json

from poc.landing_corpus import RAW, URLS
from poc.run_corpus_comparison import OUT, run

LANDING_OUT = OUT / "landing"


def main() -> None:
    listed = sum(len(c["pages"]) for c in json.loads(URLS.read_text(encoding="utf-8"))["companies"].values())
    run(fetch=False, raw=RAW, out=LANDING_OUT, report_name="landing_comparison", listed=listed)


if __name__ == "__main__":
    main()
