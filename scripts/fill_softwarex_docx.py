#!/usr/bin/env python3
"""Fill SoftareX OSP Word template from SOFTWAREX_EXPANDED.md.

Applies SoftareX Guide-for-Authors hard rules:
- Official template styles (Heading1/Heading2/Body); no style definition edits
- Five main sections + declarations + references
- Figures embedded later via embed_softwarex_figures.py (≤6)
- Content from expanded SoftareX manuscript (~2.9k words)
"""

from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14_NS = "http://schemas.microsoft.com/office/word/2010/wordml"
W = f"{{{W_NS}}}"
W14 = f"{{{W14_NS}}}"

TEMPLATE = Path.home() / "Downloads" / "softwarex-osp-template.docx"
EXPANDED = ROOT / "papers" / "softwarex" / "SOFTWAREX_EXPANDED.md"
OUT = ROOT / "papers" / "softwarex" / "ChromeRAG_SoftwareX_OSP.docx"

_NEXT_ID = 0xF000

TITLE = "ChromeRAG: Ingest-Time Elimination of Site Template Noise for Enterprise Web RAG"
AUTHORS = (
    "Bhargava Chary Peddapudi (Independent Researcher; "
    "ORCID: https://orcid.org/0009-0002-8523-8415); "
    "Corresponding email: pedapudibhargav@gmail.com"
)
KEYWORDS = "RAG; HTML extraction; boilerplate removal; vector pollution; Markdown; enterprise search"

METADATA = {
    "C1": "0.1.0",
    "C2": "https://github.com/pedapudibhargav/ChromeRAG/tree/v0.1.0",
    "C3": "MIT",
    "C4": "git",
    "C5": "Python ≥3.11, BeautifulSoup4, lxml, Pydantic; optional ONNX Runtime",
    "C6": (
        "macOS / Linux / Windows; pip install chromerag "
        "(or pip install -e . from the GitHub clone); "
        "optional extras: [dvdf], [fetch], [baselines], [ui]"
    ),
    "C7": "https://pedapudibhargav.github.io/ChromeRAG/ and repository README.md",
    "C8": "pedapudibhargav@gmail.com",
}

MAIN_SECTIONS = [
    "Motivation and significance",
    "Software description",
    "Illustrative examples",
    "Impact",
    "Conclusions",
]

# SoftareX preferred order (before Acknowledgements)
DECL_SECTIONS = [
    "CRediT author contribution statement",
    "Declaration of competing interest",
    "Funding",
    "Declaration of generative AI and AI-assisted technologies in the manuscript preparation process",
]

# Fallback bodies if a section is empty in the markdown parse
DECL_FALLBACKS: dict[str, str] = {
    "CRediT author contribution statement": (
        "Bhargava Chary Peddapudi: Conceptualization, Software, Methodology, "
        "Validation, Writing — original draft, Writing — review & editing."
    ),
    "Declaration of competing interest": (
        "The author declares that they have no known competing financial interests "
        "or personal relationships that could have appeared to influence the work "
        "reported in this paper."
    ),
    "Funding": (
        "This research did not receive any specific grant from funding agencies "
        "in the public, commercial, or not-for-profit sectors."
    ),
}


def _fresh_hex_id() -> str:
    global _NEXT_ID
    _NEXT_ID += 1
    return f"{_NEXT_ID:08X}"


def _para_text(p: etree._Element) -> str:
    return "".join(t.text or "" for t in p.iter(f"{W}t")).strip()


def _ensure_ppr(p: etree._Element, style: str) -> etree._Element:
    pPr = p.find(f"{W}pPr")
    if pPr is None:
        pPr = etree.Element(f"{W}pPr")
        p.insert(0, pPr)
    for tag in (f"{W}numPr", f"{W}ind"):
        for el in list(pPr.findall(tag)):
            pPr.remove(el)
    ps = pPr.find(f"{W}pStyle")
    if ps is None:
        ps = etree.SubElement(pPr, f"{W}pStyle")
    ps.set(f"{W}val", style)
    pPr.set(f"{W14}paraId", _fresh_hex_id())
    pPr.set(f"{W14}textId", _fresh_hex_id())
    return pPr


