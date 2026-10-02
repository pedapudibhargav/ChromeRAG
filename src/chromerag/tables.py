"""Key-value table linearization for chunk-safe RAG ingestion."""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag

from chromerag.domutil import tags_named


def _cell_text(cell: Tag) -> str:
    return " ".join(cell.get_text(" ", strip=True).split())


_BLOCK_IN_CELL = ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "blockquote", "pre", "table")
_TABLE_PARTS = ("table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption")
_LAYOUT_MIN_PROSE_CELLS = 1


def _own_rows(table: Tag) -> list[Tag]:
    """Rows that belong to ``table`` itself, not to a table nested inside it."""
    return [tr for tr in table.find_all("tr") if tr.find_parent("table") is table]


def is_layout_table(table: Tag) -> bool:
    """A table used to position page elements, not to hold tabular data.

    It has a nested table, or a cell with block content (paragraphs, headings, lists), or a
    cell holding a long run of text. Data tables keep short text in their cells.
    """
    if table.find("table"):
        return True
    if table.find("th") or table.find("caption") or table.find("thead"):
        return False
    for cell in table.find_all(["td", "th"]):
        if cell.find(_BLOCK_IN_CELL):
            return True
        if len(cell.get_text(" ", strip=True)) > 300:
            return True
    return False


def _unwrap_layout_table(table: Tag) -> None:
    for part in [table, *table.find_all(_TABLE_PARTS)]:
        if part.find_parent("table") is table or part is table:
            part.name = "div"


def linearize_table(table: Tag, index: int = 1) -> str:
    caption = table.find("caption")
    title = caption.get_text(" ", strip=True) if caption else f"Table {index}"

    rows = _own_rows(table)
    if not rows:
        return ""

    headers: list[str] = []
    body_rows: list[list[str]] = []
    header_row = table.find("thead")
    if header_row:
        ths = header_row.find_all(["th", "td"])
        headers = [_cell_text(c) for c in ths]
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


def unwrap_layout_tables(soup: BeautifulSoup) -> int:
    """Turn layout tables into plain divs so their content is scored like any other block."""
    count = 0
    for table in tags_named(soup, ("table",)):
        if table.attrs is not None and is_layout_table(table):
            _unwrap_layout_table(table)
            count += 1
    return count


def replace_tables_with_linearized(soup: BeautifulSoup) -> int:
    """Replace each <table> with a <pre> of linearized KV text. Returns count."""
    count = 0
    for i, table in enumerate(tags_named(soup, ("table",)), start=1):
        if table.attrs is None:
            continue
        if is_layout_table(table):
            _unwrap_layout_table(table)
            continue
        text = linearize_table(table, index=i)
        if not text:
            table.decompose()
            continue
        pre = soup.new_tag("pre")
        pre.string = text
        table.replace_with(pre)
        count += 1
    return count
