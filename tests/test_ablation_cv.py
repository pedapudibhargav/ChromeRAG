"""Ablation CV harness sanity checks."""

from __future__ import annotations

from dataclasses import fields

from chromerag.config import PipelineConfig
from chromerag.rules_engine import DEFAULT_INDEX, load_rules
from poc.ablation_cv import (
    CHROME_ABLATIONS,
    TF_RULE_PREFIXES,
    YAML_SKIP_ABLATIONS,
    all_specs,
)


def test_ablation_config_catalog() -> None:
    specs = all_specs()
    names = {s.name for s in specs}
    assert "baseline" in names
    assert "filter_only" in names
    assert "rules_only" in names
    assert "stack_stage2" in names
    assert "no_table_rescue" in names
    assert "no_yaml_docs_generators" not in names
    assert len(names) == len(specs) == 31


def test_rule_prefix_count() -> None:
    assert len(TF_RULE_PREFIXES) == 7


def test_yaml_skip_stems_disable_rules() -> None:
    all_rules = DEFAULT_INDEX.rules
    for _name, stems in YAML_SKIP_ABLATIONS:
        kept = load_rules(skip_stems=stems)
        assert len(kept) < len(all_rules)
        removed = {r.id for r in all_rules} - {r.id for r in kept}
        assert removed, f"skip_stems {stems} removed nothing"


def test_tf_prefixes_match_rules() -> None:
    ids = {r.id for r in DEFAULT_INDEX.rules}
    for prefix in TF_RULE_PREFIXES:
        matched = [i for i in ids if i == prefix or i.startswith(prefix + ".")]
        assert matched, f"no rule for prefix {prefix!r}"


def test_ablation_prefix_specs_disable_rules() -> None:
    ids = {r.id for r in DEFAULT_INDEX.rules}
    for spec in all_specs():
        if not spec.rule_disabled_prefixes:
            continue
        for prefix in spec.rule_disabled_prefixes:
            assert any(i == prefix or i.startswith(prefix + ".") for i in ids), prefix


def test_chrome_ablation_flags_exist() -> None:
    cfg_fields = {f.name for f in fields(PipelineConfig)}
    for _name, flag in CHROME_ABLATIONS:
        assert flag in cfg_fields


def test_pipeline_ablation_flags_exist() -> None:
    cfg_fields = {f.name for f in fields(PipelineConfig)}
    for spec in all_specs():
        for key in spec.cfg:
            assert key in cfg_fields, (spec.name, key)