def _set_para(p: etree._Element, text: str, *, style: str) -> None:
    _ensure_ppr(p, style)
    pPr = p.find(f"{W}pPr")
    for child in list(p):
        if child is not pPr:
            p.remove(child)
    run = etree.SubElement(p, f"{W}r")
    t = etree.SubElement(run, f"{W}t")
    if text[:1].isspace() or text[-1:].isspace() or "  " in text:
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text


def _new_para(text: str, *, style: str) -> etree._Element:
    p = etree.Element(f"{W}p")
    _set_para(p, text, style=style)
    return p


def _strip_md(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()


def _parse_expanded(path: Path) -> dict[str, list[tuple[str, str]]]:
    """Return {section_title: [(kind, text), ...]} kind in h2|h3|p|code|table."""
    raw = path.read_text(encoding="utf-8")
    # Drop front matter before first ## Abstract
    if "## Abstract" in raw:
        raw = raw[raw.index("## Abstract") :]
    # Drop word-count appendix
    if "## Word count estimate" in raw:
        raw = raw[: raw.index("## Word count estimate")]

    sections: dict[str, list[tuple[str, str]]] = {}
    current = None
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
            i += 1
            continue
        if current is None:
            i += 1
            continue
        if line.startswith("### "):
            sections[current].append(("h3", line[4:].strip()))
            i += 1
            continue
        if line.startswith("```"):
            buf: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1  # closing fence
            code = "\n".join(buf).strip()
            if code:
                sections[current].append(("code", code))
            continue
        if line.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\|[-:| ]+\|$", lines[i + 1].strip()):
            rows: list[str] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = lines[i].strip()
                if not re.match(r"^\|[-:| ]+\|$", row):
                    cells = [c.strip() for c in row.strip("|").split("|")]
                    rows.append(" · ".join(_strip_md(c) for c in cells if c))
                i += 1
            if rows:
                # One Body paragraph per row (keeps SoftareX ≤6 tables budget;
                # real Word tables are optional polish).
                for row in rows:
                    sections[current].append(("p", row))
            continue
        if not line.strip() or line.strip() == "---":
            i += 1
            continue
        if line.startswith("**Keywords:**"):
            i += 1
            continue
        # Skip duplicate figure caption prose (figures are embedded with Word captions)
        if re.match(r"^\*\*Figure \d+", line) or re.match(r"^Figure \d+ —", _strip_md(line)):
            i += 1
            continue
        # Accumulate paragraph
        buf = [line]
        i += 1
        while i < len(lines):
            nxt = lines[i]
            if (
                not nxt.strip()
                or nxt.startswith("#")
                or nxt.startswith("```")
                or nxt.strip().startswith("|")
                or nxt.strip() == "---"
            ):
                break
            buf.append(nxt)
            i += 1
        text = _strip_md(" ".join(x.strip() for x in buf))
        if text:
            sections[current].append(("p", text))
    return sections


def _find_heading(paras: list[etree._Element], title: str) -> etree._Element | None:
    for p in paras:
        t = _para_text(p)
        if t == title or (title in t and len(t) < len(title) + 8):
            return p
    return None


def _clear_until_next_heading(body: etree._Element, heading: etree._Element, stop_titles: set[str]) -> None:
    """Remove paragraphs after heading until a stop title (or table/sectPr)."""
    remove: list[etree._Element] = []
    el = heading.getnext()
    while el is not None:
        tag = etree.QName(el).localname
        if tag == "tbl":
            break
        if tag == "sectPr":
            break
        if tag == "p":
            t = _para_text(el)
            if t in stop_titles or any(t == s or t.startswith(s) for s in stop_titles if len(s) > 10 and t.startswith(s[:20])):
                # exact match preferred
                if t in stop_titles:
                    break
                if t in MAIN_SECTIONS or t in DECL_SECTIONS or t in {"Acknowledgements", "References", "Metadata"}:
                    break
            remove.append(el)
        el = el.getnext()
    for p in remove:
        body.remove(p)


def _insert_blocks_after(anchor: etree._Element, blocks: list[tuple[str, str]]) -> etree._Element:
    cur = anchor
    for kind, text in blocks:
        if kind == "h3":
            p = _new_para(text, style="Heading2")
        elif kind == "code":
            # SoftareX Body; keep code as compact single/multi paras
            for line_group in text.split("\n\n"):
                chunk = line_group.replace("\n", " ⏎ ")
                p = _new_para(chunk, style="Body")
                cur.addnext(p)
                cur = p
            continue
        else:
            p = _new_para(text, style="Body")
        cur.addnext(p)
        cur = p
    return cur


def _set_table_metadata(root: etree._Element) -> None:
    tbl = next(root.iter(f"{W}tbl"))
    # Fix third header to SoftareX wording if present
    first_row = tbl.find(f"{W}tr")
    if first_row is not None:
        cells = first_row.findall(f"{W}tc")
        if len(cells) >= 3:
            hdr = "".join(t.text or "" for t in cells[2].iter(f"{W}t")).strip()
            if hdr in {"Metadata", "Please fill in this column"} or "fill in" in hdr.lower() or hdr == "Metadata":
                p = cells[2].find(f"{W}p")
                if p is not None:
                    _set_para(p, "Please fill in this column", style="Body")
    for tr in tbl.findall(f"{W}tr"):
        cells = tr.findall(f"{W}tc")
        if len(cells) < 3:
            continue
        key = "".join(t.text or "" for t in cells[0].iter(f"{W}t")).strip()
        if key not in METADATA:
            continue
        p = cells[2].find(f"{W}p")
        if p is None:
            p = etree.SubElement(cells[2], f"{W}p")
        _set_para(p, METADATA[key], style="Body")


def _remove_bookmarks(root: etree._Element) -> None:
    for tag in (f"{W}bookmarkStart", f"{W}bookmarkEnd", f"{W}proofErr"):
        for el in list(root.findall(f".//{tag}")):
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)


