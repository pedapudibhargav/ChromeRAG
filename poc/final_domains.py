"""Load registrable domains excluded from the P04 final page set."""

from __future__ import annotations

import csv
from pathlib import Path

from poc.psl import load_psl, registrable_domain

INVENTORY_SETS = frozenset(
    {
        "WCXB dev",
        "WCXB test",
        "extra_raw",
        "extra_raw_final",
        "extra_raw_final2",
        "golden corpus",
        "landing",
        "landing fresh",
        "site crawl",
        "CRAG split 0",
    }
)


def load_inventory_excluded_domains(csv_path: Path) -> frozenset[str]:
    """Return registrable domains from selected inventory sets (column: domain)."""
    path = Path(csv_path)
    out: set[str] = set()
    psl = load_psl()
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row.get("set") not in INVENTORY_SETS:
                continue
            raw = (row.get("domain") or "").strip().lower()
            if raw:
                out.add(raw)
                rd_dom = registrable_domain(raw, psl) or registrable_domain(f"https://{raw}/", psl)
                if rd_dom:
                    out.add(rd_dom)
            url = (row.get("url") or "").strip()
            if url:
                rd = registrable_domain(url, psl)
                if rd:
                    out.add(rd)
    return frozenset(out)


def load_wcxb_tree_domains(wcxb_root: Path) -> frozenset[str]:
    """Registrable domains from page metadata under a WCXB data tree (if present)."""
    root = Path(wcxb_root)
    if not root.is_dir():
        return frozenset()
    psl = load_psl()
    found: set[str] = set()
    for meta in root.rglob("*.meta.json"):
        try:
            import json

            data = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for key in ("url", "requested_url"):
            val = data.get(key)
            if val:
                rd = registrable_domain(str(val), psl)
                if rd:
                    found.add(rd)
    return frozenset(found)


def merged_excluded_domains(*parts: frozenset[str]) -> frozenset[str]:
    out: set[str] = set()
    for p in parts:
        out.update(p)
    return frozenset(out)
