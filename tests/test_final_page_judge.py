"""Unit tests for poc.final_page_judge and the fixed-order verdict; no network."""

from __future__ import annotations

import json
from pathlib import Path

from poc import final_page_judge as j
from poc.eval_rubric import RULES_BY_LABEL, sensitivity_verdict


def test_sensitivity_rules():
    assert sensitivity_verdict(5, 5, 4, 3) == "tie"
    assert sensitivity_verdict(5, 2, 4, 3) == "B"
    assert sensitivity_verdict(5, 2, 3, 5) == "A"
    assert sensitivity_verdict(5, 1, 3, 2) == "B"
    assert sensitivity_verdict(5, 1, 2, 2) == "A"
    assert sensitivity_verdict(5, 1, 3, 1) == "A"
    assert sensitivity_verdict(3, 2, 5, 1) == "A"


def test_clip_same_budget():
    assert j.clip("x" * j.BUDGET_CHARS) == "x" * j.BUDGET_CHARS
    clipped = j.clip("x" * (j.BUDGET_CHARS + 1))
    assert "[...]" in clipped
    assert len(clipped) <= j.BUDGET_CHARS + 10


def test_score_row_maps_a_b_to_tools():
    job = {"id": "p", "baseline": "t", "swapped": False, "clipped": False, "ours_is_a": False}
    verdict = {"better": "B", "content_A": 3, "chrome_A": 5, "content_B": 5, "chrome_B": 5}
    row = j.score_row(job, verdict)
    assert row["winner"] == "chromerag"
    assert row["winner_sensitivity"] == "chromerag"


def test_summary_separates_unclipped_and_swapped():
    base = {"id": "a", "baseline": "t", "winner_sensitivity": "tie"}
    rows = [
        {**base, "swapped": False, "clipped": True, "winner": "baseline"},
        {**base, "id": "b", "swapped": False, "clipped": False, "winner": "chromerag"},
        {**base, "id": "b", "swapped": True, "clipped": False, "winner": "chromerag"},
    ]
    out = j.summarize(rows, ["t"])
    assert out["t"]["judge_verdict"]["pairs"] == 2
    assert out["t"]["judge_verdict_unclipped_pairs"] == {"pairs": 1, "chromerag": 1, "baseline": 0, "tie": 0}
    assert out["position_check"] == {"pairs": 1, "same_verdict": 1}


def test_rule_sets_cover_all_ids():
    assert RULES_BY_LABEL["missing"] == {"R-MISS"}
    assert "R-WRONG" not in RULES_BY_LABEL["accurate"]


def test_fixture_cases_fit_label_rule_pairs():
    path = Path(__file__).parent / "fixtures" / "crag_rubric_cases.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        case = json.loads(line)
        assert case["rule"] in RULES_BY_LABEL[case["expected_label"]], case["id"]
