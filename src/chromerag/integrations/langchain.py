"""LangChain document loader: stored HTML files → cleaned ``Document`` objects.

    pip install "chromerag[langchain]"

    from chromerag.integrations.langchain import ChromeRAGLoader

    loader = ChromeRAGLoader(["pages/pricing.html"], urls={"pages/pricing.html": "https://..."})
    docs = loader.load()   # page_content = Markdown body, metadata = front-matter + source

The YAML front-matter (title, type, dates, breadcrumb) goes into ``metadata`` rather than the
text, so a text splitter copies it onto every chunk; lists are flattened to ``"a > b"`` strings
because most vector stores accept only scalar metadata. ChromeRAG warnings (for example an
unrendered JavaScript shell) are kept in ``metadata["chromerag_warnings"]``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

from chromerag.config import ContentPriority, PipelineConfig
from chromerag.extractor import ChromeRAG
from chromerag.site_chrome import SiteChromeModel

try:
    from langchain_core.document_loaders import BaseLoader
    from langchain_core.documents import Document
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        'ChromeRAGLoader needs langchain-core: pip install "chromerag[langchain]"'
    ) from exc

_FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n+", re.S)


class ChromeRAGLoader(BaseLoader):
    """Load HTML files with ChromeRAG, one ``Document`` per file."""

    def __init__(
        self,
        file_paths: str | Path | Iterable[str | Path],
        *,
        urls: Mapping[str, str] | None = None,
        priority: ContentPriority | str = ContentPriority.BALANCED,
        site_chrome: SiteChromeModel | None = None,
        skip_thin: bool = False,
        encoding: str = "utf-8",
    ) -> None:
        paths = [file_paths] if isinstance(file_paths, (str, Path)) else list(file_paths)
        self.file_paths = [Path(p) for p in paths]
        self.urls = {str(Path(k)): v for k, v in (urls or {}).items()}
        self.extractor = ChromeRAG(
            config=PipelineConfig.from_priority(priority), site_chrome=site_chrome
        )
        self.skip_thin = skip_thin
        self.encoding = encoding

    def lazy_load(self) -> Iterator[Document]:
        for path in self.file_paths:
            url = self.urls.get(str(path))
            html = path.read_text(encoding=self.encoding, errors="replace")
            result = self.extractor.extract(html, url=url)
            if self.skip_thin and result.input_quality.get("is_thin"):
                continue
            metadata: dict[str, Any] = {
                "source": url or str(path),
                **{k: _flat(v) for k, v in result.front_matter.items() if _flat(v) is not None},
            }
            if result.warnings:
                metadata["chromerag_warnings"] = " | ".join(result.warnings)
            yield Document(page_content=_FRONT_MATTER.sub("", result.markdown), metadata=metadata)


def _flat(value: Any) -> str | int | float | bool | None:
    """Vector stores accept scalar metadata only; lists (e.g. breadcrumbs) become 'a > b'."""
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)) and all(isinstance(v, (str, int, float)) for v in value):
        return " > ".join(str(v) for v in value)
    return None
