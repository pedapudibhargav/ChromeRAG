"""Key-value table linearization for chunk-safe RAG ingestion."""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag

from chromerag.domutil import tags_named

_MAX_PIPE_COLS = 12
_MAX_PIPE_ROWS = 200


def _cell_text(cell: Tag) -> str:
    return " ".join(cell.get_text(" ", strip=True).split())


def _cell_span(cell: Tag, attr: str) -> int:
    raw = cell.get(attr)
    if raw is None:
        return 1
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 1


def _escape_pipe_cell(text: str) -> str:
    return text.replace("|", "\\|")


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


def _table_grid(table: Tag) -> tuple[list[str], list[list[str]]]:
    """Return header labels and body rows as plain cell text."""
    rows = _own_rows(table)
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
    return headers, body_rows


def _has_merged_cells(table: Tag) -> bool:
    for cell in table.find_all(["td", "th"]):
        if _cell_span(cell, "colspan") > 1 or _cell_span(cell, "rowspan") > 1:
            return True
    return False


def _cell_is_single_line(text: str) -> bool:
    return "\n" not in text and "\r" not in text


def can_render_pipe_table(table: Tag) -> bool:
    """True when the table is a small rectangular grid suitable for GFM pipe output."""
    if is_layout_table(table) or _has_merged_cells(table):
        return False
    rows = _own_rows(table)
    if not rows or len(rows) > _MAX_PIPE_ROWS:
        return False
    headers, body_rows = _table_grid(table)
    if headers:
        ncols = len(headers)
        if ncols > _MAX_PIPE_COLS:
            return False
        if not all(_cell_is_single_line(h) for h in headers):
            return False
    elif body_rows:
        ncols = len(body_rows[0])
        if ncols > _MAX_PIPE_COLS:
            return False
    else:
        return False

    for row in body_rows:
        if len(row) != ncols:
            return False
        if not all(_cell_is_single_line(c) for c in row):
            return False
    return bool(headers or body_rows)


def render_pipe_table(table: Tag) -> str:
    headers, body_rows = _table_grid(table)
    lines: list[str] = []
    if headers:
        lines.append("| " + " | ".join(_escape_pipe_cell(h) for h in headers) + " |")
        lines.append("| " + " | ".join("---" for _ in headers) + " |")
        for row in body_rows:
            if not any(row):
                continue
            lines.append("| " + " | ".join(_escape_pipe_cell(c) for c in row) + " |")
    else:
        for row in body_rows:
            if not any(row):
                continue
            lines.append("| " + " | ".join(_escape_pipe_cell(c) for c in row) + " |")
    return "\n".join(lines)


def linearize_table(table: Tag, index: int = 1) -> str:
    caption = table.find("caption")
    title = caption.get_text(" ", strip=True) if caption else f"Table {index}"

    headers, body_rows = _table_grid(table)
    if not headers and not body_rows:
        return ""

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


def format_table(table: Tag, index: int = 1, *, table_format: str = "markdown") -> str:
    if table_format == "markdown" and can_render_pipe_table(table):
        text = render_pipe_table(table)
        if text:
            return text
    return linearize_table(table, index=index)


def unwrap_layout_tables(soup: BeautifulSoup) -> int:
    """Turn layout tables into plain divs so their content is scored like any other block."""
    count = 0
    for table in tags_named(soup, ("table",)):
        if table.attrs is not None and is_layout_table(table):
            _unwrap_layout_table(table)
            count += 1
    return count


def replace_tables_with_linearized(
    soup: BeautifulSoup,
    *,
    table_format: str = "markdown",
) -> int:
    """Replace each <table> with a <pre> of table text. Returns count."""
    count = 0
    for i, table in enumerate(tags_named(soup, ("table",)), start=1):
        if table.attrs is None:
            continue
        if is_layout_table(table):
            _unwrap_layout_table(table)
            continue
        text = format_table(table, index=i, table_format=table_format)
        if not text:
            table.decompose()
            continue
        pre = soup.new_tag("pre")
        pre.string = text
        table.replace_with(pre)
        count += 1
    return count
