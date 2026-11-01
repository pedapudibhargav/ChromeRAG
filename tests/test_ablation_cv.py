"""Ablation CV harness sanity checks."""

from __future__ import annotations

from poc.ablation_cv import TF_RULE_PREFIXES, all_specs


def test_ablation_config_catalog() -> None:
    names = {s.name for s in all_specs()}
    assert "baseline" in names
    assert "filter_only" in names
    assert "rules_only" in names
    assert "stack_stage2" in names
    assert len(names) == 36


def test_rule_prefix_count() -> None:
    assert len(TF_RULE_PREFIXES) == 12
