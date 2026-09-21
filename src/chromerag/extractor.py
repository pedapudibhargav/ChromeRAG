"""Main extraction pipeline.

Order (intentional):
  1. Parse HTML (keep scripts)
  2. Schema harvest (JSON-LD lives in <script type=ld+json>)
  3. Strip scripts/styles
  4. Optional STCE (site-template chrome from multi-page mine)
  5. Structural chrome prune
  6. Density + DVDF residual prune
  7. Table KV linearization
  8. Markdown (+ optional heading paths)
"""

from __future__ import annotations

from typing import Any

import tiktoken
from bs4 import Tag

from chromerag.config import PipelineConfig, Strictness, infer_page_type
from chromerag.density import (
    candidate_blocks,
    parse_html,
    prune_noise_subtrees,
    score_blocks,
    strip_non_content_tags,
)
from chromerag.dvdf import NoiseAnchorIndex
from chromerag.markdown_out import front_matter_yaml, soup_to_markdown
from chromerag.models import ExtractResult
from chromerag.input_quality import assess_input_html
from chromerag.schema_fusion import fuse_front_matter
from chromerag.site_chrome import SiteChromeModel, apply_site_chrome, site_group_key
from chromerag.tables import replace_tables_with_linearized


def estimate_tokens(text: str, encoding: str = "cl100k_base") -> int:
    try:
        enc = tiktoken.get_encoding(encoding)
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)


