"""Scan fetched HTML for JSON-LD / microdata richness."""

from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup

from chromerag.schema_fusion import fuse_front_matter, parse_json_ld, parse_microdata

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"


def main() -> None:
    rows = []
    for meta_path in sorted(RAW.glob("*.meta.json")):
        if meta_path.name.startswith("_"):
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        html = (RAW / f"{meta['id']}.html").read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(html, "lxml")
        ld = parse_json_ld(soup)
        md = parse_microdata(soup)
        fm = fuse_front_matter(soup, url=meta.get("url"))
        row = {
            "id": meta["id"],
            "url": meta.get("url"),
            "json_ld_count": len(ld),
            "json_ld_types": sorted({str(n.get("@type")) for n in ld}),
            "microdata_count": len(md),
            "microdata_types": sorted({str(n.get("@type")) for n in md}),
            "front_matter_keys": sorted(k for k in fm if not str(k).startswith("_")),
            "title": fm.get("title"),
            "type": fm.get("type"),
        }
        rows.append(row)
        print(
            f"{row['id']:24s} jsonld={row['json_ld_count']:2d} "
            f"micro={row['microdata_count']:2d} type={row.get('type')} title={str(row.get('title'))[:60]}"
        )
    out = ROOT / "data" / "outputs" / "schema_scan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