def _delete_front_matter(body: etree._Element) -> None:
    paras = list(body.findall(f"{W}p"))
    sep_idx = None
    for i, p in enumerate(paras):
        t = _para_text(p)
        if (t.startswith("- - -") or (t.count("-") > 40 and "Title" not in t)) and i < 25:
            sep_idx = i
            break
    if sep_idx is None:
        raise RuntimeError("Template separator not found")
    for p in paras[: sep_idx + 1]:
        body.remove(p)


def _write_document(path: Path, tree: etree._ElementTree) -> None:
    tree.write(str(path), xml_declaration=True, encoding="UTF-8", standalone=True)
    text = path.read_text(encoding="utf-8")
    if text.startswith("<?xml"):
        text = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + text.split("?>", 1)[1].lstrip("\n")
    path.write_text(text, encoding="utf-8")


def main() -> None:
    if not TEMPLATE.exists():
        raise SystemExit(f"Missing template: {TEMPLATE}")
    if not EXPANDED.exists():
        raise SystemExit(f"Missing expanded manuscript: {EXPANDED}")

    sections = _parse_expanded(EXPANDED)
    abstract_blocks = sections.get("Abstract", [])
    abstract = next((t for k, t in abstract_blocks if k == "p"), "")
    if not abstract:
        raise SystemExit("Abstract missing in SOFTWAREX_EXPANDED.md")

    work = ROOT / "papers" / "softwarex" / "_docx_work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    with zipfile.ZipFile(TEMPLATE) as zf:
        zf.extractall(work)

    doc_xml = work / "word" / "document.xml"
    tree = etree.parse(str(doc_xml))
    root = tree.getroot()
    body = root.find(f"{W}body")
    assert body is not None

    _remove_bookmarks(root)
    _delete_front_matter(body)

    paras = list(body.findall(f"{W}p"))
    title_p = next(p for p in paras if "Title (Name of your software" in _para_text(p))
    _set_para(title_p, TITLE, style="Heading1")
    authors_p = next(p for p in paras if "Names of authors" in _para_text(p))
    _set_para(authors_p, AUTHORS, style="Body")

    abs_h = _find_heading(paras, "Abstract")
    assert abs_h is not None
    ca = next(p for p in paras if "ca. 100 words" in _para_text(p) or "(ca." in _para_text(p))
    _set_para(ca, abstract, style="Body")
    six = next((p for p in paras if "Your main body of text (Sections 1-5" in _para_text(p)), None)
    if six is not None:
        body.remove(six)

    for p in list(body.findall(f"{W}p")):
        t = _para_text(p)
        if "maximum of six" in t or t == "(maximum of six)":
            _set_para(p, KEYWORDS, style="Body")

    meta_instr = next(
        (p for p in body.findall(f"{W}p") if "This ancillary data table is required" in _para_text(p)),
        None,
    )
    if meta_instr is not None:
        body.remove(meta_instr)
    _set_table_metadata(root)

    # Remove empty leftovers around front matter
    for p in list(body.findall(f"{W}p")):
        if _para_text(p) == "" and p.find(f".//{W}drawing") is None:
            # keep nothing empty at this stage
            body.remove(p)

    stop_all = set(MAIN_SECTIONS + DECL_SECTIONS + ["Acknowledgements", "References", "Metadata"])

    # Fill five main sections from expanded manuscript
    for section in MAIN_SECTIONS:
        paras = list(body.findall(f"{W}p"))
        h = _find_heading(paras, section)
        if h is None:
            raise RuntimeError(f"Missing heading {section!r} in template")
        _set_para(h, section, style="Heading1")
        _clear_until_next_heading(body, h, stop_all - {section})
        blocks = sections.get(section, [])
        if not blocks:
            raise RuntimeError(f"No content for {section} in SOFTWAREX_EXPANDED.md")
        last = _insert_blocks_after(h, blocks)

        if section == "Illustrative examples":
            # Place figures after Corpus comparison, before Priority knobs
            paras_now = list(body.findall(f"{W}p"))
            knobs = _find_heading(paras_now, "Priority knobs and input-quality warnings")
            if knobs is not None:
                insert_after = knobs.getprevious()
                if insert_after is None:
                    insert_after = last
            else:
                insert_after = last
            for n in range(1, 5):
                img = _new_para(f"__FIG{n}_IMG__", style="Body")
                cap = _new_para(f"__FIG{n}_CAP__", style="Body")
                insert_after.addnext(img)
                img.addnext(cap)
                insert_after = cap
            # Ensure Priority knobs stays Heading2 after figure insert
            if knobs is not None:
                _set_para(knobs, "Priority knobs and input-quality warnings", style="Heading2")

    # Ensure Impact heading style after figure inserts
    impact_h = _find_heading(list(body.findall(f"{W}p")), "Impact")
    if impact_h is not None:
        _set_para(impact_h, "Impact", style="Heading1")

    # After Conclusions, insert declaration sections before Acknowledgements.
    # SoftareX OSP templates may already contain some of these headings — remove
    # any existing declaration/ack/refs tail and rebuild cleanly.
    ack = _find_heading(list(body.findall(f"{W}p")), "Acknowledgements")
    ref_h = _find_heading(list(body.findall(f"{W}p")), "References")
    # Drop any pre-existing declaration headings and their bodies between
    # Conclusions content and Acknowledgements/References.
    stop_after_conc = set(DECL_SECTIONS) | {"Acknowledgements", "References"}
    conc_h = _find_heading(list(body.findall(f"{W}p")), "Conclusions")
    assert conc_h is not None
    # Remove everything after conclusions content until Acknowledgements/References
    # (template placeholders + any prior bad inserts). Keep Conclusions body.
    el = conc_h.getnext()
    while el is not None:
        nxt = el.getnext()
        tag = etree.QName(el).localname
        if tag == "sectPr":
            break
        if tag == "p":
            t = _para_text(el)
            if t in {"Acknowledgements", "References"}:
                break
            # Remove leftover template declaration headings and any orphan paras
            # that appear after Conclusions once we hit the first decl/ack/ref title,
            # OR remove known decl titles anywhere after conclusions.
            if t in stop_after_conc or t.startswith("Declaration of") or t.startswith("CRediT"):
                # From this point, remove until Ack/Refs (exclusive)
                while el is not None:
                    nxt2 = el.getnext()
                    if etree.QName(el).localname == "p" and _para_text(el) in {
                        "Acknowledgements",
                        "References",
                    }:
                        break
                    if etree.QName(el).localname == "sectPr":
                        break
                    body.remove(el)
                    el = nxt2
                break
        el = nxt

    ack = _find_heading(list(body.findall(f"{W}p")), "Acknowledgements")
    insert_before = ack if ack is not None else _find_heading(
        list(body.findall(f"{W}p")), "References"
    )
    assert insert_before is not None

    # Insert in reverse SoftareX order with a moving cursor so each new section
    # lands before the previous one, with heading immediately above its body.
    cursor = insert_before
    for decl_title in reversed(DECL_SECTIONS):
        blocks = sections.get(decl_title, [])
        body_paras = [t for k, t in blocks if k == "p"]
        if not body_paras and decl_title in DECL_FALLBACKS:
            body_paras = [DECL_FALLBACKS[decl_title]]
        if not body_paras:
            raise RuntimeError(f"No content for declaration {decl_title!r}")
        for text in reversed(body_paras):
            p = _new_para(text, style="Body")
            cursor.addprevious(p)
            cursor = p
        h = _new_para(decl_title, style="Heading1")
        cursor.addprevious(h)
        cursor = h

    # Acknowledgements
    paras = list(body.findall(f"{W}p"))
    ack = _find_heading(paras, "Acknowledgements")
    if ack is not None:
        _set_para(ack, "Acknowledgements", style="Heading1")
        _clear_until_next_heading(body, ack, {"References"})
        p = _new_para("None.", style="Body")
        ack.addnext(p)

    # References
    paras = list(body.findall(f"{W}p"))
    ref_h = _find_heading(paras, "References")
    assert ref_h is not None
    _set_para(ref_h, "References", style="Heading1")
    _clear_until_next_heading(body, ref_h, set())
    # Also remove trailing reminders after references
    el = ref_h.getnext()
    while el is not None and etree.QName(el).localname == "p":
        nxt = el.getnext()
        t = _para_text(el)
        if "Reminder:" in t or t == "Thank you!" or "including this paragraph" in t:
            body.remove(el)
        el = nxt

    ref_blocks = sections.get("References", [])
    ref_texts = [t for k, t in ref_blocks if k == "p"]
    # Also split numbered list if one blob
    if len(ref_texts) == 1 and re.search(r"\n\d+\.\s", ref_texts[0]):
        ref_texts = [x.strip() for x in re.split(r"\n(?=\d+\.\s)", ref_texts[0]) if x.strip()]
    # Parse original md numbered refs from file if needed
    if len(ref_texts) < 6:
        ref_section = EXPANDED.read_text(encoding="utf-8")
        m = re.search(r"## References\n\n(.*?)(?:\n---|\n## Word count)", ref_section, re.S)
        if m:
            raw_refs = m.group(1).strip()
            ref_texts = []
            for line in raw_refs.splitlines():
                line = line.strip()
                if re.match(r"^\d+\.\s", line):
                    ref_texts.append(_strip_md(line))
                elif ref_texts and line:
                    ref_texts[-1] += " " + _strip_md(line)

    cur = ref_h
    for text in ref_texts:
        p = _new_para(text, style="Body")
        cur.addnext(p)
        cur = p

    # Final empty cleanup (keep figure placeholders)
    for p in list(body.findall(f"{W}p")):
        t = _para_text(p)
        if t == "" and p.find(f".//{W}drawing") is None:
            body.remove(p)

    for el in root.iter():
        for attr in list(el.attrib):
            local = etree.QName(attr).localname if attr.startswith("{") else attr
            if local.lower().startswith("rsid"):
                del el.attrib[attr]
    for pPr in root.findall(f".//{W}pPr"):
        pPr.set(f"{W14}paraId", _fresh_hex_id())
        pPr.set(f"{W14}textId", _fresh_hex_id())

    _write_document(doc_xml, tree)
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in work.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(work).as_posix())
    shutil.rmtree(work)

    # Report
    z = zipfile.ZipFile(OUT)
    doc = etree.fromstring(z.read("word/document.xml"))
    texts = [
        "".join(t.text or "" for t in p.iter(f"{W}t")).strip()
        for p in doc.find(f"{W}body").findall(f"{W}p")
    ]
    words = sum(len(re.findall(r"\b[\w']+\b", t)) for t in texts if t and not t.startswith("__FIG"))
    figs = sum(1 for t in texts if t.startswith("__FIG") and t.endswith("_IMG__"))
    print(f"Wrote {OUT}")
    print(f"  approx words in all paras (excl fig markers): {words}")
    print(f"  fig placeholders: {figs}")
    for needle in MAIN_SECTIONS + DECL_SECTIONS[:1] + ["References"]:
        print(f"  has {needle!r}:", any(t == needle for t in texts))


if __name__ == "__main__":
    main()