class ChromeRAG:
    """Enterprise HTML → RAG-ready Markdown."""

    def __init__(
        self,
        config: PipelineConfig | None = None,
        *,
        strictness: Strictness | str = Strictness.BALANCED,
        site_chrome: SiteChromeModel | None = None,
        # Back-compat kwargs
        density: Any = None,
        dvdf_threshold: float | None = None,
        enable_dvdf: bool | None = None,
        enable_schema: bool | None = None,
        enable_tables: bool | None = None,
        inject_heading_paths: bool | None = None,
    ) -> None:
        cfg = config or PipelineConfig.from_strictness(strictness)
        if density is not None:
            cfg.min_chars = density.min_chars
            cfg.max_link_density = density.max_link_density
            cfg.min_text_density = density.min_text_density
        if dvdf_threshold is not None:
            cfg.dvdf_threshold = dvdf_threshold
        if enable_dvdf is not None:
            cfg.enable_dvdf = enable_dvdf
        if enable_schema is not None:
            cfg.enable_schema = enable_schema
        if enable_tables is not None:
            cfg.enable_tables = enable_tables
        if inject_heading_paths is not None:
            cfg.inject_heading_paths = inject_heading_paths

        self.config = cfg
        self.site_chrome = site_chrome
        self.noise_index = (
            NoiseAnchorIndex(threshold=cfg.dvdf_threshold) if cfg.enable_dvdf else None
        )

    def extract(self, html: str, url: str | None = None) -> ExtractResult:
        cfg = self.config
        if cfg.page_type.value == "unknown" and url:
            cfg = PipelineConfig.from_strictness(
                cfg.strictness,
                infer_page_type(url, html),
                enable_schema=cfg.enable_schema,
                enable_tables=cfg.enable_tables,
                enable_dvdf=cfg.enable_dvdf,
                enable_stce=cfg.enable_stce,
                inject_heading_paths=cfg.inject_heading_paths,
                min_chars=cfg.min_chars,
                max_link_density=cfg.max_link_density,
                min_text_density=cfg.min_text_density,
                max_noise_block_chars=cfg.max_noise_block_chars,
                max_rejected_drop_chars=cfg.max_rejected_drop_chars,
                dvdf_threshold=cfg.dvdf_threshold,
                stce_min_pages=cfg.stce_min_pages,
                stce_frequency=cfg.stce_frequency,
                stce_max_block_chars=cfg.stce_max_block_chars,
                stce_require_chrome_features=cfg.stce_require_chrome_features,
            )
            self.config = cfg
            if cfg.enable_dvdf:
                self.noise_index = NoiseAnchorIndex(threshold=cfg.dvdf_threshold)

        # 0) Input quality — warn on JS shells / thin HTML (caller must render)
        input_quality = assess_input_html(html)

        # 1) Parse — keep <script> so JSON-LD is visible
        soup = parse_html(html)

        # 2) Schema BEFORE stripping scripts (JSON-LD is inside script tags)
        front: dict[str, Any] = {}
        if cfg.enable_schema:
            front = fuse_front_matter(soup, url=url)

        # 3) Hard clean
        strip_non_content_tags(soup)

        # 4) STCE — site-learned chrome (only if model provided)
        stce_removed = 0
        stce_group = None
        if cfg.enable_stce and self.site_chrome is not None:
            stce_group = self.site_chrome.group_key
            expected = site_group_key(url)
            # Allow match on host-only if path prefix differs slightly
            if (
                self.site_chrome.group_key == expected
                or self.site_chrome.group_key.split("/")[0] == (expected.split("/")[0])
            ):
                stce_removed = apply_site_chrome(soup, self.site_chrome)

        # 5) Structural chrome
        prune_noise_subtrees(soup, max_noise_block_chars=cfg.max_noise_block_chars)

        # 6) Density + DVDF
        density_cfg = cfg.density_config()
        blocks = candidate_blocks(soup, density_cfg)
        scored = score_blocks(blocks, density_cfg)
        if self.noise_index is not None:
            scored = self.noise_index.apply(scored)

        # Drop only leaf-ish rejected nodes. Decomposing parent div/section whose
        # get_text() matches a rejected block also kills nested kept content
        # (common on card grids / instance-type catalogs).
        rejected_texts = {b.text for b in scored if not b.keep}
        drop_tags = ["p", "li"]
        if cfg.strictness == Strictness.AGGRESSIVE:
            drop_tags = ["p", "li", "div", "section"]
        for tag in list(soup.find_all(drop_tags)):
            if not isinstance(tag, Tag):
                continue
            text = tag.get_text(" ", strip=True)
            if text not in rejected_texts:
                continue
            if tag.name in {"h1", "h2", "h3", "h4", "h5", "h6", "table", "tr", "pre"}:
                continue
            if len(text) >= cfg.max_rejected_drop_chars:
                continue
            # Never drop a container that still holds a heading.
            if tag.find(["h1", "h2", "h3", "h4", "h5", "h6"]):
                continue
            tag.decompose()

        # 7) Tables
        n_tables = 0
        if cfg.enable_tables:
            n_tables = replace_tables_with_linearized(soup)

        # 8) Markdown
        body_md = soup_to_markdown(soup, inject_heading_paths=cfg.inject_heading_paths)
        md = front_matter_yaml(front) + body_md if front else body_md

        kept = sum(1 for b in scored if b.keep)
        warnings = list(input_quality.warnings)
        # Also warn when extraction itself collapsed despite non-thin input.
        if (
            not input_quality.is_thin
            and estimate_tokens(md) < 40
            and kept <= 1
        ):
            warnings.append(
                "Extraction produced very little Markdown despite non-thin input HTML. "
                "Inspect diagnostics or try --priority coverage."
            )
        return ExtractResult(
            url=url,
            markdown=md,
            front_matter={k: v for k, v in front.items() if not str(k).startswith("_")},
            n_blocks_in=len(scored),
            n_blocks_kept=kept,
            n_tables=n_tables,
            tokens_estimate=estimate_tokens(md),
            method="chromerag",
            warnings=warnings,
            input_quality=input_quality.as_dict(),
            diagnostics={
                "strictness": cfg.strictness.value,
                "content_priority": cfg.content_priority.value,
                "page_type": cfg.page_type.value,
                "schema_sources": front.get("_sources", {}),
                "stce_group": stce_group,
                "stce_removed": stce_removed,
                "stce_signatures": len(self.site_chrome.signatures) if self.site_chrome else 0,
                "input_quality": input_quality.as_dict(),
                "rejected_sample": [
                    {"text": b.text[:120], "reason": b.reason, "noise": b.noise_cosine}
                    for b in scored
                    if not b.keep
                ][:15],
                "kept_sample": [
                    {"text": b.text[:120], "ld": round(b.link_density, 3), "noise": b.noise_cosine}
                    for b in scored
                    if b.keep
                ][:10],
            },
        )

    def extract_file(self, path: str, url: str | None = None) -> ExtractResult:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return self.extract(f.read(), url=url)
