"""ChromeRAG must never touch the network: it has to work in air-gapped environments.

Regression: token estimation used tiktoken, which downloads its vocabulary on first use;
offline it hung without a timeout, and behind a proxy it silently fell back to a
different estimate, so results depended on the machine.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from chromerag import ChromeRAG, ContentPriority, PipelineConfig
from chromerag.cli import main
from chromerag.extractor import estimate_tokens

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "site"


@pytest.fixture
def network_attempts(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Block the network and record every attempt, even ones the caller swallows."""
    attempts: list[str] = []

    def refuse(*args: object, **kwargs: object) -> None:
        attempts.append(repr(args[-1] if args else kwargs))
        raise OSError("network disabled in test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    return attempts


def test_extract_learn_and_batch_work_offline(network_attempts: list[str], tmp_path: Path) -> None:
    html = (EXAMPLES / "pricing.html").read_text(encoding="utf-8")
    for priority in ContentPriority:
        result = ChromeRAG(config=PipelineConfig.from_priority(priority)).extract(
            html, url="https://docs.example.com/docs/pricing"
        )
        assert result.tokens_estimate > 0
    model = tmp_path / "site.json"
    assert main(["learn", str(EXAMPLES), "-o", str(model), "--min-pages", "3"]) == 0
    assert main(["batch", str(EXAMPLES), "-o", str(tmp_path / "out"), "--chrome-model", str(model)]) == 0
    assert main(["extract", str(EXAMPLES / "pricing.html"), "-o", str(tmp_path / "p.md")]) == 0
    assert network_attempts == []


def test_token_estimate_is_deterministic() -> None:
    assert estimate_tokens("") == 1
    assert estimate_tokens("a" * 400) == 100
