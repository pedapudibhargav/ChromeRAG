#!/usr/bin/env python3
"""Pre-submission self-check of the SoftwareX OSP manuscript (.docx) and Highlights.

Checks the rules stated in the SoftwareX template (v6, March 2026) / Guide for Authors:
five mandatory sections, filled code-metadata table (C1–C8, GitHub URL), ≤ 4000 words
(abstract + body + captions), ≤ 6 figures, abstract ≈ 100 words, ≤ 6 keywords,
declarations, 3–5 highlights of ≤ 85 characters, no leftover template instructions,
and that every reference is cited.

Usage:
  python scripts/check_softwarex_draft.py [path/to/manuscript.docx]
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "papers" / "softwarex" / "ChromeRAG_SoftwareX_OSP.docx"
HIGHLIGHTS = ROOT / "papers" / "softwarex" / "HIGHLIGHTS.md"

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MAIN = ["Motivation and significance", "Software description", "Illustrative examples", "Impact", "Conclusions"]
DECLS = [
    "CRediT author contribution statement",
    "Declaration of competing interest",
    "Funding",
    "Data availability",
    "Declaration of generative AI and AI-assisted technologies in the manuscript preparation process",
    "References",
]
TEMPLATE_LEFTOVERS = ["For example", "Please fill in", "In this section, we want you", "Reminder:", "(ca. 100 words)"]


def _words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’.-]*", text))


def main() -> int:
    from lxml import etree

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    with zipfile.ZipFile(path) as zf:
        root = etree.fromstring(zf.read("word/document.xml"))
    body = root.find(f"{W}body")
    paras = [
        ("".join(t.text or "" for t in p.iter(f"{W}t")).strip(), p)
        for p in body.findall(f"{W}p")
    ]
    texts = [t for t, _ in paras]
    errors: list[str] = []
    warns: list[str] = []

    for title in MAIN + DECLS:
        if title not in texts:
            errors.append(f"Missing section heading: {title}")

    # Code metadata table
    tbl = next(root.iter(f"{W}tbl"))
    meta = {}
    for tr in tbl.findall(f"{W}tr"):
        cells = ["".join(t.text or "" for t in tc.iter(f"{W}t")).strip() for tc in tr.findall(f"{W}tc")]
        if cells and re.fullmatch(r"C\d", cells[0]):
            meta[cells[0]] = cells[-1]
    for key in [f"C{i}" for i in range(1, 9)]:
        if not meta.get(key):
            errors.append(f"Code metadata {key} is empty")
    if "github.com" not in meta.get("C2", ""):
        errors.append("C2 must be a GitHub URL")

    # Abstract / keywords
    abstract = texts[texts.index("Abstract") + 1] if "Abstract" in texts else ""
    kw = texts[texts.index("Keywords") + 1] if "Keywords" in texts else ""
    n_abs = _words(abstract)
    n_kw = len([k for k in kw.split(";") if k.strip()])
    print(f"Abstract words: {n_abs} (template asks ca. 100)")
    if n_abs > 150:
        errors.append(f"Abstract too long ({n_abs} words)")
    elif n_abs > 120:
        warns.append(f"Abstract is {n_abs} words (template asks ca. 100)")
    if not 1 <= n_kw <= 6:
        errors.append(f"Keywords must be 1–6 (found {n_kw})")

    # Word count: abstract + five main sections (body text, captions, tables, code)
    start = texts.index(MAIN[0]) if MAIN[0] in texts else 0
    end = texts.index(DECLS[0]) if DECLS[0] in texts else len(texts)
    body_words = sum(_words(t) for t in texts[start:end] if not t.startswith("__FIG"))
    table_words = 0
    for t in body.findall(f"{W}tbl")[1:]:
        table_words += _words(" ".join(x.text or "" for x in t.iter(f"{W}t")))
    total = n_abs + body_words + table_words
    print(f"Words (abstract + main sections + captions + tables): {total} (limit 4000)")
    if total > 4000:
        errors.append(f"Word count {total} exceeds 4000")

    # Figures
    n_figs = len(list(root.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}blip")))
    captions = [t for t in texts if re.match(r"^Figure \d+\.", t)]
    print(f"Embedded figures: {n_figs}; captions: {len(captions)} (limit 6)")
    if n_figs > 6:
        errors.append(f"More than 6 figures ({n_figs})")
    if n_figs != len(captions):
        errors.append("Figure/caption count mismatch")
    if any(t.startswith("__FIG") for t in texts):
        errors.append("Unfilled figure placeholder left in document")

    # Leftover template instructions
    for t in texts:
        for bad in TEMPLATE_LEFTOVERS:
            if bad in t:
                errors.append(f"Template instruction left in text: {t[:60]!r}")

    # References cited
    if "References" in texts:
        refs = [t for t in texts[texts.index("References") + 1 :] if re.match(r"^\d+\.", t)]
        body_text = " ".join(texts[: texts.index("References")])
        cited: set[int] = set()
        for grp in re.findall(r"\[([\d,\s–-]+)\]", body_text):
            for part in grp.split(","):
                part = part.strip()
                if re.fullmatch(r"\d+[–-]\d+", part):
                    a, b = map(int, re.split(r"[–-]", part))
                    cited.update(range(a, b + 1))
                elif part.isdigit():
                    cited.add(int(part))
        uncited = [i for i in range(1, len(refs) + 1) if i not in cited]
        print(f"References: {len(refs)}; uncited: {uncited or 'none'}")
        if uncited:
            errors.append(f"References never cited in text: {uncited}")
        if cited - set(range(1, len(refs) + 1)):
            errors.append(f"Citations without reference entries: {sorted(cited - set(range(1, len(refs) + 1)))}")

    # Highlights
    if HIGHLIGHTS.exists():
        m = re.search(r"```\n(.*?)\n```", HIGHLIGHTS.read_text(encoding="utf-8"), re.S)
        hl = [h for h in (m.group(1).splitlines() if m else []) if h.strip()]
        print(f"Highlights: {len(hl)} (max length {max((len(h) for h in hl), default=0)})")
        if not 3 <= len(hl) <= 5:
            errors.append(f"Highlights must be 3–5 bullets (found {len(hl)})")
        errors.extend(f"Highlight > 85 chars: {h}" for h in hl if len(h) > 85)
    else:
        errors.append(f"Missing {HIGHLIGHTS}")

    for w in warns:
        print(f"WARN: {w}")
    for e in errors:
        print(f"FAIL: {e}")
    if errors:
        print(f"\n{len(errors)} self-check error(s).")
        return 1
    print("PASS: SoftwareX manuscript self-check OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
