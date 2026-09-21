from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BlockScore:
    """Scored DOM content block."""

    text: str
    tag: str
    link_density: float
    text_density: float
    noise_cosine: float | None = None
    keep: bool = True
    reason: str = ""


@dataclass
class ExtractResult:
    """Final extraction payload."""

    url: str | None
    markdown: str
    front_matter: dict[str, Any] = field(default_factory=dict)
    n_blocks_in: int = 0
    n_blocks_kept: int = 0
    n_tables: int = 0
    tokens_estimate: int = 0
    method: str = "chromerag"
    diagnostics: dict[str, Any] = field(default_factory=dict)
    # Operator-facing warnings (e.g. JS shell / thin HTML from upstream fetch).
    warnings: list[str] = field(default_factory=list)
    input_quality: dict[str, Any] = field(default_factory=dict)
