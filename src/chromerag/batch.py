"""Learn-then-extract batch helpers.

Critical order when STCE is enabled:
  1. Mine chrome patterns across the batch (or load a saved model)
  2. Only then extract each page with the learned model

Never extract-first then learn later — early chunks would keep template noise.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from chromerag.config import PipelineConfig
from chromerag.extractor import ChromeRAG
from chromerag.models import ExtractResult
from chromerag.site_chrome import (
    SiteChromeModel,
    mine_site_chrome,
    select_model_for_url,
)


@dataclass
class BatchPage:
    html: str
    url: str | None = None
    page_id: str | None = None


@dataclass
class BatchResult:
    page_id: str | None
    url: str | None
    result: ExtractResult
    chrome_group: str | None
    stce_applied: bool


def learn_chrome(
    pages: Iterable[BatchPage | tuple[str | None, str]],
    *,
    min_pages: int | None = None,
    frequency: float | None = None,
    max_block_chars: int | None = None,
    require_chrome_features: bool = True,
    path_prefix_depth: int = 1,
    config: PipelineConfig | None = None,
) -> dict[str, SiteChromeModel]:
    """Mine site chrome from a multi-page corpus. Does not extract."""
    cfg = config or PipelineConfig()
    pairs: list[tuple[str | None, str]] = []
    for p in pages:
        if isinstance(p, BatchPage):
            pairs.append((p.url, p.html))
        else:
            pairs.append((p[0], p[1]))
    return mine_site_chrome(
        pairs,
        min_pages=min_pages if min_pages is not None else cfg.stce_min_pages,
        frequency=frequency if frequency is not None else cfg.stce_frequency,
        max_block_chars=max_block_chars
        if max_block_chars is not None
        else cfg.stce_max_block_chars,
        require_chrome_features=require_chrome_features,
        path_prefix_depth=path_prefix_depth,
    )


def learn_then_extract(
    pages: Iterable[BatchPage],
    *,
    config: PipelineConfig | None = None,
    chrome_models: dict[str, SiteChromeModel] | None = None,
    learn: bool = True,
    path_prefix_depth: int = 1,
) -> tuple[list[BatchResult], dict[str, SiteChromeModel]]:
    """
    If learn=True and chrome_models is None: mine from `pages` first, then extract.
    If chrome_models provided: use them (skip mining).
    If learn=False and no models: extract with heuristics/DVDF only (STCE off).
    """
    page_list = list(pages)
    cfg = config or PipelineConfig()

    models: dict[str, SiteChromeModel] = {}
    if chrome_models is not None:
        models = chrome_models
    elif learn and cfg.enable_stce:
        models = learn_chrome(page_list, config=cfg, path_prefix_depth=path_prefix_depth)

    results: list[BatchResult] = []
    for page in page_list:
        model = (
            select_model_for_url(models, page.url, path_prefix_depth=path_prefix_depth)
            if models and cfg.enable_stce
            else None
        )
        extractor = ChromeRAG(config=cfg, site_chrome=model)
        result = extractor.extract(page.html, url=page.url)
        results.append(
            BatchResult(
                page_id=page.page_id,
                url=page.url,
                result=result,
                chrome_group=model.group_key if model else None,
                stce_applied=bool(model and model.signatures),
            )
        )
    return results, models
