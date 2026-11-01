"""Key-value table linearization for chunk-safe RAG ingestion."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from chromerag.density import NOISE_TOKENS, _attr_tokens
from chromerag.domutil import tags_named

_MAX_PIPE_COLS = 12
_MAX_PIPE_ROWS = 200
# Hard caps so pathological tables stay time-safe (truncate + caller may warn).
_MAX_EMIT_ROWS = 100_000
_MAX_NESTED_TABLE_UNWRAP = 80

trim_notes: list[str] = []


def consume_trim_notes() -> list[str]:
    out = list(trim_notes)
    trim_notes.clear()
    return out


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
_CHROME_TABLE_TAGS = frozenset({"nav", "aside", "footer"})
_NUMERIC_CELL_RE = re.compile(r"^[\s$€£¥]?\s*-?\d[\d,]*(?:\.\d+)?\s*%?\s*$")


def _own_rows(table: Tag) -> list[Tag]:
    """Rows that belong to ``table`` itself, not to a table nested inside it.

    Stops after ``_MAX_EMIT_ROWS + 1`` own rows so huge tables stay time-safe; callers
    that emit text add a truncation marker when the cap binds. Walks ``descendants``
    (a generator) instead of ``find_all`` so a 30k-row table does not materialise every row.
    """
    rows: list[Tag] = []
    for node in table.descendants:
        if not isinstance(node, Tag) or node.name != "tr":
            continue
        if node.find_parent("table") is table:
            rows.append(node)
            if len(rows) > _MAX_EMIT_ROWS:
                break
    return rows


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


# Link-heavy grids (footers, related-product tiles) stay dropped; real data tables sit well below this.
_DATA_TABLE_MAX_LINK_DENSITY = 0.20
_DATA_TABLE_MAX_LINK_FRAC = 0.25


def table_in_chrome(table: Tag) -> bool:
    """True when ``table`` or an ancestor is nav/aside/footer or carries chrome class tokens."""
    node: Tag | None = table
    while isinstance(node, Tag):
        if node.name in _CHROME_TABLE_TAGS:
            return True
        if _attr_tokens(node) & NOISE_TOKENS:
            return True
        parent = node.parent
        node = parent if isinstance(parent, Tag) else None
    return False


def _looks_numeric(text: str) -> bool:
    return bool(text) and _NUMERIC_CELL_RE.match(text) is not None


def _grid_is_data(headers: list[str], body_rows: list[list[str]], table: Tag) -> bool:
    """Real tabular data: a header row / ``th`` cells, or at least one numeric cell."""
    if headers or table.find("th") is not None:
        return True
    return any(_looks_numeric(c) for row in body_rows for c in row)


def is_rescueable_data_table(table: Tag, link_density: float | None = None) -> bool:
    """True for a compact data grid worth keeping when its section is kept.

    Requires a header or numeric cells, at least two rows and two columns, rejects layout
    tables, chrome ancestors, and link-dense grids (footers, related-item tiles).
    ``link_density`` may be supplied by the caller; otherwise it is computed from the table.
    """
    if table_in_chrome(table) or is_layout_table(table):
        return False
    headers, body_rows = _table_grid(table)
    n_rows = (1 if headers else 0) + len(body_rows)
    if n_rows < 2:
        return False
    sample = headers or (body_rows[0] if body_rows else [])
    ncols = len(sample)
    if ncols < 2:
        return False
    if body_rows and any(len(r) != ncols for r in body_rows):
        # ragged grids still qualify on max width when headered; use max for the check below
        ncols = max(ncols, max(len(r) for r in body_rows))
    if not _grid_is_data(headers, body_rows, table):
        return False
    n_cells = max(1, n_rows * ncols)
    n_links = len(table.find_all("a"))
    if n_links / n_cells > _DATA_TABLE_MAX_LINK_FRAC:
        return False
    if link_density is None:
        text_len = len(table.get_text(" ", strip=True))
        if text_len == 0:
            return False
        link_len = sum(len(a.get_text(" ", strip=True)) for a in table.find_all("a"))
        link_density = min(1.0, link_len / max(1, text_len))
    return link_density <= _DATA_TABLE_MAX_LINK_DENSITY


def _unwrap_layout_table(table: Tag) -> None:
    """Rename this table and its direct parts to divs; leave nested tables intact.

    Nested data tables inside a layout shell must survive so they can be linearized later.
    Deeply nested layout forests use the one-shot path in ``unwrap_layout_tables`` instead.
    """
    for part in [table, *table.find_all(_TABLE_PARTS)]:
        if part is table or part.find_parent("table") is table:
            part.name = "div"


def _drop_empty_columns(
    headers: list[str], body_rows: list[list[str]]
) -> tuple[list[str], list[list[str]]]:
    """Omit columns that are empty in the header and in every body cell.

    Does not invent blank header labels for body cells past ``len(headers)`` —
    those stay as short-header extras so linearize can emit ``colN`` only when
    the cell has text (and omit empty trailing ``colN`` pads).
    """
    if not headers and not body_rows:
        return headers, body_rows
    header_width = len(headers)
    body_width = max((len(r) for r in body_rows), default=0)
    ncols = max(header_width, body_width)
    if ncols == 0:
        return headers, body_rows
    keep: list[int] = []
    for i in range(ncols):
        h = headers[i].strip() if i < header_width else ""
        has_body = any((r[i].strip() if i < len(r) else "") for r in body_rows)
        if i < header_width:
            if h or has_body:
                keep.append(i)
        elif has_body:
            keep.append(i)
    if not keep:
        return [], []
    new_headers = [headers[i] for i in keep if i < header_width]
    while new_headers and not new_headers[-1].strip():
        idx_in_keep = len(new_headers) - 1
        idx = keep[idx_in_keep]
        if any((r[idx].strip() if idx < len(r) else "") for r in body_rows):
            break
        new_headers.pop()
        keep.pop(idx_in_keep)
    new_rows = [[(r[i] if i < len(r) else "") for i in keep] for r in body_rows]
    return new_headers, new_rows


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
        if not rows:  # a <table> without rows (empty or only a caption) has nothing to linearize
            return headers, body_rows
        first = rows[0]
        cells = first.find_all(["th", "td"])
        if first.find("th") or all(c.name == "th" for c in cells):
            headers = [_cell_text(c) for c in cells]
            data_trs = rows[1:]
        else:
            data_trs = rows

    for tr in data_trs:
        body_rows.append([_cell_text(c) for c in tr.find_all(["td", "th"])])
    # Keep blank header labels (do not clear to []): pipe render already requires a
    # non-empty header, and linearized ``: value | colN: …`` cues help LBC drop chrome grids.
    headers, body_rows = _drop_empty_columns(headers, body_rows)
    return headers, body_rows


def _has_merged_cells(table: Tag) -> bool:
    for cell in table.find_all(["td", "th"]):
        if _cell_span(cell, "colspan") > 1 or _cell_span(cell, "rowspan") > 1:
            return True
    return False


def _cell_is_single_line(text: str) -> bool:
    return "\n" not in text and "\r" not in text


def _can_render_pipe_from_grid(
    table: Tag, headers: list[str], body_rows: list[list[str]]
) -> bool:
    """True when a pre-built grid is a small rectangular GFM pipe candidate."""
    if is_layout_table(table) or _has_merged_cells(table):
        return False
    # Empty spacer rows do not disqualify an otherwise rectangular data grid.
    rows = [r for r in body_rows if any(c.strip() for c in r)]
    n_data = len(rows) + (1 if headers else 0)
    if n_data == 0 or n_data > _MAX_PIPE_ROWS:
        return False
    # Blank <th> row (all-empty headers) → not a pipe table (linearize with colN cues).
    # No header row at all → allow body-only pipe (visual header often lives in row 1).
    if headers and not any(h.strip() for h in headers):
        return False
    if headers:
        ncols = len(headers)
        if ncols > _MAX_PIPE_COLS:
            return False
        if not all(_cell_is_single_line(h) for h in headers):
            return False
    elif rows:
        # Single-row headerless grids are usually nav/chrome strips, not data tables.
        if len(rows) < 2:
            return False
        ncols = len(rows[0])
        if ncols > _MAX_PIPE_COLS:
            return False
    else:
        return False

    for row in rows:
        if len(row) != ncols:
            return False
        if not all(_cell_is_single_line(c) for c in row):
            return False
    return bool(headers or rows)


def can_render_pipe_table(table: Tag) -> bool:
    """True when the table is a small rectangular grid suitable for GFM pipe output."""
    headers, body_rows = _table_grid(table)
    return _can_render_pipe_from_grid(table, headers, body_rows)


def _render_pipe_from_grid(headers: list[str], body_rows: list[list[str]]) -> str:
    body = [r for r in body_rows if any(c.strip() for c in r)]
    truncated = len(body) > _MAX_EMIT_ROWS
    to_emit = body[:_MAX_EMIT_ROWS]
    lines: list[str] = []
    if headers:
        lines.append("| " + " | ".join(_escape_pipe_cell(h) for h in headers) + " |")
        lines.append("| " + " | ".join("---" for _ in headers) + " |")
        width = len(headers)
        for row in to_emit:
            cells = list(row[:width]) + [""] * max(0, width - len(row))
            lines.append("| " + " | ".join(_escape_pipe_cell(c) for c in cells) + " |")
    else:
        for row in to_emit:
            lines.append("| " + " | ".join(_escape_pipe_cell(c) for c in row) + " |")
    if truncated:
        lines.append(f"[Table truncated after {_MAX_EMIT_ROWS} rows]")
    return "\n".join(lines)


def render_pipe_table(table: Tag) -> str:
    headers, body_rows = _table_grid(table)
    return _render_pipe_from_grid(headers, body_rows)


def _linearize_pair(header: str, value: str) -> str | None:
    """Format one cell; keep values even when the header label is blank.

    Empty headers still use the ``h: v`` shape (``: value``) so row-label columns
    stay visible and the block classifier sees the same cue as historically.
    """
    h = (header or "").strip()
    v = (value or "").strip()
    if not h and not v:
        return None
    return f"{h}: {v}"


def _linearize_from_grid(headers: list[str], body_rows: list[list[str]], title: str) -> str:
    if not headers and not body_rows:
        return ""
    body = [r for r in body_rows if any(c.strip() for c in r)]
    truncated = len(body) > _MAX_EMIT_ROWS
    to_emit = body[:_MAX_EMIT_ROWS]
    lines = [f"[Table: {title}]"]
    for i, row in enumerate(to_emit, start=1):
        pairs: list[str] = []
        width = max(len(headers), len(row))
        for idx in range(width):
            v = row[idx] if idx < len(row) else ""
            if idx < len(headers):
                piece = _linearize_pair(headers[idx], v)
            elif not v.strip():
                continue
            else:
                piece = v.strip()
            if piece is not None:
                pairs.append(piece)
        if pairs:
            lines.append(f"Row {i} -> " + " | ".join(pairs))
    if truncated:
        lines.append(f"[Table truncated after {_MAX_EMIT_ROWS} rows]")
    return "\n".join(lines)


def linearize_table(table: Tag, index: int = 1) -> str:
    caption = table.find("caption")
    title = caption.get_text(" ", strip=True) if caption else f"Table {index}"
    headers, body_rows = _table_grid(table)
    return _linearize_from_grid(headers, body_rows, title)


def format_table(table: Tag, index: int = 1, *, table_format: str = "markdown") -> str:
    headers, body_rows = _table_grid(table)
    body = [r for r in body_rows if any(c.strip() for c in r)]
    truncated = len(body) > _MAX_EMIT_ROWS
    if table_format == "markdown" and _can_render_pipe_from_grid(table, headers, body_rows):
        text = _render_pipe_from_grid(headers, body_rows)
        if text:
            if truncated and "[Table truncated after" not in text:
                text += f"\n[Table truncated after {_MAX_EMIT_ROWS} rows]"
            return text
    caption = table.find("caption")
    title = caption.get_text(" ", strip=True) if caption else f"Table {index}"
    return _linearize_from_grid(headers, body_rows, title)


def unwrap_layout_tables(soup: BeautifulSoup) -> int:
    """Turn layout tables into plain divs so their content is scored like any other block."""
    tables = [t for t in tags_named(soup, ("table",)) if t.attrs is not None]
    # Deep *nested* tables only (not many sibling tables on a listing page).
    deeply_nested = bool(tables) and len(tables[0].find_all("table")) >= _MAX_NESTED_TABLE_UNWRAP
    if deeply_nested:
        trim_notes.append(
            "Deeply nested table markup was unwrapped without linearizing inner grids (time-safe path)."
        )
        for tag in soup.find_all(("table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption")):
            tag.name = "div"
        return len(tables)
    count = 0
    for table in tables:
        if table.name != "table":
            continue
        if is_layout_table(table):
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
    index = 0
    # Snapshot once; unwrap may rename nested tables mid-walk.
    tables = [t for t in tags_named(soup, ("table",)) if t.attrs is not None]
    deeply_nested = bool(tables) and len(tables[0].find_all("table")) >= _MAX_NESTED_TABLE_UNWRAP
    if deeply_nested:
        trim_notes.append(
            "Deeply nested table markup was unwrapped without linearizing inner grids (time-safe path)."
        )
        for tag in soup.find_all(("table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption")):
            tag.name = "div"
        return 0
    for table in tables:
        if table.attrs is None or table.name != "table":
            continue
        if is_layout_table(table):
            _unwrap_layout_table(table)
            continue
        index += 1
        text = format_table(table, index=index, table_format=table_format)
        if not text:
            table.decompose()
            continue
        pre = soup.new_tag("pre")
        pre.string = text
        table.replace_with(pre)
        count += 1
    return count
