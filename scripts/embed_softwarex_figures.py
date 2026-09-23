#!/usr/bin/env python3
"""Embed SoftareX figures into existing placeholder paragraphs (no new w:p nodes)."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
DOCX = ROOT / "papers" / "softwarex" / "ChromeRAG_SoftwareX_OSP.docx"
FIGS = ROOT / "papers" / "softwarex" / "figures"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"

W, R, A, WP, PIC = f"{{{W_NS}}}", f"{{{R_NS}}}", f"{{{A_NS}}}", f"{{{WP_NS}}}", f"{{{PIC_NS}}}"

IMAGES = [
    (
        "fig0_architecture.png",
        "Figure 1. ChromeRAG processing pipeline. The optional site model produced by "
        "chromerag learn is applied in stage 3.",
    ),
    (
        "fig1_fbal.png",
        "Figure 2. Balanced F-score (Fbal, higher is better) on the 250 scoreable pages; "
        "every method is averaged over the same pages.",
    ),
    ("fig2_recall.png", "Figure 3. Content recall on the same 250 pages (higher is better)."),
    (
        "fig3_noise.png",
        "Figure 4. Noise retention, the share of navigation/footer anchors kept "
        "(lower is better), on the same 250 pages.",
    ),
    (
        "fig4_corpus_gate.png",
        "Figure 5. Benchmark corpus funnel. The scoreable cohort is selected from the input "
        "HTML only (at least 50 main-content anchors), never from any extractor's output.",
    ),
]

TEXT_WIDTH_EMU = 5943600  # 6.5 in


def _png_size(path: Path) -> tuple[int, int]:
    import struct

    with path.open("rb") as f:
        head = f.read(24)
    width, height = struct.unpack(">II", head[16:24])
    return width, height

_NEXT_ID = 0xD000


def _fresh_hex_id() -> str:
    global _NEXT_ID
    _NEXT_ID += 1
    return f"{_NEXT_ID:08X}"


def _para_text(p: etree._Element) -> str:
    return "".join(t.text or "" for t in p.iter(f"{W}t"))


def _drawing(rid: str, cx: int, cy: int, name: str, *, doc_id: int) -> etree._Element:
    drawing = etree.Element(f"{W}drawing")
    inline = etree.SubElement(drawing, f"{WP}inline", distT="0", distB="0", distL="0", distR="0")
    etree.SubElement(inline, f"{WP}extent", cx=str(cx), cy=str(cy))
    etree.SubElement(inline, f"{WP}docPr", id=str(doc_id), name=name)
    cNv = etree.SubElement(inline, f"{WP}cNvGraphicFramePr")
    etree.SubElement(cNv, f"{A}graphicFrameLocks", noChangeAspect="1")
    graphic = etree.SubElement(inline, f"{A}graphic")
    graphic_data = etree.SubElement(
        graphic,
        f"{A}graphicData",
        uri="http://schemas.openxmlformats.org/drawingml/2006/picture",
    )
    pic = etree.SubElement(graphic_data, f"{PIC}pic")
    nv = etree.SubElement(pic, f"{PIC}nvPicPr")
    etree.SubElement(nv, f"{PIC}cNvPr", id=str(doc_id), name=name)
    etree.SubElement(nv, f"{PIC}cNvPicPr")
    blip_fill = etree.SubElement(pic, f"{PIC}blipFill")
    blip = etree.SubElement(blip_fill, f"{A}blip")
    blip.set(f"{R}embed", rid)
    stretch = etree.SubElement(blip_fill, f"{A}stretch")
    etree.SubElement(stretch, f"{A}fillRect")
    sp_pr = etree.SubElement(pic, f"{PIC}spPr")
    xfrm = etree.SubElement(sp_pr, f"{A}xfrm")
    etree.SubElement(xfrm, f"{A}off", x="0", y="0")
    etree.SubElement(xfrm, f"{A}ext", cx=str(cx), cy=str(cy))
    prst = etree.SubElement(sp_pr, f"{A}prstGeom", prst="rect")
    etree.SubElement(prst, f"{A}avLst")
    return drawing


def _set_caption(p: etree._Element, text: str) -> None:
    pPr = p.find(f"{W}pPr")
    for child in list(p):
        if child is not pPr:
            p.remove(child)
    run = etree.SubElement(p, f"{W}r")
    rPr = etree.SubElement(run, f"{W}rPr")
    etree.SubElement(rPr, f"{W}i")
    t = etree.SubElement(run, f"{W}t")
    t.text = text


def _set_image_para(p: etree._Element, drawing: etree._Element) -> None:
    pPr = p.find(f"{W}pPr")
    for child in list(p):
        if child is not pPr:
            p.remove(child)
    run = etree.SubElement(p, f"{W}r")
    run.append(drawing)


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
    rels_tree = etree.parse(str(rels_path))
    rels_root = rels_tree.getroot()
    existing_ids = [
        int((r.get("Id") or "rId0").replace("rId", "") or 0)
        for r in rels_root
        if (r.get("Id") or "").startswith("rId")
    ]
    next_id = max(existing_ids or [1]) + 1

    doc_path = work / "word" / "document.xml"
    doc_tree = etree.parse(str(doc_path))
    body = doc_tree.getroot().find(f"{W}body")
    assert body is not None

    by_marker: dict[str, etree._Element] = {}
    for p in body.findall(f"{W}p"):
        t = _para_text(p).strip()
        if t.startswith("__FIG") and t.endswith("__"):
            by_marker[t] = p

    for i, (fname, caption) in enumerate(IMAGES):
        n = i + 1
        img_p = by_marker.get(f"__FIG{n}_IMG__")
        cap_p = by_marker.get(f"__FIG{n}_CAP__")
        if img_p is None or cap_p is None:
            raise SystemExit(f"Missing figure placeholders for figure {n}")
        src = FIGS / fname
        if not src.exists():
            raise SystemExit(f"Missing {src}")
        dest_name = f"image{n}.png"
        shutil.copy2(src, media / dest_name)
        rid = f"rId{next_id}"
        next_id += 1
        rel = etree.SubElement(rels_root, f"{{{REL_NS}}}Relationship")
        rel.set("Id", rid)
        rel.set(
            "Type",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
        )
        rel.set("Target", f"media/{dest_name}")
        px_w, px_h = _png_size(src)
        cx = TEXT_WIDTH_EMU
        cy = int(cx * px_h / px_w)
        _set_image_para(img_p, _drawing(rid, cx, cy, fname, doc_id=n))
        _set_caption(cap_p, caption)

    ct_path = work / "[Content_Types].xml"
    ct_tree = etree.parse(str(ct_path))
    ct_root = ct_tree.getroot()
    if not any((el.get("Extension") or "").lower() == "png" for el in ct_root):
        defn = etree.SubElement(ct_root, f"{{{CT_NS}}}Default")
        defn.set("Extension", "png")
        defn.set("ContentType", "image/png")

    doc_root = doc_tree.getroot()
    for el in doc_root.iter():
        for attr in list(el.attrib):
            local = etree.QName(attr).localname if attr.startswith("{") else attr
            if local.lower().startswith("rsid"):
                del el.attrib[attr]
    for pPr in doc_root.findall(f".//{W}pPr"):
        pPr.set(f"{W14}paraId", _fresh_hex_id())
        pPr.set(f"{W14}textId", _fresh_hex_id())

    nsmap = dict(doc_root.nsmap)
    missing = {
        k: v
        for k, v in {"wp": WP_NS, "a": A_NS, "pic": PIC_NS, "r": R_NS}.items()
        if k not in nsmap or nsmap[k] != v
    }
    doc_tree.write(str(doc_path), xml_declaration=True, encoding="UTF-8", standalone=True)
    text = doc_path.read_text(encoding="utf-8")
    if text.startswith("<?xml"):
        text = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + text.split("?>", 1)[1].lstrip("\n")
    if missing:
        inject = " ".join(f'xmlns:{k}="{v}"' for k, v in missing.items())
        text = text.replace("<w:document ", f"<w:document {inject} ", 1)
    doc_path.write_text(text, encoding="utf-8")

    rels_tree.write(str(rels_path), xml_declaration=True, encoding="UTF-8", standalone=True)
    ct_tree.write(str(ct_path), xml_declaration=True, encoding="UTF-8", standalone=True)
    for path, uri in ((rels_path, REL_NS), (ct_path, CT_NS)):
        raw = path.read_text(encoding="utf-8")
        if raw.startswith("<?xml"):
            raw = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + raw.split("?>", 1)[1].lstrip("\n")
        raw = raw.replace(f'xmlns:ns0="{uri}"', f'xmlns="{uri}"').replace("<ns0:", "<").replace("</ns0:", "</")
        path.write_text(raw, encoding="utf-8")

    DOCX.unlink()
    with zipfile.ZipFile(DOCX, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in work.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(work).as_posix())
    shutil.rmtree(work)
    print(f"Embedded {len(IMAGES)} figures into existing placeholders in {DOCX}")


if __name__ == "__main__":
    main()
