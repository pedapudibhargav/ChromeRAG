"""LlamaIndex reader: stored HTML files → cleaned ``Document`` objects.

    pip install "chromerag[llamaindex]"

    from chromerag.integrations.llamaindex import ChromeRAGReader

    docs = ChromeRAGReader().load_data(["pages/pricing.html"], urls={"pages/pricing.html": "https://..."})

``text`` is the Markdown body; the YAML front-matter (title, type, dates, breadcrumb) goes into
``metadata`` as scalar values, and ChromeRAG warnings are kept in ``metadata["chromerag_warnings"]``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from chromerag.config import ContentPriority, PipelineConfig
from chromerag.extractor import ChromeRAG
from chromerag.integrations._metadata import flat
from chromerag.site_chrome import SiteChromeModel

try:
    from llama_index.core.readers.base import BaseReader
    from llama_index.core.schema import Document
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        'ChromeRAGReader needs llama-index-core: pip install "chromerag[llamaindex]"'
    ) from exc

_FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n+", re.S)


class ChromeRAGReader(BaseReader):
    """Read HTML files with ChromeRAG, one ``Document`` per file."""

    def __init__(
        self,
        *,
        priority: ContentPriority | str = ContentPriority.BALANCED,
        site_chrome: SiteChromeModel | None = None,
        skip_thin: bool = False,
        encoding: str = "utf-8",
    ) -> None:
        super().__init__()
        self.extractor = ChromeRAG(config=PipelineConfig.from_priority(priority), site_chrome=site_chrome)
        self.skip_thin = skip_thin
        self.encoding = encoding

    def load_data(
        self,
        file_paths: str | Path | Iterable[str | Path],
        *,
        urls: Mapping[str, str] | None = None,
        **_: Any,
    ) -> list[Document]:
        paths = [file_paths] if isinstance(file_paths, (str, Path)) else list(file_paths)
        lookup = {str(Path(k)): v for k, v in (urls or {}).items()}
        docs: list[Document] = []
        for path in map(Path, paths):
            url = lookup.get(str(path))
            html = path.read_text(encoding=self.encoding, errors="replace")
            result = self.extractor.extract(html, url=url)
            if self.skip_thin and result.input_quality.get("is_thin"):
                continue
            metadata: dict[str, Any] = {"source": url or str(path)}
            for key, value in result.front_matter.items():
                flat_value = flat(value)
                if flat_value is not None:
                    metadata[key] = flat_value
            if result.warnings:
                metadata["chromerag_warnings"] = " | ".join(result.warnings)
            docs.append(Document(text=_FRONT_MATTER.sub("", result.markdown), metadata=metadata))
        return docs
