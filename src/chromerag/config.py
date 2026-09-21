"""Pipeline configuration — manageable strictness knobs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from chromerag.density import DensityConfig


class ContentPriority(str, Enum):
    """User-facing tradeoff: clean vectors vs keeping more relevant text.

    PRECISION — Prefer correctness of extracted text. Aggressively drop chrome;
                may lose some relevant chunks (lower content recall).
    COVERAGE  — Prefer not losing relevant chunks. Tolerates more residual noise
                (higher content recall, higher noise retention).
    BALANCED  — Default enterprise RAG compromise.
    """

    PRECISION = "precision"
    COVERAGE = "coverage"
    BALANCED = "balanced"


class Strictness(str, Enum):
    """Internal aggressiveness presets (mapped from ContentPriority)."""

    LENIENT = "lenient"  # Prefer recall — keep more text
    BALANCED = "balanced"  # Default for enterprise RAG
    AGGRESSIVE = "aggressive"  # Prefer precision — more chrome gone


class PageType(str, Enum):
    DOCS = "docs"
    PRICING = "pricing"
    MARKETING = "marketing"
    HUB = "hub"
    UNKNOWN = "unknown"


_PRIORITY_TO_STRICTNESS = {
    ContentPriority.PRECISION: Strictness.AGGRESSIVE,
    ContentPriority.COVERAGE: Strictness.LENIENT,
    ContentPriority.BALANCED: Strictness.BALANCED,
}


def priority_to_strictness(priority: ContentPriority | str) -> Strictness:
    if isinstance(priority, str):
        priority = ContentPriority(priority)
    return _PRIORITY_TO_STRICTNESS[priority]


@dataclass
class PipelineConfig:
    """All tunables in one place for CLI / UI / experiments."""

    strictness: Strictness = Strictness.BALANCED
    content_priority: ContentPriority = ContentPriority.BALANCED
    page_type: PageType = PageType.UNKNOWN

    enable_schema: bool = True
    enable_tables: bool = True
    enable_dvdf: bool = True
    enable_stce: bool = True  # applied only when a SiteChromeModel is provided
    inject_heading_paths: bool = False

    # Density
    min_chars: int = 40
    max_link_density: float = 0.55
    min_text_density: float = 0.12

    # Chrome / size guards
    max_noise_block_chars: int = 4000  # do not strip wrappers larger than this via class heuristics
    max_rejected_drop_chars: int = 400  # density/DVDF rejected nodes dropped only if shorter

    # DVDF
    dvdf_threshold: float = 0.42

    # STCE (site-template chrome elimination)
    stce_min_pages: int = 5
    stce_frequency: float = 0.80  # appear in ≥80% of site pages
    stce_max_block_chars: int = 1500  # never STCE-drop long shared content blocks
    stce_require_chrome_features: bool = True  # frequency alone is not enough

    def density_config(self) -> DensityConfig:
        return DensityConfig(
            min_chars=self.min_chars,
            max_link_density=self.max_link_density,
            min_text_density=self.min_text_density,
            prefer_main=True,
        )

    @classmethod
    def from_priority(
        cls,
        priority: ContentPriority | str = ContentPriority.BALANCED,
        page_type: PageType | str = PageType.UNKNOWN,
        **overrides: object,
    ) -> PipelineConfig:
        """Build config from the user-facing precision/coverage flag."""
        if isinstance(priority, str):
            priority = ContentPriority(priority)
        cfg = cls.from_strictness(
            priority_to_strictness(priority),
            page_type,
            **overrides,
        )
        cfg.content_priority = priority
        return cfg

    @classmethod
    def from_strictness(
        cls,
        strictness: Strictness | str = Strictness.BALANCED,
        page_type: PageType | str = PageType.UNKNOWN,
        **overrides: object,
    ) -> PipelineConfig:
        if isinstance(strictness, str):
            strictness = Strictness(strictness)
        if isinstance(page_type, str):
            page_type = PageType(page_type)

        # Keep content_priority aligned with strictness when callers use from_strictness
        priority = ContentPriority.BALANCED
        if strictness == Strictness.AGGRESSIVE:
            priority = ContentPriority.PRECISION
        elif strictness == Strictness.LENIENT:
            priority = ContentPriority.COVERAGE

        base = cls(strictness=strictness, content_priority=priority, page_type=page_type)

        if strictness == Strictness.LENIENT:
            base.max_link_density = 0.70
            base.min_text_density = 0.08
            base.min_chars = 25
            base.dvdf_threshold = 0.55
            base.max_rejected_drop_chars = 250
            base.stce_frequency = 0.85
            base.enable_dvdf = True
        elif strictness == Strictness.AGGRESSIVE:
            base.max_link_density = 0.40
            base.min_text_density = 0.18
            base.min_chars = 50
            base.dvdf_threshold = 0.32
            base.max_rejected_drop_chars = 600
            base.stce_frequency = 0.55
            base.stce_max_block_chars = 3500
        else:  # BALANCED
            pass

        # Page-type nudges (on top of strictness)
        if page_type == PageType.MARKETING:
            base.max_link_density = min(base.max_link_density, 0.50)
            base.dvdf_threshold = min(base.dvdf_threshold, 0.38)
        elif page_type == PageType.DOCS:
            base.max_link_density = max(base.max_link_density, 0.60)  # docs side nav is linky but keep body
            base.enable_dvdf = True
        elif page_type == PageType.PRICING:
            base.enable_tables = True
            base.max_rejected_drop_chars = min(base.max_rejected_drop_chars, 300)

        for key, value in overrides.items():
            if not hasattr(base, key):
                raise ValueError(f"Unknown PipelineConfig field: {key}")
            setattr(base, key, value)
        return base


def infer_page_type(url: str | None, html: str = "") -> PageType:
    blob = f"{url or ''} {html[:2000]}".lower()
    if any(k in blob for k in ("/pricing", "pricing", "on-demand", "price-list")):
        return PageType.PRICING
    if any(k in blob for k in ("/docs", "documentation", "userguide", "developer", "/learn/")):
        return PageType.DOCS
    if any(k in blob for k in ("/products", "/product/", "solutions", "platform")):
        return PageType.MARKETING
    if any(k in blob for k in ("/blog", "resources", "customers")):
        return PageType.HUB
    return PageType.UNKNOWN
