"""Every rule must drop its chrome, keep real content, and carry evidence and a fixture."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from chromerag import ChromeRAG, PipelineConfig
from chromerag.rules_engine import DEFAULT_INDEX, Rule, RuleIndex

ROOT = Path(__file__).resolve().parents[1]
RULES = {r.id: r for r in DEFAULT_INDEX.rules}


def _extract(html: str, *, rules: bool):
    cfg = PipelineConfig(enable_dvdf=False, enable_rules=rules)
    return ChromeRAG(config=cfg).extract(html)


def test_rule_ids_unique_and_documented() -> None:
    ids = [r.id for r in DEFAULT_INDEX.rules]
    assert ids and len(ids) == len(set(ids))
    for rule in DEFAULT_INDEX.rules:
        assert len(rule.evidence) >= 20, rule.id
        assert rule.fixture, rule.id
        assert (ROOT / rule.fixture).is_file(), rule.id


@pytest.mark.parametrize("rule", DEFAULT_INDEX.rules, ids=lambda r: r.id)
def test_rule_drops_chrome_and_keeps_content(rule: Rule) -> None:
    html = (ROOT / rule.fixture).read_text(encoding="utf-8")
    chrome = re.findall(r'data-chrome="([^"]+)"', html)
    keep = re.findall(r'data-keep="([^"]+)"', html)
    assert chrome and keep, "fixture needs data-chrome and data-keep markers"

    on = _extract(html, rules=True)

    assert rule.id in {h["rule"] for h in on.diagnostics["removed"]}, "rule did not fire"
    low = on.markdown.lower()
    for phrase in chrome:
        assert phrase.lower() not in low, f"chrome kept: {phrase}"
    for phrase in keep:
        assert phrase.lower() in low, f"content lost: {phrase}"


def test_text_outside_rule_scope_is_kept() -> None:
    html = (
        "<html><body><main><p>An essay about how to share a social calendar with a team "
        "and keep related tasks together in one place.</p></main></body></html>"
    )
    md = _extract(html, rules=True).markdown.lower()
    assert "social calendar" in md and "related tasks" in md


def test_class_token_is_a_whole_class_name() -> None:
    index = RuleIndex.load()
    html = (
        '<html><body><main><div class="sharepoint-guide"><p>Keep sharepoint guide text '
        "that explains permissions in detail for administrators.</p></div></main></body></html>"
    )
    md = ChromeRAG(config=PipelineConfig(enable_dvdf=False), rule_index=index).extract(html).markdown
    assert "sharepoint guide" in md.lower()
