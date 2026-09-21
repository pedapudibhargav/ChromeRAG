#!/usr/bin/env python3
"""Fill Elsevier SoftareX OSP Word template (v6) from SOFTWAREX_DRAFT content.

Uses only the stdlib (zipfile + xml.etree) — no python-docx dependency.
Preserves template styles; replaces italic instruction text with manuscript text.
"""

from __future__ import annotations

import re
import shutil
import zipfile
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}
ET.register_namespace("w", W_NS)
# Keep common OOXML namespaces if present
for prefix, uri in [
    ("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships"),
    ("wp", "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"),
    ("a", "http://schemas.openxmlformats.org/drawingml/2006/main"),
    ("pic", "http://schemas.openxmlformats.org/drawingml/2006/picture"),
    ("mc", "http://schemas.openxmlformats.org/markup-compatibility/2006"),
    ("w14", "http://schemas.microsoft.com/office/word/2010/wordml"),
    ("w15", "http://schemas.microsoft.com/office/word/2012/wordml"),
]:
    ET.register_namespace(prefix, uri)

TEMPLATE = Path.home() / "Downloads" / "softwarex-osp-template.docx"
OUT = ROOT / "papers" / "softwarex" / "ChromeRAG_SoftwareX_OSP.docx"


def _para_text(p: ET.Element) -> str:
    return "".join(t.text or "" for t in p.iter(f"{{{W_NS}}}t"))


def _set_para_text(p: ET.Element, text: str) -> None:
    """Replace all text in a paragraph with a single run (preserve pPr)."""
    pPr = p.find(f"{{{W_NS}}}pPr")
    for child in list(p):
        if child is not pPr:
            p.remove(child)
    run = ET.SubElement(p, f"{{{W_NS}}}r")
    # Prefer non-italic body for filled content
    rPr = ET.SubElement(run, f"{{{W_NS}}}rPr")
    ET.SubElement(rPr, f"{{{W_NS}}}i").set(f"{{{W_NS}}}val", "0")
    t = ET.SubElement(run, f"{{{W_NS}}}t")
    if text.startswith(" ") or text.endswith(" ") or "  " in text:
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text


def _clone_para_after(body: ET.Element, after: ET.Element, text: str, style: str | None = "Body") -> ET.Element:
    """Insert a new paragraph after `after` with optional style."""
    new_p = ET.Element(f"{{{W_NS}}}p")
    pPr = ET.SubElement(new_p, f"{{{W_NS}}}pPr")
    if style:
        ps = ET.SubElement(pPr, f"{{{W_NS}}}pStyle")
        ps.set(f"{{{W_NS}}}val", style)
    run = ET.SubElement(new_p, f"{{{W_NS}}}r")
    rPr = ET.SubElement(run, f"{{{W_NS}}}rPr")
    ET.SubElement(rPr, f"{{{W_NS}}}i").set(f"{{{W_NS}}}val", "0")
    t_el = ET.SubElement(run, f"{{{W_NS}}}t")
    t_el.text = text
    # insert after
    children = list(body)
    idx = children.index(after)
    body.insert(idx + 1, new_p)
    return new_p


def _find_para(paras: list[ET.Element], contains: str) -> ET.Element | None:
    for p in paras:
        if contains in _para_text(p):
            return p
    return None


def _set_table_metadata(root: ET.Element) -> None:
    """Fill SoftareX v6 metadata table (C1–C8)."""
    values = {
        "C1": "0.1.0a1",
        "C2": "https://github.com/pedapudibhargav/ChromeRAG",
        "C3": "MIT",
        "C4": "git",
        "C5": "Python ≥3.11, BeautifulSoup4, lxml, Pydantic; optional ONNX Runtime",
        "C6": (
            "macOS / Linux / Windows; pip install -e . from the GitHub clone; "
            "optional extras: [dvdf], [fetch], [baselines], [ui]"
        ),
        "C7": "https://pedapudibhargav.github.io/ChromeRAG/ and repository README.md",
        "C8": "pedapudibhargav@gmail.com",
    }
    tbl = next(root.iter(f"{{{W_NS}}}tbl"))
    for tr in tbl.findall(f"{{{W_NS}}}tr", NS):
        cells = tr.findall(f"{{{W_NS}}}tc", NS)
        if len(cells) < 3:
            continue
        key = "".join(t.text or "" for t in cells[0].iter(f"{{{W_NS}}}t")).strip()
        if key in values:
            # clear and set third cell text
            # find first paragraph in cell
            p = cells[2].find(f"{{{W_NS}}}p", NS)
            if p is None:
                p = ET.SubElement(cells[2], f"{{{W_NS}}}p")
            _set_para_text(p, values[key])


