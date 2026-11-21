"""Load evaluation rubric prompts from evaluations/2026-11-final/RUBRIC.md."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUBRIC_MD = ROOT / "evaluations" / "2026-11-final" / "RUBRIC.md"

ANSWER_RULE_IDS = frozenset(
    {
        "R-MISS",
        "R-REQ",
        "R-PART",
        "R-WRONG",
        "R-NUM",
        "R-NAME",
        "R-DATE",
        "R-ALT",
        "R-MULTI",
        "R-HEDGE",
        "R-CONTRA",
        "R-TIME",
    }
)

# Rule ids each label may cite, from the ordered steps in RUBRIC.md.
RULES_BY_LABEL = {
    "missing": frozenset({"R-MISS"}),
    "incorrect": frozenset(
        {"R-CONTRA", "R-HEDGE", "R-TIME", "R-NUM", "R-DATE", "R-WRONG", "R-PART", "R-MULTI"}
    ),
    "accurate": frozenset({"R-HEDGE", "R-ALT", "R-NUM", "R-DATE", "R-NAME", "R-REQ"}),
}

_BLOCK = re.compile(
    r"<!-- (?P<tag>[\w_]+) -->\s*```prompt\s*\n(?P<body>.*?)\n```\s*<!-- END_(?P=tag) -->",
    re.S,
)


def _extract(tag: str) -> str:
    text = RUBRIC_MD.read_text(encoding="utf-8")
    for m in _BLOCK.finditer(text):
        if m.group("tag") == tag:
            return m.group("body").strip()
    raise KeyError(f"prompt block {tag!r} not found in {RUBRIC_MD.name}")


def answer_judge_prompt_v2() -> str:
    return _extract("ANSWER_JUDGE_PROMPT_V2")


def page_judge_prompt() -> str:
    return _extract("PAGE_JUDGE_PROMPT")


def sensitivity_verdict(
    content_a: int, chrome_a: int, content_b: int, chrome_b: int
) -> str:
    """Fixed-order verdict from RUBRIC.md, computed from stored scores: "A", "B" or "tie"."""
    cont_a, cont_b = min(content_a, 4), min(content_b, 4)
    chr_a, chr_b = min(chrome_a, 3), min(chrome_b, 3)
    if cont_a == cont_b:
        if chr_a == chr_b:
            return "tie"
        return "A" if chr_a > chr_b else "B"
    high, low = ("A", "B") if cont_a > cont_b else ("B", "A")
    chr_high, chr_low = (chrome_a, chrome_b) if high == "A" else (chrome_b, chrome_a)
    cont_low = content_b if high == "A" else content_a
    if chr_high == 1 and chr_low >= 2 and cont_low >= 3:
        return low
    return high
