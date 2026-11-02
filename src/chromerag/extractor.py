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
from dataclasses import replace
from functools import lru_cache
from typing import Any

import numpy as np
from bs4 import BeautifulSoup, Tag

from chromerag.blockfeatures import block_features, find_blocks, wrap_loose_text
from chromerag.collapse import dual_region_candidate, extraction_looks_collapsed
from chromerag.config import (
    PipelineConfig,
    Strictness,
    coverage_fallback,
    infer_page_type,
    with_page_type,
)
from chromerag.content_root import find_content_root
from chromerag.density import (
    NOISE_TOKENS,
    ElementCache,
    _attr_tokens,
    candidate_blocks,
    parse_html,
    prune_noise_subtrees,
    score_blocks,
    strip_non_content_tags,
)
from chromerag.dvdf import NoiseAnchorIndex
from chromerag.generic_chrome import drop_generic_chrome, infer_page_kind_hint
from chromerag.hidden import remove_hidden_nodes, remove_skip_links
from chromerag.input_quality import InputQualityReport, assess_input_html
from chromerag.lbc import TwoStageModel, default_two_stage
from chromerag.markdown_out import consume_trim_notes as consume_md_trim_notes
from chromerag.markdown_out import front_matter_yaml, soup_to_markdown
from chromerag.markdown_out import reset_trim_notes as reset_md_trim_notes
from chromerag.models import BlockScore, ExtractResult
from chromerag.rules_engine import DEFAULT_INDEX, RuleHit, RuleIndex
from chromerag.schema_fusion import fuse_front_matter
from chromerag.site_chrome import SiteChromeModel, apply_site_chrome, site_group_key
from chromerag.tables import (
    _own_rows,
    is_rescueable_data_table,
    replace_tables_with_linearized,
    unwrap_layout_tables,
)
from chromerag.tables import (
    consume_trim_notes as consume_table_trim_notes,
)
from chromerag.tables import (
    reset_trim_notes as reset_table_trim_notes,
)
from chromerag.textio import decode_html
from chromerag.trafilatura_ideas import apply_trafilatura_ideas
from chromerag.treestats import TreeStats


