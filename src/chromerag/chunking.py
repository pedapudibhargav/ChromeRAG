"""Structure-aware Markdown chunking for vector-database ingestion."""

from __future__ import annotations

import re
from dataclasses import dataclass

_FRONT = re.compile(r"\A---\n.*?\n---\n+", re.S)
_HEAD = re.compile(r"^(#{1,6}) +(.+?) *$")


def _word_count(text: str) -> int:
    return len(text.split())


def _strip_front_matter(md: str) -> str:
    return _FRONT.sub("", md)


def _dedupe_adjacent(items: tuple[str, ...]) -> tuple[str, ...]:
    out: list[str] = []
    for item in items:
        if not item:
            continue
        if out and out[-1] == item:
            continue
        out.append(item)
    return tuple(out)


def _heading_path(title: str, stack: tuple[tuple[int, str], ...]) -> tuple[str, ...]:
    headings = tuple(t for _, t in stack)
    if title:
        return _dedupe_adjacent((title, *headings))
    return _dedupe_adjacent(headings)


def _parse_blocks(md: str) -> list[tuple[str, object]]:
    """Return ``(kind, payload)`` blocks: heading, text, code, table."""
    lines = md.split("\n")
    blocks: list[tuple[str, object]] = []
    buf: list[str] = []
    i = 0

    def flush_buf() -> None:
        if not buf:
            return
        text = "\n".join(buf).strip()
        buf.clear()
        if text:
            blocks.append(("text", text))

    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            flush_buf()
            fence = [line]
            i += 1
            while i < len(lines):
                fence.append(lines[i])
                if lines[i].strip().startswith("```") and len(fence) > 1:
                    i += 1
                    break
                i += 1
            blocks.append(("code", "\n".join(fence)))
            continue

        if line.startswith("[Table:"):
            flush_buf()
            table_lines = [line]
            i += 1
            while i < len(lines) and lines[i].strip():
                table_lines.append(lines[i])
                i += 1
            blocks.append(("table", "\n".join(table_lines)))
            continue

        if line.strip().startswith("|"):
            flush_buf()
            table_lines = [line]
            i += 1
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            blocks.append(("table", "\n".join(table_lines)))
            continue

        hm = _HEAD.match(line)
        if hm and not buf:
            flush_buf()
            blocks.append(("heading", (len(hm.group(1)), hm.group(2))))
            i += 1
            if i < len(lines) and not lines[i].strip():
                i += 1
            continue

        if not line.strip():
            flush_buf()
            i += 1
            continue

        buf.append(line)
        i += 1

    flush_buf()
    return blocks


@dataclass(frozen=True)
class Chunk:
    """One ingest chunk with heading context for embedding."""

    text: str
    heading_path: tuple[str, ...]
    depth: int
    words: int
    index: int

    @property
    def embed_text(self) -> str:
        if self.heading_path:
            return " > ".join(self.heading_path) + "\n" + self.text
        return self.text

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "embed_text": self.embed_text,
            "heading_path": list(self.heading_path),
            "depth": self.depth,
            "words": self.words,
            "index": self.index,
        }


@dataclass
class _RawChunk:
    text: str
    stack: tuple[tuple[int, str], ...]


def _apply_min_words(chunks: list[_RawChunk], min_words: int) -> list[_RawChunk]:
    if not chunks:
        return []
    total = sum(_word_count(c.text) for c in chunks)
    if total < min_words:
        combined = "\n\n".join(c.text for c in chunks)
        return [_RawChunk(text=combined, stack=())]

    out = list(chunks)
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(out):
            if _word_count(out[i].text) >= min_words:
                i += 1
                continue
            stk = out[i].stack
            if i > 0 and out[i - 1].stack == stk:
                merged = out[i - 1].text + "\n\n" + out[i].text
                out[i - 1] = _RawChunk(text=merged, stack=stk)
                del out[i]
                changed = True
                continue
            parent = stk[:-1]
            merged_fwd = False
            for j in range(i + 1, len(out)):
                if len(out[j].stack) >= len(parent) and out[j].stack[: len(parent)] == parent:
                    merged = out[i].text + "\n\n" + out[j].text
                    out[j] = _RawChunk(text=merged, stack=out[j].stack)
                    del out[i]
                    changed = True
                    merged_fwd = True
                    break
            if merged_fwd:
                continue
            del out[i]
            changed = True
    return out


def chunk_markdown(
    markdown: str,
    title: str = "",
    *,
    max_words: int = 180,
    min_words: int = 50,
) -> list[Chunk]:
    """Split Markdown into heading-aware chunks sized for embedding."""
    md = _strip_front_matter(markdown)
    blocks = _parse_blocks(md)

    stack: list[tuple[int, str]] = []
    raw: list[_RawChunk] = []
    buf: list[str] = []
    words = 0

    def current_stack() -> tuple[tuple[int, str], ...]:
        return tuple(stack)

    def emit() -> None:
        nonlocal buf, words
        text = "\n".join(buf).strip()
        buf, words = [], 0
        if text:
            raw.append(_RawChunk(text=text, stack=current_stack()))

    for kind, payload in blocks:
        if kind == "heading":
            emit()
            level, heading = payload  # type: ignore[misc]
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, heading))
            continue

        content = str(payload)
        block_words = _word_count(content)
        atomic = kind in {"code", "table"}
        if words and words + block_words > max_words:
            emit()
        if atomic and words and block_words > max_words:
            emit()
        buf.append(content)
        words += block_words

    emit()
    merged = _apply_min_words(raw, min_words)

    chunks: list[Chunk] = []
    for idx, item in enumerate(merged):
        text = item.text.strip()
        if not text:
            continue
        path = _heading_path(title, item.stack)
        chunks.append(
            Chunk(
                text=text,
                heading_path=path,
                depth=len(item.stack),
                words=_word_count(text),
                index=len(chunks),
            )
        )
    return chunks
