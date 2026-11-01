"""Strict training split manifest has no overlap with leaks or test domains."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WCXB = ROOT / "data" / "wcxb"
TRAIN_IDS = ROOT / "poc" / "wcxb_strict_train_ids.json"
LEAKED = ROOT / "poc" / "wcxb_leaked_ids.json"


def test_strict_train_ids_disjoint_from_leaked() -> None:
    train = set(json.loads(TRAIN_IDS.read_text(encoding="utf-8")))
    leaked = set(json.loads(LEAKED.read_text(encoding="utf-8")))
    assert train.isdisjoint(leaked)


def test_strict_train_domains_disjoint_from_test() -> None:
    if not WCXB.is_dir():
        pytest.skip("data/wcxb missing (CI has no WCXB corpus)")

    from poc.strict_split import page_domain
    from poc.wcxb import load_split

    train = set(json.loads(TRAIN_IDS.read_text(encoding="utf-8")))
    test_domains = {page_domain(p) for p in load_split("test") if page_domain(p)}
    for page in load_split("dev"):
        if page.id not in train:
            continue
        dom = page_domain(page)
        assert dom not in test_domains, f"train page {page.id} shares domain {dom} with test"