def estimate_tokens(text: str) -> int:
    """Approximate token count (characters / 4), computed offline."""
    return max(1, len(text) // 4)


_FRONT_MATTER_RE = re.compile(r"^---\n.*?\n---\n*", re.S)
# Visible body large enough that a JS-shell / thin-input warning is misleading.
_BODY_WORDS_RICH = 80


def _markdown_body(md: str) -> str:
    """Markdown with YAML front matter stripped."""
    return _FRONT_MATTER_RE.sub("", md or "", count=1)


def _markdown_body_words(md: str) -> int:
    """Word count of extracted Markdown excluding YAML front matter."""
    return len(re.findall(r"\w+", _markdown_body(md).lower()))


def _body_word_count(soup: BeautifulSoup) -> int:
    body = soup.body
    if body is None or not isinstance(body, Tag):
        return 0
    return len(re.findall(r"\w+", body.get_text(" ", strip=True).lower()))


def _sanitize_unicode(text: str) -> str:
    """Drop lone surrogates so UTF-8 encoding never raises."""
    return text.encode("utf-8", errors="replace").decode("utf-8")


def _resolve_cfg(base: PipelineConfig, url: str | None, html: str) -> PipelineConfig:
    if base.page_type.value != "unknown" or not url:
        return base
    return with_page_type(base, infer_page_type(url, html))


@lru_cache(maxsize=8)
def _noise_index_for(threshold: float) -> NoiseAnchorIndex:
    """One shared anchor bank per threshold (it never changes after construction)."""
    return NoiseAnchorIndex(threshold=threshold)


# Pages with fewer blocks than this are kept whole by the learned classifier.
LBC_MIN_BLOCKS = 4
_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_LBC_HEADING_RESCUE_MIN = 0.08
_LBC_TITLE_FALLBACK_MIN = 0.03
_LBC_LEAD_MIN = 0.10
_LBC_LEAD_MIN_WORDS = 8
# Below this expected F1 the page gets a warning (on WCXB dev such pages score 0.57 on average, the rest 0.88).
LOW_CONFIDENCE_F1 = 0.70
_SEMANTIC_LEAF = frozenset({"dt", "dd"})
_LBC_LONG_TABLE_ROWS = 500
_PRODUCT_DL_MAX_TERM = 40
_PRODUCT_DL_MAX_DEF = 80


class StopExtraction(Exception):
    """Raised by the training hook to end extraction right after cleaning."""


class ChromeRAG:
    """Enterprise HTML → RAG-ready Markdown."""

    def __init__(
        self,
        config: PipelineConfig | None = None,
        *,
        strictness: Strictness | str = Strictness.BALANCED,
        site_chrome: SiteChromeModel | None = None,
        rule_index: RuleIndex | None = None,
        rule_disabled_groups: set[str] | None = None,
        rule_disabled_prefixes: set[str] | None = None,
        lbc_model: TwoStageModel | None = None,
        density: Any = None,
        dvdf_threshold: float | None = None,
        enable_dvdf: bool | None = None,
        enable_schema: bool | None = None,
        enable_tables: bool | None = None,
        table_format: str | None = None,
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
        if table_format is not None:
            cfg.table_format = table_format
        if inject_heading_paths is not None:
            cfg.inject_heading_paths = inject_heading_paths

        self.config = cfg
        self.site_chrome = site_chrome
        self.rule_index = rule_index or DEFAULT_INDEX
        self._rule_disabled_groups = rule_disabled_groups
        self._rule_disabled_prefixes = rule_disabled_prefixes
        self.lbc_model = lbc_model if lbc_model is not None else default_two_stage()
        self._capture: Any = None

    def _drop_by_classifier(
        self, soup: BeautifulSoup, body: Tag, content_root: Any, cfg: PipelineConfig
    ) -> tuple[int, int, dict[str, float]]:
        """Remove blocks the learned classifier scores below ``cfg.lbc_threshold``."""
        stats = TreeStats(body)
        blocks = find_blocks(body, stats)
        if len(blocks) < LBC_MIN_BLOCKS:
            return len(blocks), len(blocks), {}  # too little page to judge: the model never saw pages like this
        root = content_root if isinstance(content_root, Tag) else None
        X, box = block_features(blocks, body, stats, root)
        chars = np.array([len(b.text) for b in blocks])
        proba = (
            self.lbc_model.predict(X.astype("float64"), chars, box)
            if cfg.enable_lbc_stage2 and self.lbc_model.second is not None
            else self.lbc_model.first.predict_proba(X.astype("float64"))
        )
        seen: set[str] = set()
        structure = cfg.enable_lbc_structure_rules
        title_block = self._title_block(soup, blocks) if structure and cfg.lbc_keep_title else None
        if title_block is None and structure and cfg.lbc_keep_title and cfg.lbc_title_fallback:
            title_block = self._title_fallback(body, root, blocks, proba)
        base_keep: list[bool] = []
        for block, p in zip(blocks, proba, strict=True):
            key = " ".join(block.text.lower().split())
            if block is title_block:
                base_keep.append(True)
                seen.add(key)
            elif p < cfg.lbc_threshold or (cfg.lbc_drop_repeats and len(key) >= 30 and key in seen):
                base_keep.append(False)
            else:
                base_keep.append(True)
                seen.add(key)
        keep = list(base_keep)
        if structure and cfg.lbc_rescue_headings:
            for i, (block, p) in enumerate(zip(blocks, proba, strict=True)):
                if keep[i] or p >= cfg.lbc_threshold or p < _LBC_HEADING_RESCUE_MIN:
                    continue
                if block.tag.name not in _HEADING_TAGS:
                    continue
                for j in range(i + 1, min(i + 3, len(blocks))):
                    if base_keep[j]:
                        keep[i] = True
                        break
        if structure and cfg.lbc_rescue_lead and title_block is not None:
            for i, block in enumerate(blocks):
                if block is not title_block:
                    continue
                j = i + 1
                if j >= len(blocks) or keep[j]:
                    break
                lead, p = blocks[j], proba[j]
                if lead.tag.name in {"p", "div"} and len(lead.text.split()) >= _LBC_LEAD_MIN_WORDS and p >= _LBC_LEAD_MIN:
                    keep[j] = True
                break
        tables_rescued = 0
        semantic_rescued = 0
        if structure and cfg.lbc_rescue_tables and cfg.enable_tables:
            keep, tables_rescued = self._rescue_data_tables(blocks, keep, stats, root, proba, cfg)
        if structure and cfg.lbc_rescue_headings:
            keep, semantic_rescued = self._rescue_semantic_blocks(blocks, keep, root, cfg)
        dual_candidate = dual_region_candidate(blocks, proba, box)
        for block, k in zip(blocks, keep, strict=True):
            if not k:
                block.tag.decompose()
        kept = sum(keep)
        # What the model expects of its own output, from its probabilities: a page with many
        # blocks near 0.5 gets a low expected F1 and deserves a look.
        words = np.maximum(np.array([len(b.text.split()) for b in blocks], dtype=np.float64), 1.0)
        kept_mask = np.array(keep)
        tp = float((words * proba)[kept_mask].sum())
        ref = float((words * proba).sum())
        out_words = float(words[kept_mask].sum())
        exp_p, exp_r = tp / max(out_words, 1.0), tp / max(ref, 1.0)
        exp_f = 2 * exp_p * exp_r / max(exp_p + exp_r, 1e-9)
        return (
            len(blocks),
            kept,
            {
                "expected_precision": exp_p,
                "expected_recall": exp_r,
                "expected_f1": exp_f,
                "tables_rescued": tables_rescued,
                "semantic_rescued": semantic_rescued,
                "dual_region_candidate": dual_candidate,
            },
        )

    @staticmethod
    def _title_block(soup: BeautifulSoup, blocks: list[Any]) -> Any:
        """The page's own heading: the first ``h1`` whose words mostly occur in ``<title>``. It is kept so that
        every chunk source carries its title, whatever the classifier thinks of a three-word heading."""
        node = soup.find("title")
        title = {w for w in re.findall(r"\w+", node.get_text(' ', strip=True).lower())} if node else set()
        if not title:
            return None
        for block in blocks:
            if block.tag.name == "h1":
                words = re.findall(r"\w+", block.text.lower())
                if len(words) >= 2 and sum(w in title for w in words) / len(words) >= 0.5:
                    return block
        return None

    @staticmethod
    def _title_fallback(body: Tag, content_root: Tag | None, blocks: list[Any], proba: np.ndarray) -> Any:
        """First ``h1`` inside the content root (or body) with enough words and a non-trivial score."""
        root = content_root if content_root is not None else body
        for i, block in enumerate(blocks):
            if block.tag.name != "h1":
                continue
            if root is not body:
                parent = block.tag.parent
                while parent is not None and parent is not root:
                    parent = parent.parent
                if parent is not root:
                    continue
            words = re.findall(r"\w+", block.text.lower())
            if len(words) >= 2 and proba[i] >= _LBC_TITLE_FALLBACK_MIN:
                return block
        return None

    @staticmethod
    def _rescue_data_tables(
        blocks: list[Any],
        keep: list[bool],
        stats: TreeStats,
        content_root: Tag | None,
        proba: np.ndarray,
        cfg: PipelineConfig,
    ) -> tuple[list[bool], int]:
        """Keep dropped data tables under a kept section heading (same content root).

        Reads the original ``keep`` list so rescues cannot cascade. When a heading and its
        data table both sit just under the threshold, keeps the pair if the heading would
        qualify for rescue once the table counted as its body. Section bounds: the next
        heading ends the window. Repeat-dropped duplicates are not resurrected.
        """
        base = list(keep)
        out = list(keep)
        rescued = 0
        kept_texts = {
            " ".join(blocks[i].text.lower().split())
            for i, k in enumerate(base)
            if k and len(blocks[i].text) >= 30
        }
        heading_idxs = [i for i, b in enumerate(blocks) if b.tag.name in _HEADING_TAGS]

        def _in_root(tag: Tag) -> bool:
            if content_root is None:
                return True
            parent: Tag | None = tag
            while parent is not None:
                if parent is content_root:
                    return True
                parent = parent.parent if isinstance(parent.parent, Tag) else None
            return False

        def _nearest_heading(i: int) -> int | None:
            for j in range(i - 1, -1, -1):
                if blocks[j].tag.name in _HEADING_TAGS:
                    return j
            return None

        def _section_end(h: int) -> int:
            for j in heading_idxs:
                if j > h:
                    return j
            return len(blocks)

        for i, block in enumerate(blocks):
            if base[i] or block.tag.name != "table":
                continue
            if not _in_root(block.tag):
                continue
            key = " ".join(block.text.lower().split())
            # Do not resurrect a table whose text was already kept (repeat-drop).
            if len(key) >= 30 and key in kept_texts:
                continue
            if not is_rescueable_data_table(block.tag, stats.link_density(block.tag)):
                continue
            # A grid this long is data whatever the model thinks of its section heading.
            if len(_own_rows(block.tag)) >= _LBC_LONG_TABLE_ROWS:
                out[i] = True
                rescued += 1
                continue
            h = _nearest_heading(i)
            if h is None or not _in_root(blocks[h].tag):
                continue
            # Next heading ends the section; tables past it belong elsewhere.
            if i >= _section_end(h):
                continue
            # Nearest heading above was kept (section body, including orphan fill).
            if base[h]:
                out[i] = True
                rescued += 1
                if len(key) >= 30:
                    kept_texts.add(key)
                continue
            # Pair-rescue: heading in the rescue band, table still inside its section.
            if not cfg.lbc_rescue_headings:
                continue
            p = float(proba[h])
            if p < _LBC_HEADING_RESCUE_MIN or p >= cfg.lbc_threshold:
                continue
            if i - h > 2:
                continue
            out[h] = True
            out[i] = True
            rescued += 1
            if len(key) >= 30:
                kept_texts.add(key)
        return out, rescued

    @staticmethod
    def _is_product_metafield_dl(dl: Tag) -> bool:
        """True for short Shopify-style spec grids; long glossary entries stay rescuable."""
        if _attr_tokens(dl) & NOISE_TOKENS:
            return True
        dts = dl.find_all("dt", recursive=False) or dl.find_all("dt")
        dds = dl.find_all("dd", recursive=False) or dl.find_all("dd")
        if not dts or not dds:
            return False
        short_terms = all(len(dt.get_text(" ", strip=True)) <= _PRODUCT_DL_MAX_TERM for dt in dts)
        short_defs = all(len(dd.get_text(" ", strip=True)) <= _PRODUCT_DL_MAX_DEF for dd in dds)
        # Count alone is not enough: a long glossary with >10 entries must remain rescuable.
        if len(dts) >= 4 and short_terms and short_defs:
            return True
        return False

    @staticmethod
    def _rescue_semantic_blocks(
        blocks: list[Any],
        keep: list[bool],
        content_root: Tag | None,
        cfg: PipelineConfig,
    ) -> tuple[list[bool], int]:
        """Keep glossary ``dl`` pairs under a kept section heading (not product spec grids)."""
        base = list(keep)
        out = list(keep)
        rescued = 0
        heading_idxs = [i for i, b in enumerate(blocks) if b.tag.name in _HEADING_TAGS]

        def _in_root(tag: Tag) -> bool:
            if content_root is None:
                return True
            parent: Tag | None = tag
            while parent is not None:
                if parent is content_root:
                    return True
                parent = parent.parent if isinstance(parent.parent, Tag) else None
            return False

        def _nearest_heading(i: int) -> int | None:
            for j in range(i - 1, -1, -1):
                if blocks[j].tag.name in _HEADING_TAGS:
                    return j
            return None

        def _section_end(h: int) -> int:
            for j in heading_idxs:
                if j > h:
                    return j
            return len(blocks)

        for i, block in enumerate(blocks):
            if base[i] or block.tag.name not in _SEMANTIC_LEAF:
                continue
            if not _in_root(block.tag):
                continue
            name = block.tag.name
            if name in {"dt", "dd"}:
                dl = block.tag.find_parent("dl")
                if dl is None or ChromeRAG._is_product_metafield_dl(dl):
                    continue
            h = _nearest_heading(i)
            if h is None or not base[h] or not _in_root(blocks[h].tag):
                continue
            if i >= _section_end(h):
                continue
            out[i] = True
            rescued += 1
        return out, rescued

    def _noise_index(self, cfg: PipelineConfig) -> NoiseAnchorIndex | None:
        if not cfg.enable_dvdf:
            return None
        return _noise_index_for(cfg.dvdf_threshold)

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
        reset_table_trim_notes()
        reset_md_trim_notes()
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
        if cfg.enable_tables:
            unwrap_layout_tables(soup)

        body_words = _body_word_count(soup)
        if force_body_root:
            content_root = soup.body if isinstance(soup.body, Tag) else soup
            root_label = "body-forced"
        else:
            content_root, root_label = find_content_root(soup, cfg.page_type, body_words)

        body = soup.body if isinstance(soup.body, Tag) else soup
        stats: TreeStats | None = TreeStats(body)

        rule_hits: list[RuleHit] = []
        rule_totals: dict[str, int] = {}
        root_tag = content_root if isinstance(content_root, Tag) else None
        if cfg.enable_rules:
            rule_hits, rule_totals = self.rule_index.apply(
                soup,
                content_root=root_tag,
                page_type=cfg.page_type.value,
                stats=stats,
                disabled_groups=self._rule_disabled_groups,
                disabled_prefixes=self._rule_disabled_prefixes,
            )
            if rule_hits:
                stats = None  # the tree changed

        traf_stats = (
            apply_trafilatura_ideas(soup, cfg, root_tag, stats=stats or TreeStats(body))
            if cfg.enable_trafilatura_rules
            else {}
        )
        if any(traf_stats.values()):
            stats = None

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
                if stce_removed:
                    stats = None

        page_kind = infer_page_kind_hint(soup)
        generic_chrome = (
            drop_generic_chrome(soup, root_tag, page_kind, cfg=cfg) if cfg.enable_generic_chrome else {}
        )
        if any(generic_chrome.values()):
            stats = None

        if cfg.enable_chrome_prune:
            prune_noise_subtrees(
                soup,
                max_noise_block_chars=cfg.max_noise_block_chars,
                cache=elem_cache,
                stats=stats or TreeStats(body),
            )
        if self._capture is not None or (cfg.enable_lbc and self.lbc_model is not None):
            wrap_loose_text(body)  # text between blocks becomes blocks, so the classifier sees it
        if self._capture is not None:  # training hook: hand over the cleaned page and stop
            self._capture(soup, content_root if isinstance(content_root, Tag) else None)
            raise StopExtraction
        use_lbc = cfg.enable_lbc and self.lbc_model is not None
        scored: list[BlockScore] = []
        lbc_in = lbc_kept = 0
        lbc_conf: dict[str, float] = {}
        if use_lbc:
            lbc_in, lbc_kept, lbc_conf = self._drop_by_classifier(soup, body, content_root, cfg)
            if cfg.lbc_whole_page:
                content_root = body
        else:
            stats = TreeStats(body, serialized=True)  # pruning removed nodes; measure what is left
            density_cfg = cfg.density_config()
            blocks = candidate_blocks(
                soup,
                density_cfg,
                cache=elem_cache,
                content_root=content_root if isinstance(content_root, Tag) else None,
                stats=stats,
            )
            scored = score_blocks(blocks, density_cfg, cache=elem_cache, stats=stats)
            noise_index = self._noise_index(cfg)
            if noise_index is not None:
                scored = noise_index.apply(scored)

            rejected_texts = {b.text for b in scored if not b.keep}
            drop_tags = ["p", "li"]
            if cfg.strictness == Strictness.AGGRESSIVE:
                drop_tags = ["p", "li", "div", "section"]
            for tag in [t for t in soup.find_all(drop_tags) if isinstance(t, Tag)]:
                # Long blocks are never dropped here; checking that first avoids reading their text.
                if stats.text_len(tag) >= cfg.max_rejected_drop_chars:
                    continue
                text = tag.get_text(" ", strip=True)
                if text not in rejected_texts:
                    continue
                if tag.name in {"h1", "h2", "h3", "h4", "h5", "h6", "table", "tr", "pre"}:
                    continue
                if tag.find(["h1", "h2", "h3", "h4", "h5", "h6"]):
                    continue
                tag.decompose()

        n_tables = (
            replace_tables_with_linearized(soup, table_format=cfg.table_format)
            if cfg.enable_tables
            else 0
        )
        root_tag = content_root if isinstance(content_root, Tag) else None
        body_md = soup_to_markdown(
            soup,
            inject_heading_paths=cfg.inject_heading_paths,
            content_root=root_tag,
            links=cfg.include_links,
        )
        md = front_matter_yaml(front) + body_md if front else body_md
        kept = lbc_kept if use_lbc else sum(1 for b in scored if b.keep)
        token_est = estimate_tokens(md)

        diagnostics = {
            "strictness": cfg.strictness.value,
            "content_priority": cfg.content_priority.value,
            "page_type": cfg.page_type.value,
            "content_root": root_label,
            "lbc": lbc_conf,
            "removed": [{"rule": h.rule_id, "chars": h.chars} for h in rule_hits[:50]],
            "removed_total": sum(rule_totals.values()),
            "removed_rules": len(rule_totals),
            "schema_sources": front.get("_sources", {}),
            "stce_group": stce_group,
            "stce_removed": stce_removed,
            "stce_signatures": len(self.site_chrome.signatures) if self.site_chrome else 0,
            "generic_chrome": generic_chrome,
            "page_kind_hint": page_kind,
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
            n_blocks_in=lbc_in if use_lbc else len(scored),
            n_blocks_kept=kept,
            n_tables=n_tables,
            tokens_estimate=token_est,
            method="chromerag",
            warnings=list(input_quality.warnings),
            input_quality=input_quality.as_dict(),
            diagnostics=diagnostics,
        )
        # Capture this pass's notes before a retry clears the contextvars.
        pass_notes = consume_table_trim_notes() + consume_md_trim_notes()
        meta = {
            "front": front,
            "input_quality": input_quality,
            "body_words": body_words,
            "trim_notes": pass_notes,
        }
        return md, meta, result

    def extract(self, html: str | bytes, url: str | None = None) -> ExtractResult:
        if not isinstance(html, str):
            html = decode_html(html)
        html = _sanitize_unicode(html)
        cfg = _resolve_cfg(self.config, url, html)
        try:
            return self._extract_with_retries(html, url, cfg)
        except (RecursionError, UnicodeEncodeError, UnicodeDecodeError) as exc:
            warn = (
                f"Extraction aborted ({type(exc).__name__}); returning empty Markdown. "
                "Input may be deeply nested or contain invalid Unicode."
            )
            return ExtractResult(
                url=url,
                markdown="",
                front_matter={},
                n_blocks_in=0,
                n_blocks_kept=0,
                n_tables=0,
                tokens_estimate=1,
                method="chromerag",
                warnings=[warn],
                input_quality={},
                diagnostics={"abort": type(exc).__name__},
            )

    def _extract_with_retries(
        self, html: str, url: str | None, cfg: PipelineConfig
    ) -> ExtractResult:
        md, meta, result = self._extract_core(html, url, cfg)
        chosen_trim_notes: list[str] = list(meta.get("trim_notes") or [])
        body_words = int(meta["body_words"])
        out_words = _markdown_body_words(md)
        # Front matter alone can inflate tokens_estimate; collapse uses body words.
        lbc_diag = result.diagnostics.get("lbc") or {}
        # dual_region_candidate stays diagnostic-only (no keep / retry effect).
        collapsed = extraction_looks_collapsed(
            out_words,
            body_words,
            n_blocks_in=result.n_blocks_in,
            n_blocks_kept=result.n_blocks_kept,
            expected_f1=lbc_diag.get("expected_f1"),
            dual_region_candidate=False,
            cfg=cfg,
        )
        retry_notes: list[str] = []
        # Keep the is_thin retry gate (noscript-heavy pages can look thin pre-unwrap but extract
        # well); still clear misleading JS-shell warnings after a rich body is observed.
        if collapsed and not meta["input_quality"].is_thin:
            coverage_cfg = coverage_fallback(cfg)
            first_out = out_words
            md2, meta2, result2 = self._extract_core(
                html,
                url,
                coverage_cfg,
                force_body_root=True,
                input_quality=meta["input_quality"],
                front=copy.deepcopy(meta["front"]),
            )
            # Compare on body words; only take the retry when the first pass was near-empty or
            # the retry is clearly longer (avoids trading precision for chrome-heavy coverage).
            md2_words = _markdown_body_words(md2)
            # Prefer body-word growth; also accept token growth so coverage retries that
            # add structured/table text still win when word counts are close.
            if (md2_words > first_out and (first_out < 40 or md2_words > 1.5 * first_out)) or (
                estimate_tokens(md2) > result.tokens_estimate and md2_words >= first_out
            ):
                result = result2
                md = md2
                out_words = md2_words
                chosen_trim_notes = list(meta2.get("trim_notes") or [])
                retry_notes.append(
                    "Extraction collapsed with detected content root; retried with body root "
                    "and coverage thresholds."
                )
            # Only when output is still near-empty: ratio-vs-body alone is unsafe on
            # chrome-heavy pages where a solid coverage retry is already << body_words.
            near_empty = _markdown_body_words(result.markdown) < 40
            lbc_dropped = result.n_blocks_in > result.n_blocks_kept
            # Pass-one found 0 blocks (empty main / over-prune): still allow a no-LBC retry.
            no_blocks = result.n_blocks_in == 0
            if (
                near_empty
                and cfg.enable_lbc
                and self.lbc_model is not None
                and (lbc_dropped or no_blocks)
            ):
                wide_cfg = replace(coverage_cfg, enable_lbc=False)
                md3, meta3, result3 = self._extract_core(
                    html,
                    url,
                    wide_cfg,
                    force_body_root=True,
                    input_quality=meta["input_quality"],
                    front=copy.deepcopy(meta["front"]),
                )
                if _markdown_body_words(md3) > _markdown_body_words(result.markdown):
                    result = result3
                    chosen_trim_notes = list(meta3.get("trim_notes") or [])
                    retry_notes.append(
                        "Extraction still collapsed after coverage retry; retried with body root "
                        "without the learned block filter."
                    )

        out_words = _markdown_body_words(result.markdown)
        result.markdown = _sanitize_unicode(result.markdown)
        # Drop misleading thin/JS-shell warnings when the cleaned body has real prose.
        iq_warnings = list(meta["input_quality"].warnings)
        if body_words >= _BODY_WORDS_RICH or out_words >= 40:
            iq_warnings = [
                w
                for w in iq_warnings
                if "JavaScript-rendered shell" not in w and "thin for RAG ingest" not in w
            ]
        warnings = iq_warnings + retry_notes
        input_looks_thin = meta["input_quality"].is_thin and body_words < _BODY_WORDS_RICH
        # Depend on body words (not tokens_estimate): front matter alone can look large.
        if out_words < 40 and result.n_blocks_kept <= 1 and (
            body_words >= _BODY_WORDS_RICH or not input_looks_thin
        ):
            warnings.append(
                "Extraction produced very little Markdown despite non-thin input HTML. "
                "Inspect diagnostics or try --priority coverage."
            )
        expected_f1 = result.diagnostics.get("lbc", {}).get("expected_f1")
        if expected_f1 is not None and expected_f1 < LOW_CONFIDENCE_F1:
            warnings.append(
                f"Low extraction confidence (expected F1 {expected_f1:.2f}): the model is unsure which "
                "blocks are content on this page. Check the output or try another priority."
            )
        has_table_trim_note = any(
            "truncated to" in n and "rows" in n for n in chosen_trim_notes
        )
        # Trim notes already name the row budget; only add a generic warn when notes are absent.
        if "[Table truncated after" in result.markdown and not has_table_trim_note:
            warnings.append(
                "One or more tables were truncated to a time-safe row budget."
            )
        warnings.extend(chosen_trim_notes)
        # Drop any notes left by a rejected retry so they cannot leak into the next extract.
        consume_table_trim_notes()
        consume_md_trim_notes()
        if result.diagnostics.get("generic_chrome", {}).get("chrome_time_safe_skip"):
            warnings.append(
                "Generic chrome heuristics were skipped on a very large DOM (time-safe path)."
            )
        result.warnings = warnings
        result.tokens_estimate = estimate_tokens(result.markdown)
        return result

    def extract_file(self, path: str, url: str | None = None) -> ExtractResult:
        with open(path, "rb") as f:
            return self.extract(f.read(), url=url)
