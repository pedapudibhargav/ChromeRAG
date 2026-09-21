#!/usr/bin/env python3
"""Embed SoftareX figure PNGs into ChromeRAG_SoftwareX_OSP.docx (stdlib only)."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DOCX = ROOT / "papers" / "softwarex" / "ChromeRAG_SoftwareX_OSP.docx"
FIGS = ROOT / "papers" / "softwarex" / "figures"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

ET.register_namespace("w", W_NS)
ET.register_namespace("r", R_NS)
ET.register_namespace("a", A_NS)
ET.register_namespace("wp", WP_NS)
ET.register_namespace("pic", PIC_NS)
ET.register_namespace("", REL_NS)

IMAGES = [
    ("fig1_fbal.png", "Figure 1. Fbal on 238 scoreable pages."),
    ("fig2_recall.png", "Figure 2. Content recall on the same scoreable set."),
    ("fig3_noise.png", "Figure 3. Noise retention (lower is better)."),
    ("fig4_corpus_gate.png", "Figure 4. Corpus honesty gate: listed → fetched → scoreable / thin."),
]


def _drawing(rid: str, cx: int, cy: int, name: str) -> ET.Element:
    # Minimal inline drawing
    drawing = ET.Element(f"{{{W_NS}}}drawing")
    inline = ET.SubElement(drawing, f"{{{WP_NS}}}inline")
    inline.set("distT", "0")
    inline.set("distB", "0")
    inline.set("distL", "0")
    inline.set("distR", "0")
    extent = ET.SubElement(inline, f"{{{WP_NS}}}extent")
    extent.set("cx", str(cx))
    extent.set("cy", str(cy))
    docPr = ET.SubElement(inline, f"{{{WP_NS}}}docPr")
    docPr.set("id", "1")
    docPr.set("name", name)
    graphic = ET.SubElement(inline, f"{{{A_NS}}}graphic")
    graphicData = ET.SubElement(graphic, f"{{{A_NS}}}graphicData")
    graphicData.set("uri", "http://schemas.openxmlformats.org/drawingml/2006/picture")
    pic = ET.SubElement(graphicData, f"{{{PIC_NS}}}pic")
    nv = ET.SubElement(pic, f"{{{PIC_NS}}}nvPicPr")
    cNvPr = ET.SubElement(nv, f"{{{PIC_NS}}}cNvPr")
    cNvPr.set("id", "0")
    cNvPr.set("name", name)
    ET.SubElement(nv, f"{{{PIC_NS}}}cNvPicPr")
    blipFill = ET.SubElement(pic, f"{{{PIC_NS}}}blipFill")
    blip = ET.SubElement(blipFill, f"{{{A_NS}}}blip")
    blip.set(f"{{{R_NS}}}embed", rid)
    stretch = ET.SubElement(blipFill, f"{{{A_NS}}}stretch")
    ET.SubElement(stretch, f"{{{A_NS}}}fillRect")
    spPr = ET.SubElement(pic, f"{{{PIC_NS}}}spPr")
    xfrm = ET.SubElement(spPr, f"{{{A_NS}}}xfrm")
    off = ET.SubElement(xfrm, f"{{{A_NS}}}off")
    off.set("x", "0")
    off.set("y", "0")
    ext = ET.SubElement(xfrm, f"{{{A_NS}}}ext")
    ext.set("cx", str(cx))
    ext.set("cy", str(cy))
    prst = ET.SubElement(spPr, f"{{{A_NS}}}prstGeom")
    prst.set("prst", "rect")
    ET.SubElement(prst, f"{{{A_NS}}}avLst")
    return drawing


def main() -> None:
    if not DOCX.exists():
        raise SystemExit(f"Missing {DOCX}")
    work = ROOT / "papers" / "softwarex" / "_docx_embed"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    with zipfile.ZipFile(DOCX) as zf:
        zf.extractall(work)

    media = work / "word" / "media"
    media.mkdir(parents=True, exist_ok=True)

    rels_path = work / "word" / "_rels" / "document.xml.rels"
    rels = ET.parse(rels_path)
    rels_root = rels.getroot()
    existing_ids = [
        int(r.get("Id", "rId0").replace("rId", "") or 0)
        for r in rels_root
        if (r.get("Id") or "").startswith("rId")
    ]
    next_id = max(existing_ids or [1]) + 1

    doc_path = work / "word" / "document.xml"
    doc = ET.parse(doc_path)
    body = doc.getroot().find(f"{{{W_NS}}}body")
    assert body is not None

    # Find Illustrative examples heading; insert figures before Impact
    paras = list(body.findall(f"{{{W_NS}}}p"))
    insert_before = None
    for p in paras:
        text = "".join(t.text or "" for t in p.iter(f"{{{W_NS}}}t"))
        if text.strip() == "Impact":
            insert_before = p
            break
    if insert_before is None:
        raise SystemExit("Could not find Impact heading")

    children = list(body)
    idx = children.index(insert_before)

    # EMUs: 914400 per inch; ~6.5" wide
    cx, cy = 5943600, 3439800

    for i, (fname, caption) in enumerate(IMAGES):
        src = FIGS / fname
        if not src.exists():
            raise SystemExit(f"Missing figure {src}")
        dest_name = f"image{i+1}.png"
        shutil.copy2(src, media / dest_name)
        rid = f"rId{next_id}"
        next_id += 1
        rel = ET.SubElement(rels_root, f"{{{REL_NS}}}Relationship")
        rel.set("Id", rid)
        rel.set(
            "Type",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
        )
        rel.set("Target", f"media/{dest_name}")

        # figure paragraph
        p_fig = ET.Element(f"{{{W_NS}}}p")
        r = ET.SubElement(p_fig, f"{{{W_NS}}}r")
        r.append(_drawing(rid, cx, cy if i < 3 else 2376000, fname))
        body.insert(idx, p_fig)
        idx += 1

        # caption
        p_cap = ET.Element(f"{{{W_NS}}}p")
        pPr = ET.SubElement(p_cap, f"{{{W_NS}}}pPr")
        ps = ET.SubElement(pPr, f"{{{W_NS}}}pStyle")
        ps.set(f"{{{W_NS}}}val", "Body")
        run = ET.SubElement(p_cap, f"{{{W_NS}}}r")
        rPr = ET.SubElement(run, f"{{{W_NS}}}rPr")
        ET.SubElement(rPr, f"{{{W_NS}}}i")
        t = ET.SubElement(run, f"{{{W_NS}}}t")
        t.text = caption
        body.insert(idx, p_cap)
        idx += 1

    # Content types for png
    ct_path = work / "[Content_Types].xml"
    ct = ET.parse(ct_path)
    ct_root = ct.getroot()
    CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
    ET.register_namespace("", CT_NS)
    has_png = any(
        (el.get("Extension") or "").lower() == "png" for el in ct_root
    )
    if not has_png:
        defn = ET.SubElement(ct_root, f"{{{CT_NS}}}Default")
        defn.set("Extension", "png")
        defn.set("ContentType", "image/png")
    ct.write(ct_path, encoding="UTF-8", xml_declaration=True)
    rels.write(rels_path, encoding="UTF-8", xml_declaration=True)
    doc.write(doc_path, encoding="UTF-8", xml_declaration=True)

    DOCX.unlink()
    with zipfile.ZipFile(DOCX, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in work.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(work).as_posix())
    shutil.rmtree(work)
    print(f"Embedded {len(IMAGES)} figures into {DOCX}")


if __name__ == "__main__":
    main()
