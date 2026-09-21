"""Key-value table linearization for chunk-safe RAG ingestion."""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag


def _cell_text(cell: Tag) -> str:
    return " ".join(cell.get_text(" ", strip=True).split())


def linearize_table(table: Tag, index: int = 1) -> str:
    caption = table.find("caption")
    title = caption.get_text(" ", strip=True) if caption else f"Table {index}"

    rows = table.find_all("tr")
    if not rows:
        return ""

    headers: list[str] = []
    body_rows: list[list[str]] = []
    header_row = table.find("thead")
    if header_row:
        ths = header_row.find_all(["th", "td"])
        headers = [_cell_text(c) for c in ths]
        data_trs = table.find("tbody").find_all("tr") if table.find("tbody") else []
        if not data_trs:
            data_trs = [tr for tr in rows if tr.find_parent("thead") is None]
    else:
        first = rows[0]
        cells = first.find_all(["th", "td"])
        if first.find("th") or all(c.name == "th" for c in cells):
            headers = [_cell_text(c) for c in cells]
            data_trs = rows[1:]
        else:
            data_trs = rows

    for tr in data_trs:
        body_rows.append([_cell_text(c) for c in tr.find_all(["td", "th"])])

    lines = [f"[Table: {title}]"]
    for i, row in enumerate(body_rows, start=1):
        if not any(row):
            continue
        if headers and len(headers) == len(row):
            pairs = [f"{h}: {v}" for h, v in zip(headers, row) if h or v]
            lines.append(f"Row {i} -> " + " | ".join(pairs))
        elif headers and len(headers) > 0:
            pairs = []
            for idx, v in enumerate(row):
                h = headers[idx] if idx < len(headers) else f"col{idx+1}"
                pairs.append(f"{h}: {v}")
            lines.append(f"Row {i} -> " + " | ".join(pairs))
        else:
            lines.append(f"Row {i} -> " + " | ".join(row))
    return "\n".join(lines)


def replace_tables_with_linearized(soup: BeautifulSoup) -> int:
    """Replace each <table> with a <pre> of linearized KV text. Returns count."""
    count = 0
    for i, table in enumerate(list(soup.find_all("table")), start=1):
        text = linearize_table(table, index=i)
        if not text:
            table.decompose()
            continue
        pre = soup.new_tag("pre")
        pre.string = text
        table.replace_with(pre)
        count += 1
    return count
