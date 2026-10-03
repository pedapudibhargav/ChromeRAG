"""HTML fragment → Markdown helpers."""

from __future__ import annotations

import re

import yaml
from bs4 import BeautifulSoup, NavigableString, Tag


def front_matter_yaml(data: dict) -> str:
    clean = {k: v for k, v in data.items() if not str(k).startswith("_") and v is not None}
    if not clean:
        return ""
    dumped = yaml.safe_dump(clean, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{dumped}\n---\n\n"


def _inline(el: Tag | NavigableString, links: bool = True) -> str:
    if isinstance(el, NavigableString):
        return str(el)
    if not isinstance(el, Tag):
        return ""
    name = el.name or ""
    if name in {"script", "style"}:
        return ""
    if name == "br":
        return "\n"
    if name in {"strong", "b"}:
        return f"**{''.join(_inline(c, links) for c in el.children).strip()}**"
    if name in {"em", "i"}:
        return f"*{' '.join(_inline(c, links) for c in el.children).strip()}*"
    if name == "code" and el.parent and el.parent.name != "pre":
        return f"`{el.get_text()}`"
    if name == "a":
        text = el.get_text(" ", strip=True)
        href = el.get("href") or ""
        if links and href and text:
            return f"[{text}]({href})"
        return text
    return "".join(_inline(c, links) for c in el.children)


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


_BLOCK_NAMES = ["p", "ul", "ol", "li", "table", "pre", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "dl"]


def element_to_markdown(el: Tag, links: bool = True) -> str:
    name = el.name or ""
    if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        level = int(name[1])
        return f"{'#' * level} {el.get_text(' ', strip=True)}\n\n"
    if name == "p":
        return f"{''.join(_inline(c, links) for c in el.children).strip()}\n\n"
    if name == "pre":
        text = _preformatted_text(el)
        if _is_table_pre(text):
            return f"{text}\n\n"
        return f"```\n{text}\n```\n\n"
    if name == "li":
        return f"- {el.get_text(' ', strip=True)}\n"
    if name in {"ul", "ol"}:
        return "\n".join(_list_lines(el)) + "\n\n"
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

    def _mark(el: Tag) -> None:
        name = el.name or ""
        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(name[1])
            text = el.get_text(" ", strip=True)
            if not text:
                seen.add(id(el))
                return
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, text))
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
        if name in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "pre", "blockquote"}:
            if id(node) not in seen:
                _mark(node)
            continue
        if name in {"ul", "ol"}:
            if id(node) not in seen:
                _mark(node)
            continue
        if name == "li":
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

    md = "".join(parts)
    md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"
    return md
