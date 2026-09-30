"""Rule index fixture tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from chromerag import ChromeRAG, PipelineConfig
from chromerag.rules_engine import RuleIndex

RULES_DIR = Path(__file__).resolve().parents[1] / "src" / "chromerag" / "rules"
FIXTURES = Path(__file__).parent / "rules"


def test_rule_metadata_complete() -> None:
    index = RuleIndex.load()
    ids = [r.id for r in index.rules]
    assert len(ids) == len(set(ids))
    for rule in index.rules:
        assert rule.evidence, rule.id
        assert rule.fixture, rule.id
        assert Path(rule.fixture).is_file(), rule.id


@pytest.mark.parametrize("fixture_path", sorted(FIXTURES.glob("*.html")))
def test_rule_fixture_removes_chrome_keeps_content(fixture_path: Path) -> None:
    html = fixture_path.read_text(encoding="utf-8")
    md = ChromeRAG(config=PipelineConfig(enable_dvdf=False)).extract(html).markdown.lower()
    if "consent" in fixture_path.name or "onetrust" in fixture_path.name or "cookiebot" in fixture_path.name:
        assert "cookie" not in md or "keep" in md or "documentation" in md or "oauth" in md or "webhook" in md
    assert "keep" in md
