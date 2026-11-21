"""Blind A/B assignment checks for poc.run_llm_judge_final."""

from __future__ import annotations

import random
from pathlib import Path

from poc import run_llm_judge_final as j
from poc.run_llm_judge import BASELINES, REFERENCE


def test_ab_assignment_shared_across_baselines(tmp_path: Path):
    outputs = tmp_path / "out"
    outputs.mkdir()
    for name in (REFERENCE, *BASELINES):
        (outputs / f"{name}.md").write_text(f"extraction {name}", encoding="utf-8")
    item = {
        "corpus": "landing",
        "id": "page-42",
        "html": "<html><body>Hello world content here</body></html>",
        "meta": {"category": "x"},
        "outputs": outputs,
    }
    jobs = j._jobs([item], random.Random(0))
    primary = [x for x in jobs if not x["swapped"]]
    assert len(primary) == len(BASELINES)
    assert len({x["ours_is_a"] for x in primary}) == 1
    assert len({x["ab_seed"] for x in primary}) == 1
    assert all(x["ab_seed"] == j._page_ab_seed("page-42") for x in primary)
