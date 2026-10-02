"""LlamaIndex reader (skipped when llama-index-core is not installed)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("llama_index.core")

from chromerag.integrations.llamaindex import ChromeRAGReader  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def test_reader_returns_markdown_and_source() -> None:
    path = FIXTURES / "docs_page.html"
    docs = ChromeRAGReader().load_data([path], urls={str(path): "https://docs.example.com/x"})
    assert len(docs) == 1
    assert docs[0].metadata["source"] == "https://docs.example.com/x"
    assert docs[0].text.strip()
