"""One bottom-up pass that gives every element its text and link-text sizes.

``tag.get_text(" ", strip=True)`` costs O(size of subtree), so asking for it on every element of
a page costs O(n * depth). This module computes the same numbers for all elements in O(n).

The values are exact, not estimates:
  text_len(tag)   == len(tag.get_text(" ", strip=True))
  text_nosep(tag) == len(tag.get_text("", strip=True))
  link_len(tag)   == len(" ".join(a.get_text(" ", strip=True) for a in tag.find_all("a")))
  has_main(tag)   == tag.find("main") or tag.find(attrs={"role": "main"}) is found
  html_len(tag)   == len(str(tag))   (only when built with ``serialized=True``)

Statistics describe the tree at the moment of the call. After the tree is changed, they stay
valid for every element that is not an ancestor of a removed node, so a caller that walks in
document order (ancestors first) and removes only the node it is looking at can keep using them.
"""

from __future__ import annotations

from bs4 import BeautifulSoup, CData, NavigableString, Tag

_TEXT_TYPES = (NavigableString, CData)
_RAW_TEXT_PARENTS = frozenset({"script", "style"})  # bs4 does not escape text inside these


def _text_html_len(node: NavigableString, parent_name: str | None) -> int:
    """Length of a text node as ``str(tag)`` writes it (``& < >`` become entities)."""
    if type(node) is CData:
        return len(node) + 12  # <![CDATA[ ... ]]>
    text = str(node)
    if parent_name in _RAW_TEXT_PARENTS:
        return len(text)
    return len(text) + 4 * text.count("&") + 3 * (text.count("<") + text.count(">"))


def _open_close_len(tag: Tag) -> int | None:
    """Length of the start and end tags of ``tag`` as ``str(tag)`` writes them.

    Returns None when the attributes need special handling (then callers ask bs4 itself).
    """
    name = tag.name
    total = 1 + len(name) + 1  # "<name" + ">"
    for key, val in tag.attrs.items():
        if val is None:
            total += 1 + len(key)
            continue
        if isinstance(val, (list, tuple)):
            val = " ".join(val)
        elif type(val) is not str:
            return None  # e.g. meta charset values that bs4 rewrites on output
        quotes = val.count('"')
        length = len(val) + 4 * val.count("&") + 3 * (val.count("<") + val.count(">"))
        if quotes and "'" in val:
            length += 5 * quotes  # &quot;
        total += 1 + len(key) + 1 + length + 2  # ' key="value"'
    if tag.is_empty_element:
        return total + 1  # "/>" instead of ">"
    return total + len(name) + 3  # "</name>"


class TreeStats:
    """Per-element sizes for the subtree under ``root`` (which is included)."""

    __slots__ = ("_rows", "_serialized")

    def __init__(self, root: Tag | BeautifulSoup, *, serialized: bool = False) -> None:
        # row = [sum of stripped string lengths, string count, descendant <a> count,
        #        sum of text_len over descendant <a>, has descendant main,
        #        length of the children as str() writes them, inexact flag]
        rows: dict[int, list] = {}
        get = rows.get
        for node in reversed(list(root.descendants)):
            parent = node.parent
            if type(node) in _TEXT_TYPES:
                if parent is None:
                    continue
                row = get(id(parent))
                if row is None:
                    row = rows[id(parent)] = [0, 0, 0, 0, False, 0, False]
                stripped = node.strip()
                if stripped:
                    row[0] += len(stripped)
                    row[1] += 1
                if serialized:
                    row[5] += _text_html_len(node, parent.name)
                continue
            if not isinstance(node, Tag):
                if serialized and parent is not None:
                    # comments, doctype...: leave the count to bs4
                    row = get(id(parent))
                    if row is None:
                        row = rows[id(parent)] = [0, 0, 0, 0, False, 0, False]
                    row[6] = True
                continue
            row = get(id(node))
            if row is None:
                row = rows[id(node)] = [0, 0, 0, 0, False, 0, False]
            if parent is None:
                continue
            prow = get(id(parent))
            if prow is None:
                prow = rows[id(parent)] = [0, 0, 0, 0, False, 0, False]
            prow[0] += row[0]
            prow[1] += row[1]
            prow[2] += row[2]
            prow[3] += row[3]
            if node.name == "a":
                prow[2] += 1
                prow[3] += row[0] + (row[1] - 1 if row[1] > 1 else 0)
            if row[4] or node.name == "main" or node.attrs.get("role") == "main":
                prow[4] = True
            if serialized:
                overhead = _open_close_len(node)
                if overhead is None or row[6]:
                    prow[6] = True
                else:
                    prow[5] += overhead + row[5]
        self._rows = rows
        self._serialized = serialized

    def _row(self, tag: Tag) -> list:
        row = self._rows.get(id(tag))
        return row if row is not None else [0, 0, 0, 0, False, 0, False]

    def html_len(self, tag: Tag) -> int:
        """``len(str(tag))``. Needs ``serialized=True``; asks bs4 itself for odd markup."""
        row = self._row(tag)
        if not self._serialized or row[6]:
            return len(str(tag))
        overhead = _open_close_len(tag)
        if overhead is None:
            return len(str(tag))
        return overhead + row[5]

    def text_len(self, tag: Tag) -> int:
        row = self._row(tag)
        return row[0] + (row[1] - 1 if row[1] > 1 else 0)

    def text_nosep(self, tag: Tag) -> int:
        return self._row(tag)[0]

    def link_len(self, tag: Tag) -> int:
        row = self._row(tag)
        return row[3] + (row[2] - 1 if row[2] > 1 else 0)

    def has_main(self, tag: Tag) -> bool:
        return self._row(tag)[4]

    def link_density(self, tag: Tag) -> float:
        """Same value as ``density.link_density`` (empty text counts as fully linked)."""
        text_len = self.text_len(tag)
        if text_len == 0:
            return 1.0
        return min(1.0, self.link_len(tag) / max(1, text_len))
