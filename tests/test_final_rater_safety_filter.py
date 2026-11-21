"""Unit tests for poc.final_rater_safety_filter; no network."""

from __future__ import annotations

from poc import final_rater_safety_filter as f


def test_domain_rules():
    assert f.domain_reason("www.themoviebox.xyz") == "risky_domain_ending"
    assert f.domain_reason("five88.shoes") == "risky_domain_name"
    assert f.domain_reason("299betvip.com") == "risky_domain_name"
    assert f.domain_reason("opera.com") is None
    assert f.domain_reason("better-search.ch") is None


def test_text_needs_several_hits():
    assert f.text_category("online casino jackpot and poker tonight") == ("gambling", 3)
    assert f.text_category("a news story about a casino") is None
