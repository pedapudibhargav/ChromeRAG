"""Main extraction pipeline.

Order (intentional):
  1. Parse HTML (keep scripts)
  2. Schema harvest (JSON-LD lives in <script type=ld+json>)
  3. Strip scripts/styles
  4. Hidden / skip-link removal
  5. Optional STCE (site-template chrome from multi-page mine)
  6. Structural chrome prune
  7. Density + DVDF residual prune
  8. Table KV linearization
  9. Markdown (+ optional heading paths)
"""

from __future__ import annotations

import copy
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from chromerag.config import ContentPriority, PipelineConfig, Strictness, infer_page_type
from chromerag.content_root import find_content_root
from chromerag.density import (
    ElementCache,
    candidate_blocks,
    parse_html,
    prune_noise_subtrees,
    score_blocks,
    strip_non_content_tags,
)
from chromerag.dvdf import NoiseAnchorIndex
from chromerag.hidden import remove_hidden_nodes, remove_skip_links
from chromerag.markdown_out import front_matter_yaml, soup_to_markdown
from chromerag.models import ExtractResult
from chromerag.input_quality import InputQualityReport, assess_input_html
from chromerag.rules_engine import DEFAULT_INDEX, RuleHit
from chromerag.schema_fusion import fuse_front_matter
from chromerag.site_chrome import SiteChromeModel, apply_site_chrome, site_group_key
from chromerag.tables import replace_tables_with_linearized


