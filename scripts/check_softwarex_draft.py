#!/usr/bin/env python3
"""SoftareX manuscript format/self-check (no official Elsevier linter exists).

Elsevier SoftareX requires the official Word/LaTeX *template* (styles must not be
altered). There is no public SoftareX auto-formatter. This script enforces the
guide-of-authors constraints we can check locally:

  - required section headings present
  - Highlights 3–5 bullets, each ≤85 chars
  - approximate word count ≤4000 (abstract+body+captions; excludes refs/metadata)
  - ≤6 figures referenced
  - Code metadata C1–C9 mentioned
  - AI declaration / funding / competing interests present

Usage:
  python scripts/check_softwarex_draft.py
  python scripts/check_softwarex_draft.py papers/softwarex/SOFTWAREX_DRAFT.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "papers" / "softwarex" / "SOFTWAREX_DRAFT.md"

REQUIRED_SECTIONS = [
    r"Motivation and significance",
    r"Software description",
    r"Illustrative examples",
    r"Impact",
    r"Conclusions",
]

REQUIRED_PHRASES = [
    (r"Code metadata|C1", "Code metadata table (C1–C9)"),
    (r"Declaration of generative AI", "AI declaration section"),
    (r"Funding|funding agencies", "Funding statement"),
    (r"competing interest|Competing interest|nothing to declare", "Competing interests"),
    (r"CRediT|Author contributions", "CRediT / author contributions"),
    (r"Playwright|must render|JS shell|JavaScript-rendered", "Honest JS-shell limitation"),
    (r"scoreable|Scoreable", "Scoreable-page filter disclosure"),
]


def _word_count_body(text: str) -> int:
    # Drop references / metadata tables / checklist tails for SoftareX count approx.
    cut = re.split(
        r"^##\s+References|^##\s+Paste checklist|^##\s+Declaration of competing",
        text,
        maxsplit=1,
        flags=re.M | re.I,
    )[0]
    # Also drop the code metadata table block roughly
    cut = re.sub(r"(?s)\| Nr \| Code metadata.*?\| C9 \|.*?\|", " ", cut)
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", cut)
    return len(words)


def _highlights(text: str) -> list[str]:
    m = re.search(r"(?is)##\s*Highlights\s*(.*?)(?:\n##\s|\Z)", text)
    if not m:
        return []
    block = m.group(1)
    return [re.sub(r"^[-*]\s*", "", ln).strip() for ln in block.splitlines() if re.match(r"^[-*]\s+\S", ln)]


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    if not path.exists():
        print(f"Missing draft: {path}")
        return 2
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    warns: list[str] = []

    for pat in REQUIRED_SECTIONS:
        if not re.search(pat, text, re.I):
            errors.append(f"Missing required section matching /{pat}/")

    for pat, label in REQUIRED_PHRASES:
        if not re.search(pat, text, re.I):
            errors.append(f"Missing: {label}")

    hl = _highlights(text)
    if not (3 <= len(hl) <= 5):
        errors.append(f"Highlights must be 3–5 bullets (found {len(hl)})")
    for h in hl:
        if len(h) > 85:
            errors.append(f"Highlight >85 chars ({len(h)}): {h[:60]}…")

    wc = _word_count_body(text)
    print(f"Approx SoftareX word count (body+abstract): {wc} (limit 4000)")
    if wc > 4000:
        errors.append(f"Word count {wc} exceeds SoftareX 4000 limit")
    elif wc > 3600:
        warns.append(f"Word count {wc} is close to the 4000 limit")

    fig_refs = re.findall(r"(?i)\b(?:fig(?:ure)?\.?\s*\d+|Fig\.?\s*\d+)\b", text)
    n_figs = len(set(fig_refs))
    print(f"Distinct figure references found: {n_figs} (limit 6)")
    if n_figs > 6:
        errors.append(f"More than 6 figures referenced ({n_figs})")

    if "official SoftareX" not in text and "official SoftwareX" not in text and "template" not in text.lower():
        warns.append("Remind authors: paste into official SoftareX Word/LaTeX template before EM")

    for w in warns:
        print(f"WARN: {w}")
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        print(f"\n{len(errors)} SoftareX self-check error(s).")
        return 1
    print("PASS: SoftareX draft self-check OK (still paste into official Elsevier template).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
