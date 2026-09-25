"""ChromeRAG — Ingest-time elimination of site template noise for enterprise web RAG.

Core contract: HTML string in → RAG-ready Markdown out.
Fetching/crawling is intentionally out of scope (use your crawler / poc harness).
"""

from chromerag.batch import learn_then_extract
from chromerag.config import ContentPriority, PageType, PipelineConfig, Strictness
from chromerag.extractor import ChromeRAG
from chromerag.input_quality import InputQualityReport, assess_input_html
from chromerag.models import ExtractResult
from chromerag.site_chrome import (
    SiteChromeModel,
    load_chrome_models,
    mine_site_chrome,
    save_chrome_models,
)

__all__ = [
    "ChromeRAG",
    "ExtractResult",
    "PipelineConfig",
    "ContentPriority",
    "Strictness",
    "PageType",
    "SiteChromeModel",
    "mine_site_chrome",
    "save_chrome_models",
    "load_chrome_models",
    "learn_then_extract",
    "assess_input_html",
    "InputQualityReport",
]
__version__ = "0.1.2"
__paper__ = (
    "ChromeRAG: Ingest-Time Elimination of Site Template Noise for Enterprise Web RAG"
)
