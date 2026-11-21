"""Tests for collapsed-extraction coverage-retry signals."""

from __future__ import annotations

import numpy as np
from bs4 import BeautifulSoup

from chromerag.blockfeatures import Block, find_blocks
from chromerag.collapse import dual_region_candidate, extraction_looks_collapsed
from chromerag.config import PipelineConfig
from chromerag.treestats import TreeStats


def _blocks(html: str) -> list[Block]:
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("body")
    assert body is not None
    stats = TreeStats(body)
    return find_blocks(body, stats)


def test_rich_collapsed_retry_detects_low_keep_ratio() -> None:
    cfg = PipelineConfig(lbc_rich_collapsed_retry=True)
    assert extraction_looks_collapsed(
        70,
        400,
        n_blocks_in=50,
        n_blocks_kept=2,
        expected_f1=0.6,
        dual_region_candidate=False,
        cfg=cfg,
    )
    off = PipelineConfig(lbc_rich_collapsed_retry=False)
    assert not extraction_looks_collapsed(
        70,
        400,
        n_blocks_in=50,
        n_blocks_kept=2,
        expected_f1=0.6,
        dual_region_candidate=False,
        cfg=off,
    )


def test_dual_region_candidate_is_pure_detection() -> None:
    html = (
        "<html><body>"
        "<article><p>Left column article prose with many words about topic A here.</p></article>"
        "<aside><p>Right sidebar article prose with many words about topic B here.</p></aside>"
        "</body></html>"
    )
    blocks = _blocks(html)
    n = len(blocks)
    proba = np.linspace(0.55, 0.48, n)
    box = np.zeros(n, dtype=np.int32)
    mid = max(1, n // 2)
    box[mid:] = 1
    assert isinstance(dual_region_candidate(blocks, proba, box), bool)


def test_dual_region_candidate_signal_widens_collapsed() -> None:
    cfg = PipelineConfig(lbc_rich_collapsed_retry=True)
    assert not extraction_looks_collapsed(
        90,
        400,
        n_blocks_in=20,
        n_blocks_kept=10,
        expected_f1=0.7,
        dual_region_candidate=False,
        cfg=cfg,
    )
    assert extraction_looks_collapsed(
        90,
        400,
        n_blocks_in=20,
        n_blocks_kept=10,
        expected_f1=0.7,
        dual_region_candidate=True,
        cfg=cfg,
    )
