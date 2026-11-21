"""Offline checks for CRAG answer rubric fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from poc import crag_answer_eval as m
from poc.eval_rubric import ANSWER_RULE_IDS

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "crag_rubric_cases.jsonl"
REQUIRED_KEYS = frozenset({"id", "question", "gold", "answer", "expected_label", "rule"})


def load_rubric_cases(path: Path = FIXTURES) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            missing = REQUIRED_KEYS - row.keys()
            assert not missing, f"line {line_no}: missing keys {missing}"
            rows.append(row)
    return rows


def test_rubric_fixtures_well_formed():
    rows = load_rubric_cases()
    assert len(rows) >= 30
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids))
    for row in rows:
        assert row["expected_label"] in m.VALID_LABELS
        assert row["rule"] in ANSWER_RULE_IDS


def test_judge_rubric_v2_loads():
    prompt = m.judge_system_for_rubric("v2")
    assert "R-PART" in prompt
    assert "rule_id" in prompt
