"""HTML fragment → Markdown helpers."""

from __future__ import annotations

import re
from contextvars import ContextVar

import yaml
from bs4 import BeautifulSoup, NavigableString, Tag


def front_matter_yaml(data: dict) -> str:
    clean = {k: v for k, v in data.items() if not str(k).startswith("_") and v is not None}
    if not clean:
        return ""
    dumped = yaml.safe_dump(clean, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{dumped}\n---\n\n"


_BREAK_CLASS_TOKENS = frozenset({"br", "linebreak", "line-break", "newline"})
# Stay well under the default recursion limit (~1000); deep trees fall back to get_text.
_INLINE_DEPTH_CAP = 200
_LIST_DEPTH_CAP = 200
_trim_notes_var: ContextVar[list[str] | None] = ContextVar("chromerag_md_trim_notes", default=None)


def _trim_notes() -> list[str]:
    notes = _trim_notes_var.get()
    if notes is None:
        notes = []
        _trim_notes_var.set(notes)
    return notes


def consume_trim_notes() -> list[str]:
    notes = _trim_notes_var.get()
    _trim_notes_var.set([])
    return list(notes or [])


def reset_trim_notes() -> None:
    _trim_notes_var.set([])


def _class_tokens(el: Tag) -> set[str]:
    raw = el.get("class") or []
    if isinstance(raw, str):
        raw = raw.split()
    return {str(c).lower() for c in raw}


def _emph_wrap(marker: str, inner: str) -> str:
    if not inner.strip():
        return inner if inner else ""
    s = inner.strip()
    # Nested same-marker emphasis already carries markers; re-wrapping would emit ****.
    if s.startswith(marker) and s.endswith(marker) and len(s) >= 2 * len(marker):
        return s
    return f"{marker}{s}{marker}"


def _join_inline_parts(parts: list[str]) -> str:
    """Join inline pieces without creating adjacent emphasis runs (``****`` / ``**``)."""
    if not parts:
        return ""
    out = parts[0]
    for part in parts[1:]:
        if not part:
            continue
        if not out:
            out = part
            continue
        if (out.endswith("**") and part.startswith("**")) or (
            out.endswith("*") and part.startswith("*") and not out.endswith("**") and not part.startswith("**")
        ):
            out = f"{out} {part}"
        else:
            out += part
    return out


def _break_adjacent_markers(text: str) -> str:
    """Split accidental ``****`` from adjacent emphasis only; never call on pre/code text."""
    if "****" not in text:
        return text
    prev = None
    while prev != text:
        prev = text
        text = text.replace("****", "** **")
    return text


def _inline(el: Tag | NavigableString, links: bool = True, _depth: int = 0) -> str:
    if isinstance(el, NavigableString):
        return str(el)
    if not isinstance(el, Tag):
        return ""
    if _depth > _INLINE_DEPTH_CAP:
        notes = _trim_notes()
        if not notes or notes[-1] != "Deep inline nesting was truncated during Markdown rendering.":
            notes.append("Deep inline nesting was truncated during Markdown rendering.")
        return el.get_text(" ", strip=True)
    name = el.name or ""
    if name in {"script", "style"}:
        return ""
    if name == "br" or (name == "span" and _class_tokens(el) & _BREAK_CLASS_TOKENS):
        return "\n"
    if name in {"strong", "b"}:
        return _emph_wrap(
            "**", _join_inline_parts([_inline(c, links, _depth + 1) for c in el.children])
        )
    if name in {"em", "i"}:
        return _emph_wrap(
            "*", _join_inline_parts([_inline(c, links, _depth + 1) for c in el.children])
        )
    if name == "code" and el.parent and el.parent.name != "pre":
        return f"`{el.get_text()}`"
    if name == "a":
        text = el.get_text(" ", strip=True)
        href = el.get("href") or ""
        if links and href and text:
            return f"[{text}]({href})"
        return text
    joined = _join_inline_parts([_inline(c, links, _depth + 1) for c in el.children])
    # Do not rewrite literal asterisks that live inside inline code spans.
    if el.find("code") is not None:
        return joined
    return _break_adjacent_markers(joined)


def _is_pipe_table(text: str) -> bool:
    lines = [ln for ln in text.strip().split("\n") if ln.strip()]
    return len(lines) >= 2 and all(ln.strip().startswith("|") for ln in lines)


def _is_table_pre(text: str) -> bool:
    return text.startswith("[Table:") or _is_pipe_table(text)


def _preformatted_text(el: Tag) -> str:
    """Text of a ``<pre>`` as written: syntax-highlight spans are joined, ``<br>`` becomes a line break."""
    parts: list[str] = []
    for node in el.descendants:
        if isinstance(node, NavigableString):
            parts.append(str(node))
        elif isinstance(node, Tag) and node.name == "br":
            parts.append("\n")
    return "".join(parts).strip("\n").rstrip()


def _list_lines(el: Tag, depth: int = 0) -> list[str]:
    """Lines of a list: ``1.`` for ordered lists, ``-`` otherwise, nested lists indented by two spaces."""
    if depth > _LIST_DEPTH_CAP:
        notes = _trim_notes()
        msg = "Deep list nesting was truncated during Markdown rendering."
        if msg not in notes:
            notes.append(msg)
        text = el.get_text(" ", strip=True)
        return [f"- {text}"] if text else []
    lines: list[str] = []
    ordered = el.name == "ol"
    start = el.get("start")
    number = int(start) if isinstance(start, str) and start.isdigit() else 1
    for li in el.find_all("li", recursive=False):
        own = []
        nested: list[Tag] = []
        for child in li.children:
            if isinstance(child, Tag) and child.name in ("ul", "ol"):
                nested.append(child)
            elif isinstance(child, Tag):
                own.append(child.get_text(" ", strip=True))
            else:
                own.append(str(child).strip())
        text = " ".join(t for t in own if t)
        marker = f"{number}." if ordered else "-"
        number += 1
        if text:
            lines.append("  " * depth + f"{marker} {text}")
        for sub in nested:
            lines.extend(_list_lines(sub, depth + (1 if text else 0)))
    return lines


_BLOCK_NAMES = [
    "p",
    "ul",
    "ol",
    "li",
    "table",
    "pre",
    "blockquote",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "dl",
    "figure",
    "figcaption",
]
# Content landmarks only: break open a list that wrongly wraps page body. Nav/aside/footer
# inside a list are ordinary chrome, not a reason to flatten the whole list.
_CONTENT_LANDMARKS = frozenset({"main", "article"})
_CONTENT_WRAPPERS = frozenset({"div", "section"})


def _list_is_layout_shell(node: Tag) -> bool:
    """True when a list wraps page structure rather than a card/related-post list.

    ``main`` anywhere under the list always counts. Multiple ``<li>`` each holding an
    ``article`` is a card grid and stays an ordinary list.
    """
    if node.find("main") is not None:
        return True
    art_lis = [li for li in node.find_all("li") if li.find("article") is not None]
    if len(art_lis) >= 2:
        return False
    for child in node.children:
        if not isinstance(child, Tag):
            continue
        if child.name in _CONTENT_LANDMARKS:
            return True
        if child.name in _CONTENT_WRAPPERS | {"li"} and child.find(_CONTENT_LANDMARKS) is not None:
            return True
    return False


def _content_branches(node: Tag) -> list[Tag]:
    """Direct content landmarks or section/div wrappers around them (skip nav/promo siblings)."""
    out: list[Tag] = []
    for child in node.children:
        if not isinstance(child, Tag):
            continue
        if child.name in _CONTENT_LANDMARKS:
            out.append(child)
        elif child.name in _CONTENT_WRAPPERS and child.find(_CONTENT_LANDMARKS) is not None:
            out.append(child)
        elif child.name == "li":
            out.extend(_content_branches(child))
    return out


_DL_BLOCK_CHILDREN = (
    "p",
    "ul",
    "ol",
    "table",
    "pre",
    "blockquote",
    "div",
    "section",
    "dl",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
)


def _dt_dd_to_markdown(el: Tag, links: bool = True) -> str:
    """Render a single ``dt`` or ``dd`` when a non-simple ``dl`` is walked by the block scanner."""
    name = el.name or ""
    if name == "dt":
        term = el.get_text(" ", strip=True)
        return f"- **{term}**\n\n" if term else ""
    if name == "dd":
        # Block children are emitted by the walker; keep direct text and inline tags here.
        parts: list[str] = []
        has_block = False
        for c in el.children:
            if isinstance(c, Tag) and (c.name or "") in _DL_BLOCK_CHILDREN:
                has_block = True
                continue
            parts.append(_inline(c, links))
        defin = _join_inline_parts(parts).strip()
        if el.find("code") is None:
            defin = _break_adjacent_markers(defin).strip()
        if not defin:
            return ""
        # Mixed inline+block: emit the inline prefix without a list bullet (blocks follow).
        if has_block or el.find(_DL_BLOCK_CHILDREN) is not None:
            return f"{defin}\n\n"
        return f"- {defin}\n\n"
    return ""


def _dl_to_markdown(el: Tag, links: bool = True) -> str:
    lines: list[str] = []
    pending_terms: list[str] = []
    for child in el.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "dt":
            term = child.get_text(" ", strip=True)
            if term:
                pending_terms.append(term)
        elif child.name == "dd":
            defin = _join_inline_parts([_inline(c, links) for c in child.children]).strip()
            if child.find("code") is None:
                defin = _break_adjacent_markers(defin).strip()
            if pending_terms:
                for term in pending_terms:
                    if defin:
                        lines.append(f"- **{term}**: {defin}")
                    else:
                        lines.append(f"- **{term}**")
                pending_terms = []
            elif defin:
                lines.append(f"- {defin}")
    for term in pending_terms:
        lines.append(f"- **{term}**")
    if lines:
        return "\n".join(lines) + "\n\n"
    text = el.get_text(" ", strip=True)
    return f"{text}\n\n" if text else ""


def _is_simple_dl(el: Tag) -> bool:
    """A term list rendered as one block. A ``dl`` that holds blocks is a layout wrapper: walk it instead."""
    return el.find(_DL_BLOCK_CHILDREN) is None


def element_to_markdown(el: Tag, links: bool = True) -> str:
    name = el.name or ""
    if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        level = int(name[1])
        return f"{'#' * level} {el.get_text(' ', strip=True)}\n\n"
    if name == "p":
        joined = _join_inline_parts([_inline(c, links) for c in el.children])
        if el.find("code") is None:
            joined = _break_adjacent_markers(joined)
        return f"{joined.strip()}\n\n"
    if name == "pre":
        text = _preformatted_text(el)
        if _is_table_pre(text):
            return f"{text}\n\n"
        return f"```\n{text}\n```\n\n"
    if name == "li":
        return f"- {el.get_text(' ', strip=True)}\n"
    if name in {"ul", "ol"}:
        return "\n".join(_list_lines(el)) + "\n\n"
    if name == "dl":
        return _dl_to_markdown(el, links)
    if name in {"dt", "dd"}:
        return _dt_dd_to_markdown(el, links)
    if name == "figcaption":
        joined = _join_inline_parts([_inline(c, links) for c in el.children])
        if el.find("code") is None:
            joined = _break_adjacent_markers(joined)
        text = joined.strip()
        return f"*{text}*\n\n" if text else ""
    if name == "blockquote":
        body = el.get_text(" ", strip=True)
        return "> " + body.replace("\n", "\n> ") + "\n\n"
    # generic
    text = el.get_text(" ", strip=True)
    return f"{text}\n\n" if text else ""


def soup_to_markdown(
    soup: BeautifulSoup,
    *,
    inject_heading_paths: bool = False,
    content_root: Tag | None = None,
    links: bool = True,
) -> str:
    """Convert cleaned soup to Markdown.

    When inject_heading_paths=True, each non-heading block is prefixed with its
    ancestor heading trail so chunk embeddings retain section context:
      [Section: H1 > H2 > H3]
      paragraph text...
    """
    root = soup.body or soup
    main = content_root or root.find("main") or root.find("article") or root
    parts: list[str] = []
    seen: set[int] = set()
    heading_stack: list[tuple[int, str]] = []  # (level, text)
    last_h1: str | None = None

    def _mark(el: Tag) -> None:
        nonlocal last_h1
        name = el.name or ""
        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(name[1])
            text = el.get_text(" ", strip=True)
            if not text:
                seen.add(id(el))
                return
            if name == "h1" and last_h1 is not None and text == last_h1:
                seen.add(id(el))
                return
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, text))
            if name == "h1":
                last_h1 = text
            parts.append(element_to_markdown(el, links))
            seen.add(id(el))
            return

        body = element_to_markdown(el, links)
        if inject_heading_paths and body.strip() and heading_stack:
            path = " > ".join(t for _, t in heading_stack)
            parts.append(f"[Section: {path}]\n{body}")
        else:
            parts.append(body)
        seen.add(id(el))

    stack = [main] if isinstance(main, Tag) else []
    while stack:
        node = stack.pop(0)
        if not isinstance(node, Tag):
            continue
        name = node.name or ""
        if name in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "pre", "blockquote", "figcaption"} or (
            name == "dl" and _is_simple_dl(node)
        ):
            if id(node) not in seen:
                _mark(node)
            continue
        if name in {"dt", "dd"}:
            if id(node) not in seen:
                body = _dt_dd_to_markdown(node, links)
                if body.strip():
                    if inject_heading_paths and heading_stack:
                        path = " > ".join(t for _, t in heading_stack)
                        parts.append(f"[Section: {path}]\n{body}")
                    else:
                        parts.append(body)
                seen.add(id(node))
                # Block-bearing ``dd`` still needs its children walked.
                if name == "dd" and node.find(_DL_BLOCK_CHILDREN) is not None:
                    stack[0:0] = [child for child in node.children if isinstance(child, Tag)]
            continue
        if name in {"ul", "ol"}:
            if _list_is_layout_shell(node):
                stack[0:0] = _content_branches(node)
                continue
            if id(node) not in seen:
                _mark(node)
            continue
        if name == "li":
            # Expand only under a layout-shell <ul>/<ol>. Orphan carousel <li> cards stay skipped.
            parent_list = node.find_parent(["ul", "ol"])
            if parent_list is not None and _list_is_layout_shell(parent_list):
                branches = _content_branches(node)
                if branches:
                    stack[0:0] = branches
            continue
        # Shallow content divs/sections (no nested block children) — common on SPAs
        if name in {"div", "section", "article"}:
            child_blocks = [
                c
                for c in node.children
                if isinstance(c, Tag)
                and c.name
                in {
                    "div",
                    "section",
                    "article",
                    "p",
                    "ul",
                    "ol",
                    "table",
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                    "h5",
                    "h6",
                    "pre",
                    "blockquote",
                    "dl",
                    "figure",
                    "figcaption",
                }
            ]
            # A div whose children are custom elements (<awsdocs-view>, <app-root>) has no direct block
            # child but may hold the whole page: only a div with no block anywhere below is a text leaf.
            leaf = not child_blocks and node.find(_BLOCK_NAMES) is None
            text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip() if leaf else ""
            if text and leaf and id(node) not in seen:
                if inject_heading_paths and heading_stack:
                    path = " > ".join(t for _, t in heading_stack)
                    parts.append(f"[Section: {path}]\n{text}\n\n")
                else:
                    parts.append(f"{text}\n\n")
                seen.add(id(node))
                continue
        # Depth first, in document order: push the children in front of the siblings still waiting.
        stack[0:0] = [child for child in node.children if isinstance(child, Tag)]

    # Do not run _break_adjacent_markers on the full document: it would alter pre/code.
    md = "".join(parts)
    md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"
    return md