def estimate_tokens(text: str) -> int:
    """Approximate token count (characters / 4), computed offline."""
    return max(1, len(text) // 4)


def _body_word_count(soup: BeautifulSoup) -> int:
    body = soup.body
    if body is None or not isinstance(body, Tag):
        return 0
    return len(re.findall(r"\w+", body.get_text(" ", strip=True).lower()))


def _resolve_cfg(base: PipelineConfig, url: str | None, html: str) -> PipelineConfig:
    if base.page_type.value != "unknown" or not url:
        return base
    return PipelineConfig.from_strictness(
        base.strictness,
        infer_page_type(url, html),
        enable_schema=base.enable_schema,
        enable_tables=base.enable_tables,
        enable_dvdf=base.enable_dvdf,
        enable_stce=base.enable_stce,
        inject_heading_paths=base.inject_heading_paths,
        min_chars=base.min_chars,
        max_link_density=base.max_link_density,
        min_text_density=base.min_text_density,
        max_noise_block_chars=base.max_noise_block_chars,
        max_rejected_drop_chars=base.max_rejected_drop_chars,
        dvdf_threshold=base.dvdf_threshold,
        stce_min_pages=base.stce_min_pages,
        stce_frequency=base.stce_frequency,
        stce_max_block_chars=base.stce_max_block_chars,
        stce_require_chrome_features=base.stce_require_chrome_features,
    )


class ChromeRAG:
    """Enterprise HTML → RAG-ready Markdown."""

    def __init__(
        self,
        config: PipelineConfig | None = None,
        *,
        strictness: Strictness | str = Strictness.BALANCED,
        site_chrome: SiteChromeModel | None = None,
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

    def _noise_index(self, cfg: PipelineConfig) -> NoiseAnchorIndex | None:
        if not cfg.enable_dvdf:
            return None
        return NoiseAnchorIndex(threshold=cfg.dvdf_threshold)

    def _extract_core(
        self,
        html: str,
        url: str | None,
        cfg: PipelineConfig,
        *,
        force_body_root: bool = False,
        input_quality: InputQualityReport | None = None,
        front: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any], ExtractResult]:
        soup = parse_html(html)
        if input_quality is None:
            input_quality = assess_input_html(html, soup=soup)
        if front is None:
            front = {}
            if cfg.enable_schema:
                front = fuse_front_matter(soup, url=url)

        strip_non_content_tags(soup)
        remove_hidden_nodes(soup)
        remove_skip_links(soup)

        body_words = _body_word_count(soup)
        if force_body_root:
            content_root = soup.body if isinstance(soup.body, Tag) else soup
            root_label = "body-forced"
        else:
            content_root, root_label = find_content_root(soup, cfg.page_type)

        rule_hits: list[RuleHit] = []
        rule_totals: dict[str, int] = {}
        if cfg.enable_rules:
            root_tag = content_root if isinstance(content_root, Tag) else None
            rule_hits, rule_totals = DEFAULT_INDEX.apply(
                soup,
                content_root=root_tag,
                page_type=cfg.page_type.value,
            )

        elem_cache = ElementCache()
        stce_removed = 0
        stce_group = None
        if cfg.enable_stce and self.site_chrome is not None:
            stce_group = self.site_chrome.group_key
            expected = site_group_key(url)
            if (
                self.site_chrome.group_key == expected
                or self.site_chrome.group_key.split("/")[0] == (expected.split("/")[0])
            ):
                stce_removed = apply_site_chrome(soup, self.site_chrome)

        prune_noise_subtrees(soup, max_noise_block_chars=cfg.max_noise_block_chars, cache=elem_cache)

        density_cfg = cfg.density_config()
        blocks = candidate_blocks(
            soup,
            density_cfg,
            cache=elem_cache,
            content_root=content_root if isinstance(content_root, Tag) else None,
        )
        scored = score_blocks(blocks, density_cfg, cache=elem_cache)
        noise_index = self._noise_index(cfg)
        if noise_index is not None:
            scored = noise_index.apply(scored)

        rejected_texts = {b.text for b in scored if not b.keep}
        drop_tags = ["p", "li"]
        if cfg.strictness == Strictness.AGGRESSIVE:
            drop_tags = ["p", "li", "div", "section"]
        for tag in [t for t in soup.find_all(drop_tags) if isinstance(t, Tag)]:
            text = tag.get_text(" ", strip=True)
            if text not in rejected_texts:
                continue
            if tag.name in {"h1", "h2", "h3", "h4", "h5", "h6", "table", "tr", "pre"}:
                continue
            if len(text) >= cfg.max_rejected_drop_chars:
                continue
            if tag.find(["h1", "h2", "h3", "h4", "h5", "h6"]):
                continue
            tag.decompose()

        n_tables = replace_tables_with_linearized(soup) if cfg.enable_tables else 0
        root_tag = content_root if isinstance(content_root, Tag) else None
        body_md = soup_to_markdown(
            soup,
            inject_heading_paths=cfg.inject_heading_paths,
            content_root=root_tag,
        )
        md = front_matter_yaml(front) + body_md if front else body_md
        kept = sum(1 for b in scored if b.keep)
        token_est = estimate_tokens(md)

        diagnostics = {
            "strictness": cfg.strictness.value,
            "content_priority": cfg.content_priority.value,
            "page_type": cfg.page_type.value,
            "content_root": root_label,
            "removed": [{"rule": h.rule_id, "chars": h.chars} for h in rule_hits[:50]],
            "removed_total": sum(rule_totals.values()),
            "removed_rules": len(rule_totals),
            "schema_sources": front.get("_sources", {}),
            "stce_group": stce_group,
            "stce_removed": stce_removed,
            "stce_signatures": len(self.site_chrome.signatures) if self.site_chrome else 0,
            "input_quality": input_quality.as_dict(),
            "body_words": body_words,
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
        }
        result = ExtractResult(
            url=url,
            markdown=md,
            front_matter={k: v for k, v in front.items() if not str(k).startswith("_")},
            n_blocks_in=len(scored),
            n_blocks_kept=kept,
            n_tables=n_tables,
            tokens_estimate=token_est,
            method="chromerag",
            warnings=list(input_quality.warnings),
            input_quality=input_quality.as_dict(),
            diagnostics=diagnostics,
        )
        meta = {"front": front, "input_quality": input_quality, "body_words": body_words}
        return md, meta, result

    def extract(self, html: str, url: str | None = None) -> ExtractResult:
        cfg = _resolve_cfg(self.config, url, html)
        md, meta, result = self._extract_core(html, url, cfg)
        body_words = int(meta["body_words"])
        out_words = len(re.findall(r"\w+", md.lower()))
        collapsed = result.tokens_estimate < 40 or (
            body_words > 0 and out_words < 0.15 * body_words
        )
        if collapsed and not meta["input_quality"].is_thin:
            coverage_cfg = PipelineConfig.from_priority(
                ContentPriority.COVERAGE,
                page_type=cfg.page_type,
                enable_schema=cfg.enable_schema,
                enable_tables=cfg.enable_tables,
                enable_dvdf=cfg.enable_dvdf,
                enable_stce=cfg.enable_stce,
                inject_heading_paths=cfg.inject_heading_paths,
            )
            md2, _, result2 = self._extract_core(
                html,
                url,
                coverage_cfg,
                force_body_root=True,
                input_quality=meta["input_quality"],
                front=copy.deepcopy(meta["front"]),
            )
            if estimate_tokens(md2) > result.tokens_estimate:
                result = result2
                result.warnings = list(meta["input_quality"].warnings) + [
                    "Extraction collapsed with detected content root; retried with body root "
                    "and coverage thresholds."
                ]
                return result

        warnings = list(meta["input_quality"].warnings)
        if (
            not meta["input_quality"].is_thin
            and result.tokens_estimate < 40
            and result.n_blocks_kept <= 1
        ):
            warnings.append(
                "Extraction produced very little Markdown despite non-thin input HTML. "
                "Inspect diagnostics or try --priority coverage."
            )
        result.warnings = warnings
        return result

    def extract_file(self, path: str, url: str | None = None) -> ExtractResult:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return self.extract(f.read(), url=url)
