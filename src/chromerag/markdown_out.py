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


def _inline(el: Tag | NavigableString) -> str:
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
        return f"**{''.join(_inline(c) for c in el.children).strip()}**"
    if name in {"em", "i"}:
        return f"*{' '.join(_inline(c) for c in el.children).strip()}*"
    if name == "code" and el.parent and el.parent.name != "pre":
        return f"`{el.get_text()}`"
    if name == "a":
        text = el.get_text(" ", strip=True)
        href = el.get("href") or ""
        if href and text:
            return f"[{text}]({href})"
        return text
    return "".join(_inline(c) for c in el.children)


def element_to_markdown(el: Tag) -> str:
    name = el.name or ""
    if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        level = int(name[1])
        return f"{'#' * level} {el.get_text(' ', strip=True)}\n\n"
    if name == "p":
        return f"{''.join(_inline(c) for c in el.children).strip()}\n\n"
    if name == "pre":
        text = el.get_text("\n", strip=False).strip()
        if text.startswith("[Table:"):
            return f"{text}\n\n"
        return f"```\n{text}\n```\n\n"
    if name == "li":
        return f"- {el.get_text(' ', strip=True)}\n"
    if name in {"ul", "ol"}:
        parts = []
        for li in el.find_all("li", recursive=False):
            parts.append(f"- {li.get_text(' ', strip=True)}")
        return "\n".join(parts) + "\n\n"
    if name == "blockquote":
        body = el.get_text(" ", strip=True)
        return "> " + body.replace("\n", "\n> ") + "\n\n"
    # generic
    text = el.get_text(" ", strip=True)
    return f"{text}\n\n" if text else ""


def soup_to_markdown(soup: BeautifulSoup, *, inject_heading_paths: bool = False) -> str:
    """Convert cleaned soup to Markdown.

    When inject_heading_paths=True, each non-heading block is prefixed with its
    ancestor heading trail so chunk embeddings retain section context:
      [Section: H1 > H2 > H3]
      paragraph text...
    """
    root = soup.body or soup
    main = root.find("main") or root.find("article") or root
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
            parts.append(element_to_markdown(el))
            seen.add(id(el))
            return

        body = element_to_markdown(el)
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
            text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
            if text and len(child_blocks) == 0 and id(node) not in seen:
                if inject_heading_paths and heading_stack:
                    path = " > ".join(t for _, t in heading_stack)
                    parts.append(f"[Section: {path}]\n{text}\n\n")
                else:
                    parts.append(f"{text}\n\n")
                seen.add(id(node))
                continue
        for child in list(node.children):
            if isinstance(child, Tag):
                stack.append(child)

    md = "".join(parts)
    md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"
    return md
