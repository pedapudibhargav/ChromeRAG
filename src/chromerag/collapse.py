"""Collapsed-extraction signals for coverage retry."""

from __future__ import annotations

import re

import numpy as np

from chromerag.blockfeatures import Block
from chromerag.config import PipelineConfig

_WORD = re.compile(r"\w+")
_DUAL_MIN_MEAN = 0.42
_DUAL_MIN_BOX_WORDS = 25


def _words(text: str) -> int:
    return len(_WORD.findall(text))


def dual_region_candidate(
    blocks: list[Block],
    proba: np.ndarray,
    box: np.ndarray,
) -> bool:
    """True when ≥2 non-overlapping content boxes both score high (no keep effect)."""
    if len(blocks) == 0:
        return False
    words = np.array([max(1, _words(b.text)) for b in blocks], dtype=np.float64)
    boxes: dict[int, list[int]] = {}
    for i, b in enumerate(box):
        if b < 0:
            continue
        boxes.setdefault(int(b), []).append(i)
    if len(boxes) < 2:
        return False
    high = 0
    for idxs in boxes.values():
        w = words[idxs]
        p = proba[idxs].astype(np.float64)
        mean_p = float((w * p).sum() / w.sum())
        if mean_p >= _DUAL_MIN_MEAN and int(w.sum()) >= _DUAL_MIN_BOX_WORDS:
            high += 1
            if high >= 2:
                return True
    return False


def extraction_looks_collapsed(
    out_words: int,
    body_words: int,
    *,
    n_blocks_in: int,
    n_blocks_kept: int,
    expected_f1: float | None,
    dual_region_candidate: bool,
    cfg: PipelineConfig,
) -> bool:
    base = out_words < 40 or (body_words > 0 and out_words < 0.15 * body_words)
    if not cfg.lbc_rich_collapsed_retry:
        return base
    if base:
        return True
    if body_words >= 120 and out_words < 0.22 * body_words and n_blocks_in > 0:
        if n_blocks_kept / n_blocks_in < 0.12:
            return True
    if expected_f1 is not None and expected_f1 < 0.45 and body_words >= 100:
        if out_words < 0.30 * body_words:
            return True
    if dual_region_candidate and body_words >= 80 and out_words < 0.25 * body_words:
        return True
    return False
