"""Turn file bytes into text the way a browser would: honour the declared or detected encoding."""

from __future__ import annotations

from bs4.dammit import UnicodeDammit


def decode_html(data: bytes | bytearray | str) -> str:
    """Decode HTML bytes using ``<meta charset>``, a byte-order mark or detection; never raises."""
    if isinstance(data, str):
        return data
    raw = bytes(data)
    converted = UnicodeDammit(raw, is_html=True).unicode_markup
    return converted if converted is not None else raw.decode("utf-8", errors="replace")