def _replace_instruction_block(
    body: ET.Element,
    paras: list[ET.Element],
    heading_contains: str,
    next_heading_contains: str,
    paragraphs: list[str],
) -> None:
    """Replace italic instruction paras between two headings with content paragraphs."""
    start = None
    end = None
    for i, p in enumerate(paras):
        t = _para_text(p)
        if start is None and heading_contains in t and len(t) < 80:
            start = i
            continue
        if start is not None and next_heading_contains in t and len(t) < 120:
            end = i
            break
    if start is None or end is None:
        raise RuntimeError(f"Could not locate section '{heading_contains}' → '{next_heading_contains}'")

    # Keep heading at start; remove instruction paragraphs between heading and next heading
    to_remove = paras[start + 1 : end]
    for p in to_remove:
        body.remove(p)

    # Insert content after heading
    anchor = paras[start]
    for text in reversed(paragraphs):
        # insert right after heading repeatedly
        _clone_para_after(body, anchor, text, style="Body")


def main() -> None:
    if not TEMPLATE.exists():
        raise SystemExit(f"Missing template: {TEMPLATE}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TEMPLATE, OUT)

    # Work in a temp extract
    work = ROOT / "papers" / "softwarex" / "_docx_work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    with zipfile.ZipFile(TEMPLATE) as zf:
        zf.extractall(work)

    doc_xml = work / "word" / "document.xml"
    tree = ET.parse(doc_xml)
    root = tree.getroot()
    body = root.find(f"{{{W_NS}}}body")
    assert body is not None

    paras = [p for p in body.findall(f"{{{W_NS}}}p", NS)]

    # --- Title / authors / abstract / keywords ---
    title_p = _find_para(paras, "Title (Name of your software")
    if title_p is not None:
        _set_para_text(
            title_p,
            "ChromeRAG: Ingest-Time Elimination of Site Template Noise for Enterprise Web RAG",
        )

    authors_p = _find_para(paras, "Names of authors / main developers")
    if authors_p is not None:
        _set_para_text(
            authors_p,
            "Bhargava Chary Peddapudi (Independent Researcher; ORCID: https://orcid.org/0009-0002-8523-8415); "
            "Corresponding email: pedapudibhargav@gmail.com",
        )

    # Abstract: replace the ca.100 words instruction paragraph after Abstract heading
    abs_heading = _find_para(paras, "Abstract")
    ca100 = _find_para(paras, "ca. 100 words")
    if ca100 is not None:
        _set_para_text(
            ca100,
            (
                "Enterprise retrieval-augmented generation (RAG) pipelines often index scraped HTML whose "
                "navigation chrome, marketing banners, and footers pollute the vector space. Existing extractors "
                "such as Trafilatura and Readability are strong on news-like pages but under-serve SaaS "
                "documentation and pricing surfaces. ChromeRAG (chromerag) is a CPU-first Python toolkit that "
                "converts HTML to RAG-ready Markdown using site-template chrome elimination (STCE), optional "
                "density/vector noise pruning (DVDF), Schema.org front-matter fusion, and table key-value "
                "linearization. On a public corpus (373 URLs listed; 277 fetched; 238 scoreable), ChromeRAG "
                "coverage mode reaches Fbal 0.800 versus Trafilatura 0.752 and MarkItDown 0.695. Thin or "
                "JavaScript-shell inputs emit operator warnings so callers can verify their fetch/render "
                "pipeline. The software is MIT-licensed with a CLI, static Compare Lab, and reproducible "
                "benchmark scripts."
            ),
        )
    # Remove the six-page instruction paragraph after abstract if present
    six = _find_para(paras, "Your main body of text (Sections 1-5")
    if six is not None:
        body.remove(six)

    kw = _find_para(paras, "maximum of six")
    if kw is not None:
        _set_para_text(
            kw,
            "RAG; HTML extraction; boilerplate removal; vector pollution; Markdown; enterprise search",
        )
    # SoftareX v6 sometimes keeps Keywords heading + separate italic instruction
    for p in list(paras):
        if _para_text(p).strip() == "(maximum of six)":
            _set_para_text(
                p,
                "RAG; HTML extraction; boilerplate removal; vector pollution; Markdown; enterprise search",
            )

    _set_table_metadata(root)

    # Refresh para list after removals for section fills
    paras = [p for p in body.findall(f"{{{W_NS}}}p", NS)]

    motivation = [
        (
            "Modern enterprise assistants retrieve over documentation hubs, knowledge bases, and marketing "
            "sites. When those pages are ingested with generic HTML-to-text converters, shared chrome "
            "(nav, footer, CTAs, cookie banners) is embedded repeatedly. The result is vector pollution: "
            "near-duplicate chrome chunks compete with factual content at query time."
        ),
        (
            "Prior extractors optimize for news article main-content (Trafilatura, Readability) or general "
            "Markdown conversion (MarkItDown, markdownify). They do not jointly provide: (i) learn-then-extract "
            "site chrome models across a corporate domain, (ii) Schema.org JSON-LD injected as YAML front-matter "
            "for chunk context, and (iii) pricing/spec table linearization for RAG. ChromeRAG targets that gap "
            "as ingest-time, query-agnostic software—orthogonal to query-time HtmlRAG pruning."
        ),
        (
            "Experimental setting: users fetch or crawl HTML with their own pipeline (or the optional poc/ "
            "harness), then run chromerag extract / learn / batch to produce RAG-ready Markdown. On thin or "
            "JavaScript-rendered shells, ChromeRAG emits warnings instructing callers to Playwright-render "
            "first rather than silently averaging empty pages into evaluation means."
        ),
        (
            "Related work includes Trafilatura, readability-lxml, MarkItDown, and query-time HtmlRAG pruning. "
            "ChromeRAG’s contribution is a reusable ingest toolkit with deterministic Recall / Noise / Fbal "
            "benchmarks on a public multi-category corpus."
        ),
    ]
    _replace_instruction_block(body, paras, "Motivation and significance", "Software description", motivation)

    paras = [p for p in body.findall(f"{{{W_NS}}}p", NS)]
    software = [
        (
            "ChromeRAG converts an HTML string into RAG-ready Markdown. Architecture: (1) input-quality check "
            "for thin/JS shells; (2) Schema.org harvest before script strip; (3) deterministic clean plus "
            "optional site-template chrome elimination (STCE); (4) optional density/DVDF leaf prune; "
            "(5) heading-safe Markdown with YAML front-matter; (6) optional table key-value linearization."
        ),
        (
            "Major functionalities: chromerag extract (priority knobs precision/coverage/balanced), "
            "chromerag learn (mine site-chrome models), chromerag batch (learn-then-extract), optional DVDF "
            "via [dvdf], and a static Compare Lab under docs/ for GitHub Pages."
        ),
        (
            "Sample usage: pip install -e \".[baselines]\"; chromerag extract page.html -o out.md "
            "--priority coverage --json-meta. Python: ChromeRAG(...).extract(html, url=...) returns "
            "markdown, front_matter, and warnings."
        ),
    ]
    _replace_instruction_block(body, paras, "Software description", "Illustrative examples", software)

    paras = [p for p in body.findall(f"{{{W_NS}}}p", NS)]
    examples = [
        (
            "On 238 scoreable pages (277 fetched; 373 URLs listed), ChromeRAG coverage reaches content recall "
            "0.701, noise retention 0.005, and Fbal 0.800, versus Trafilatura (0.662 / 0.019 / 0.752) and "
            "MarkItDown (0.702 / 0.261 / 0.695). Metrics use structural main/article vs nav/footer anchors. "
            "Figures 1–4 (papers/softwarex/figures/) show Fbal, recall, noise retention, and the corpus "
            "honesty gate (listed → fetched → scoreable/thin)."
        ),
        (
            "Priority knobs trade recall vs noise. Passing a near-empty div id=root shell prints a stderr "
            "WARNING that the caller must render first—reviewers should trust that disclosure more than a "
            "table that silently averages those failures."
        ),
    ]
    _replace_instruction_block(body, paras, "Illustrative examples", "Impact", examples)

    paras = [p for p in body.findall(f"{{{W_NS}}}p", NS)]
    impact = [
        (
            "ChromeRAG enables new evaluation questions about ingest-time chrome pollution versus converter "
            "token counts alone, using Recall, Noise retention, and Fbal on corporate docs/pricing/marketing "
            "HTML."
        ),
        (
            "It improves existing RAG corpus construction by cutting chrome retention (~0.005 vs ~0.26 for "
            "MarkItDown-class converters) while keeping documentation and table facts, and by injecting "
            "Schema.org identity into chunk front-matter."
        ),
        (
            "Daily practice: practitioners wire chromerag into loaders and ETL jobs; input-quality warnings "
            "surface broken fetch/render pipelines before vectors are indexed."
        ),
        (
            "The software is newly released as open source on GitHub under MIT; adoption metrics will grow "
            "with the public repository and Compare Lab. Commercial use is intended as a library dependency "
            "inside private RAG stacks rather than a hosted SaaS."
        ),
        (
            "Limitations stated for honesty: ChromeRAG does not execute JavaScript; thin pages (39 of 277) "
            "are excluded from leaderboard means via a scoreable hygiene gate (recall ≥ 0.05), with both "
            "counts reported; anchors are structural heuristics, not human gold."
        ),
    ]
    _replace_instruction_block(body, paras, "Impact", "Conclusions", impact)

    paras = [p for p in body.findall(f"{{{W_NS}}}p", NS)]
    conclusions = [
        (
            "ChromeRAG packages ingest-time chrome elimination, optional vector density pruning, schema "
            "front-matter, table linearization, and input-quality warnings into a MIT-licensed Python CLI. "
            "On 238 scoreable public pages, coverage mode reaches Fbal 0.800 vs Trafilatura 0.752 and "
            "MarkItDown 0.695, mainly by cutting chrome retention. Future work includes page-type adaptive "
            "profiles and Chrome Centroid Drift metrics."
        ),
    ]
    # Conclusions → Acknowledgements or References
    next_h = "Acknowledgements"
    if _find_para(paras, "Acknowledgements") is None:
        next_h = "References"
    _replace_instruction_block(body, paras, "Conclusions", next_h, conclusions)

    # Acknowledgements: optional none
    paras = [p for p in body.findall(f"{{{W_NS}}}p", NS)]
    ack = _find_para(paras, "Optional. You can use this section to acknowledge")
    if ack is not None:
        _set_para_text(ack, "None.")

    # References
    paras = [p for p in body.findall(f"{{{W_NS}}}p", NS)]
    ref1 = _find_para(paras, "Use this style of ordering")
    if ref1 is not None:
        _set_para_text(
            ref1,
            "[1] A. Barbaresi, Trafilatura: A Web Scraping Library and Toolkit for Texts for Computational "
            "Linguistics, Proceedings of the ACL System Demonstrations, 2021.",
        )
    ref_pid = _find_para(paras, "If the software repository you used supplied a DOI")
    if ref_pid is not None:
        _set_para_text(
            ref_pid,
            "[2] B. C. Peddapudi, ChromeRAG, GitHub repository, https://github.com/pedapudibhargav/ChromeRAG "
            "(accessed 2026).",
        )
        # Add a couple more refs after
        _clone_para_after(
            body,
            ref_pid,
            "[3] Microsoft, MarkItDown: Python tool for converting files and office documents to Markdown, "
            "https://github.com/microsoft/markitdown (accessed 2026).",
            style="Body",
        )

    # Delete everything above the separator line (instructions)
    paras = [p for p in body.findall(f"{{{W_NS}}}p", NS)]
    sep = None
    for p in paras:
        t = _para_text(p).strip()
        if t.startswith("- - -") or (t.count("-") > 40 and len(t) < 120):
            sep = p
            break
    if sep is not None:
        for p in list(body.findall(f"{{{W_NS}}}p", NS)):
            if p is sep:
                body.remove(p)
                break
            body.remove(p)
            if p is sep:
                break
        # remove until sep inclusive — redo carefully
    # Re-parse approach for separator cleanup
    paras = [p for p in body.findall(f"{{{W_NS}}}p", NS)]
    sep_idx = None
    for i, p in enumerate(paras):
        t = _para_text(p).strip()
        if t.startswith("- - -") or (t.count("-") > 40 and "Title" not in t):
            # only early separator
            if i < 20:
                sep_idx = i
                break
    if sep_idx is not None:
        for p in paras[: sep_idx + 1]:
            if p in list(body):
                body.remove(p)

    # Remove final reminder italics
    for p in list(body.findall(f"{{{W_NS}}}p", NS)):
        t = _para_text(p)
        if "Reminder: Before you submit" in t or "including this paragraph" in t or t.strip() == "Thank you!":
            body.remove(p)
        if "the instructions in this document" in t:
            body.remove(p)

    # Delete Metadata instruction heading leftovers that are pure instructions
    for p in list(body.findall(f"{{{W_NS}}}p", NS)):
        t = _para_text(p)
        if "This ancillary data table is required" in t:
            body.remove(p)
        if t.strip() == "Metadata" and "code" not in t.lower():
            # keep short Metadata heading if it's the section title - SoftareX uses Heading1 Metadata
            pass

    tree.write(doc_xml, encoding="UTF-8", xml_declaration=True)

    # Repack docx
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in work.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(work).as_posix())

    shutil.rmtree(work)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
