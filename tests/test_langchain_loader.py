"""ChromeRAGLoader against a minimal stand-in for langchain-core's loader interface."""

from __future__ import annotations

import importlib
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "site"


@pytest.fixture
def loader_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    """Install stand-ins for langchain_core.documents / document_loaders, then import the loader."""

    @dataclass
    class Document:
        page_content: str
        metadata: dict[str, Any] = field(default_factory=dict)

    class BaseLoader:
        def load(self) -> list[Document]:
            return list(self.lazy_load())

    core = types.ModuleType("langchain_core")
    documents = types.ModuleType("langchain_core.documents")
    documents.Document = Document
    loaders = types.ModuleType("langchain_core.document_loaders")
    loaders.BaseLoader = BaseLoader
    monkeypatch.setitem(sys.modules, "langchain_core", core)
    monkeypatch.setitem(sys.modules, "langchain_core.documents", documents)
    monkeypatch.setitem(sys.modules, "langchain_core.document_loaders", loaders)
    monkeypatch.delitem(sys.modules, "chromerag.integrations.langchain", raising=False)
    return importlib.import_module("chromerag.integrations.langchain")


def test_loader_moves_front_matter_into_metadata(loader_module: types.ModuleType) -> None:
    path = EXAMPLES / "pricing.html"
    url = "https://docs.example.com/docs/pricing"
    docs = loader_module.ChromeRAGLoader([path], urls={str(path): url}).load()
    assert len(docs) == 1
    doc = docs[0]
    assert doc.metadata["source"] == url
    assert doc.metadata["title"] == "Plans and pricing"
    assert not doc.page_content.startswith("---")
    assert "Monthly price (USD): 49" in doc.page_content


def test_loader_can_skip_javascript_shells(loader_module: types.ModuleType, tmp_path: Path) -> None:
    shell = tmp_path / "spa.html"
    shell.write_text('<html><body><div id="root"></div><script src="a.js"></script></body></html>')
    kept = loader_module.ChromeRAGLoader([shell]).load()
    assert kept and kept[0].metadata["chromerag_warnings"]
    assert loader_module.ChromeRAGLoader([shell], skip_thin=True).load() == []
