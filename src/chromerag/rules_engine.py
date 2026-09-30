"""Load and apply YAML removal rules."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from bs4 import BeautifulSoup, Tag

_RULES_PKG = Path(__file__).resolve().parent / "rules"
_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Rule:
    id: str
    action: str
    scope: str
    match: list[dict[str, str]]
    max_chars: int = 6000
    applies_when: dict[str, list[str]] = field(default_factory=dict)
    risk: str = "safe"
    evidence: str = ""
    fixture: str = ""


@dataclass
class RuleHit:
    rule_id: str
    chars: int


def _load_yaml_files() -> list[Rule]:
    rules: list[Rule] = []
    for path in sorted(_RULES_PKG.glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        for item in payload:
            rules.append(
                Rule(
                    id=str(item["id"]),
                    action=str(item.get("action", "drop")),
                    scope=str(item.get("scope", "anywhere")),
                    match=list(item.get("match") or []),
                    max_chars=int(item.get("max_chars", 6000)),
                    applies_when=dict(item.get("applies_when") or {}),
                    risk=str(item.get("risk", "safe")),
                    evidence=str(item.get("evidence", "")),
                    fixture=str(item.get("fixture", "")),
                )
            )
    return rules


def _compile_match(spec: dict[str, Any]) -> dict[str, Any]:
    compiled: dict[str, Any] = {}
    for key, val in spec.items():
        if key == "id":
            compiled[key] = re.compile(str(val), re.I)
        elif key == "class_regex":
            compiled[key] = re.compile(str(val), re.I)
        elif key == "class_token":
            compiled[key] = str(val).lower()
        elif key == "tag":
            compiled[key] = str(val)
        elif key == "role":
            compiled[key] = str(val)
        elif key == "text_exact":
            compiled[key] = re.sub(r"[^\w\s]", "", str(val).lower()).strip()
        elif key == "attr":
            if isinstance(val, dict):
                compiled[key] = (str(val["name"]), re.compile(str(val["pattern"]), re.I))
            else:
                name, _, pattern = str(val).partition("=")
                compiled[key] = (name, re.compile(pattern, re.I))
    return compiled


@dataclass
class RuleIndex:
    rules: list[Rule]
    compiled: list[tuple[Rule, list[dict[str, Any]]]]
    removed_cap: int = 50

    @classmethod
    def load(cls) -> RuleIndex:
        rules = _load_yaml_files()
        compiled = [(r, [_compile_match(m) for m in r.match]) for r in rules]
        return cls(rules=rules, compiled=compiled)

    def _class_tokens(self, tag: Tag) -> set[str]:
        tokens: set[str] = set()
        for item in tag.get("class") or []:
            for part in re.split(r"[\s_\-:/]+", str(item).lower()):
                if part:
                    tokens.add(part)
        return tokens

    def _matches(self, tag: Tag, specs: list[dict[str, Any]]) -> bool:
        for spec in specs:
            ok = True
            if "tag" in spec and (tag.name or "") != spec["tag"]:
                ok = False
            ident = tag.get("id") or ""
            if ok and "id" in spec and not spec["id"].search(str(ident)):
                ok = False
            if ok and "class_token" in spec and spec["class_token"] not in self._class_tokens(tag):
                ok = False
            if ok and "class_regex" in spec:
                blob = " ".join(tag.get("class") or [])
                if not spec["class_regex"].search(blob):
                    ok = False
            if ok and "role" in spec and (tag.get("role") or "").lower() != spec["role"].lower():
                ok = False
            if ok and "attr" in spec:
                name, pattern = spec["attr"]
                if not pattern.search(str(tag.get(name) or "")):
                    ok = False
            if ok and "text_exact" in spec:
                text = re.sub(r"[^\w\s]", "", tag.get_text(" ", strip=True).lower()).strip()
                if text != spec["text_exact"] and not text.startswith(spec["text_exact"]):
                    ok = False
            if ok:
                return True
        return False

    def apply(
        self,
        soup: BeautifulSoup,
        *,
        content_root: Tag | None,
        page_type: str = "unknown",
        platform: str = "unknown",
        disabled_groups: set[str] | None = None,
    ) -> tuple[list[RuleHit], dict[str, int]]:
        hits: list[RuleHit] = []
        totals: dict[str, int] = {}
        disabled = disabled_groups or set()
        root = content_root

        for rule, specs in self.compiled:
            group = rule.id.split(".", 1)[0]
            if group in disabled:
                continue
            when = rule.applies_when
            if when.get("page_type") and page_type not in when["page_type"]:
                continue
            if when.get("platform") and platform not in when["platform"]:
                continue

            for tag in list(soup.find_all(True)):
                if not isinstance(tag, Tag) or getattr(tag, "attrs", None) is None:
                    continue
                if rule.scope == "inside_root" and root is not None:
                    if tag is not root and root not in tag.parents:
                        continue
                if not self._matches(tag, specs):
                    continue
                text_len = len(tag.get_text(" ", strip=True))
                if text_len > rule.max_chars:
                    continue
                if rule.action == "drop":
                    tag.decompose()
                    hits.append(RuleHit(rule_id=rule.id, chars=text_len))
                    totals[rule.id] = totals.get(rule.id, 0) + text_len
                    if len(hits) >= self.removed_cap:
                        return hits, totals
        return hits, totals


DEFAULT_INDEX = RuleIndex.load()
