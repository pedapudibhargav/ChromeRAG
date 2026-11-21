#!/usr/bin/env python3
"""Write papers/softwarex/ChromeRAG_highlights.docx (Editorial Manager upload) from the code block in HIGHLIGHTS.md."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "papers" / "softwarex" / "HIGHLIGHTS.md"
OUT = ROOT / "papers" / "softwarex" / "ChromeRAG_highlights.docx"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
STAMP = (1980, 1, 1, 0, 0, 0)  # fixed zip timestamps: the same text gives the same file

CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/numbering.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
    "</Types>"
)
RELS = (
    '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/></Relationships>'
)
DOC_RELS = (
    '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" '
    'Target="numbering.xml"/></Relationships>'
)
NUMBERING = (
    f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:numbering xmlns:w="{W}">'
    '<w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="hybridMultilevel"/><w:lvl w:ilvl="0">'
    '<w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/>'
    '<w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum>'
    '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>'
)


def highlights() -> list[str]:
    m = re.search(r"```\n(.*?)\n```", SRC.read_text(encoding="utf-8"), re.S)
    if not m:
        raise SystemExit(f"No highlights code block in {SRC}")
    items = [h.strip() for h in m.group(1).splitlines() if h.strip()]
    if not 3 <= len(items) <= 5 or any(len(h) > 85 for h in items):
        raise SystemExit("Highlights must be 3-5 bullets of at most 85 characters")
    return items


def main() -> None:
    paras = ['<w:p><w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">Highlights</w:t></w:r></w:p>']
    for h in highlights():
        paras.append(
            '<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>'
            f'<w:r><w:t xml:space="preserve">{escape(h)}</w:t></w:r></w:p>'
        )
    doc = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{W}"><w:body>{"".join(paras)}</w:body></w:document>'
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in (
            ("[Content_Types].xml", CONTENT_TYPES),
            ("_rels/.rels", RELS),
            ("word/document.xml", doc),
            ("word/numbering.xml", NUMBERING),
            ("word/_rels/document.xml.rels", DOC_RELS),
        ):
            zf.writestr(zipfile.ZipInfo(name, STAMP), data)
    print(f"Wrote {OUT} ({len(paras) - 1} highlights)")


if __name__ == "__main__":
    main()
