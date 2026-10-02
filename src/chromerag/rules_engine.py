"""Removal-rule index: reviewed selectors kept as data (``rules/*.yaml``).

Every rule needs ``evidence`` and a ``fixture`` (see ``rules/README.md``). All rules are
applied in one pass over the document: elements are visited in document order, candidate
rules are found through dictionaries (class name, id, tag), and only those candidates are
checked in full.

Match keys (all keys inside one ``match`` item must hold; any item may match):
  tag          element name
  id           regular expression searched in the id (case-insensitive)
  class_token  one whole class name, compared case-insensitively (``ot-sdk-container`` is one
               token; it is *not* split at hyphens)
  class_regex  regular expression searched in the space-joined class attribute
  role         value of the role attribute
  attr         ``{name, pattern}``: regular expression searched in that attribute
  text_exact   whole visible text of the element equals this phrase (punctuation and case ignored)
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from bs4 import BeautifulSoup, Tag

from chromerag.domutil import all_tags
from chromerag.treestats import TreeStats

_RULES_PKG = Path(__file__).resolve().parent / "rules"
_ID_PREFIX = re.compile(r"^\^([A-Za-z0-9_\-]+)$")
_ID_EXACT = re.compile(r"^\^([A-Za-z0-9_\-]+)\$$")
_PUNCT = re.compile(r"[^\w\s]")


@dataclass(frozen=True)
class Rule:
    id: str
    action: str
    scope: str
    match: list[dict[str, Any]]
    max_chars: int = 6000
    applies_when: dict[str, list[str]] = field(default_factory=dict)
    risk: str = "safe"
    evidence: str = ""
    fixture: str = ""

    @property
    def group(self) -> str:
        return self.id.split(".", 1)[0]


@dataclass
class RuleHit:
    rule_id: str
    chars: int


def load_rules(rules_dir: Path = _RULES_PKG) -> list[Rule]:
    rules: list[Rule] = []
    for path in sorted(rules_dir.glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        for item in payload:
            rules.append(
                Rule(
                    id=str(item["id"]),
                    action=str(item.get("action", "drop")),
                    scope=str(item.get("scope", "anywhere")),
                    match=list(item.get("match") or []),
                    max_chars=int(item.get("max_chars", 6000)),
                    applies_when={k: list(v) for k, v in (item.get("applies_when") or {}).items()},
                    risk=str(item.get("risk", "safe")),
                    evidence=str(item.get("evidence", "")),
                    fixture=str(item.get("fixture", "")),
                )
            )
    return rules


@dataclass
class _Spec:
    """One compiled ``match`` item of one rule."""

    rule: int
    tag: str | None = None
    id_re: re.Pattern[str] | None = None
    class_token: str | None = None
    class_re: re.Pattern[str] | None = None
    role: str | None = None
    attr: tuple[str, re.Pattern[str]] | None = None
    text_exact: str | None = None

    def holds(self, tag: Tag, ident: str, classes: list[str], text: str | None) -> bool:
        if self.tag is not None and tag.name != self.tag:
            return False
        if self.id_re is not None and not self.id_re.search(ident):
            return False
        if self.class_token is not None and self.class_token not in {c.lower() for c in classes}:
            return False
        if self.class_re is not None and not self.class_re.search(" ".join(classes)):
            return False
        if self.role is not None and (tag.get("role") or "").lower() != self.role:
            return False
        if self.attr is not None:
            name, pattern = self.attr
            value = tag.get(name) or ""
            if isinstance(value, list):
                value = " ".join(value)
            if not pattern.search(str(value)):
                return False
        if self.text_exact is not None:
            if text is None:
                return False
            norm = _PUNCT.sub("", text.lower()).strip()
            if norm != self.text_exact:
                return False
        return True


def _compile_spec(rule_no: int, item: dict[str, Any]) -> _Spec:
    spec = _Spec(rule=rule_no)
    for key, val in item.items():
        if key == "tag":
            spec.tag = str(val).lower()
        elif key == "id":
            spec.id_re = re.compile(str(val), re.I)
        elif key == "class_token":
            spec.class_token = str(val).lower()
        elif key == "class_regex":
            spec.class_re = re.compile(str(val), re.I)
        elif key == "role":
            spec.role = str(val).lower()
        elif key == "attr":
            if isinstance(val, dict):
                spec.attr = (str(val["name"]), re.compile(str(val["pattern"]), re.I))
            else:
                name, _, pattern = str(val).partition("=")
                spec.attr = (name, re.compile(pattern, re.I))
        elif key == "text_exact":
            spec.text_exact = _PUNCT.sub("", str(val).lower()).strip()
        else:
            raise ValueError(f"unknown match key {key!r} in rule #{rule_no}")
    return spec


class RuleIndex:
    """Compiled rules plus dictionaries that find candidate rules for an element."""

    def __init__(self, rules: list[Rule], removed_cap: int = 50) -> None:
        self.rules = rules
        self.removed_cap = removed_cap
        self._by_class: dict[str, list[_Spec]] = defaultdict(list)
        self._by_id_exact: dict[str, list[_Spec]] = defaultdict(list)
        self._by_id_prefix: dict[int, dict[str, list[_Spec]]] = defaultdict(lambda: defaultdict(list))
        self._id_generic: list[_Spec] = []
        self._class_generic: list[_Spec] = []
        self._by_tag: dict[str, list[_Spec]] = defaultdict(list)
        self._generic: list[_Spec] = []
        for no, rule in enumerate(rules):
            for item in rule.match:
                spec = _compile_spec(no, item)
                self._register(spec, item)

    @classmethod
    def load(cls) -> RuleIndex:
        return cls(load_rules())

    def _register(self, spec: _Spec, item: dict[str, Any]) -> None:
        if spec.class_token is not None:
            self._by_class[spec.class_token].append(spec)
        elif spec.id_re is not None:
            pattern = str(item["id"])
            if m := _ID_EXACT.match(pattern):
                self._by_id_exact[m.group(1).lower()].append(spec)
            elif m := _ID_PREFIX.match(pattern):
                prefix = m.group(1).lower()
                self._by_id_prefix[len(prefix)][prefix].append(spec)
            else:
                self._id_generic.append(spec)
        elif spec.class_re is not None:
            self._class_generic.append(spec)
        elif spec.tag is not None:
            self._by_tag[spec.tag].append(spec)
        else:
            self._generic.append(spec)

    def _candidates(self, tag: Tag, ident: str, classes: list[str]) -> list[_Spec]:
        found: list[_Spec] = []
        for cls in classes:
            bucket = self._by_class.get(cls.lower())
            if bucket:
                found.extend(bucket)
        if ident:
            low = ident.lower()
            bucket = self._by_id_exact.get(low)
            if bucket:
                found.extend(bucket)
            for length, table in self._by_id_prefix.items():
                bucket = table.get(low[:length])
                if bucket:
                    found.extend(bucket)
            found.extend(self._id_generic)
        if classes:
            found.extend(self._class_generic)
        bucket = self._by_tag.get(tag.name or "")
        if bucket:
            found.extend(bucket)
        found.extend(self._generic)
        return found

    def apply(
        self,
        soup: BeautifulSoup,
        *,
        content_root: Tag | None,
        page_type: str = "unknown",
        platform: str = "unknown",
        disabled_groups: set[str] | None = None,
        stats: TreeStats | None = None,
    ) -> tuple[list[RuleHit], dict[str, int]]:
        """Remove matching elements. Returns (hits, characters removed per rule id).

        ``stats`` must describe the tree as it is now. Elements are visited in document order
        and only the visited element is removed, so it stays exact for the rest of the walk.
        """
        hits: list[RuleHit] = []
        totals: dict[str, int] = {}
        disabled = disabled_groups or set()
        active = [
            not (
                rule.group in disabled
                or (rule.applies_when.get("page_type") and page_type not in rule.applies_when["page_type"])
                or (rule.applies_when.get("platform") and platform not in rule.applies_when["platform"])
            )
            for rule in self.rules
        ]
        if not any(active):
            return hits, totals
        stats = stats or TreeStats(soup)
        root_ids: set[int] | None = None
        if content_root is not None:
            root_ids = {id(t) for t in all_tags(content_root)}
            root_ids.add(id(content_root))

        for tag in all_tags(soup):
            if tag.attrs is None:  # inside a subtree removed earlier in this walk
                continue
            ident = str(tag.get("id") or "")
            raw_classes = tag.get("class") or []
            classes = [raw_classes] if isinstance(raw_classes, str) else list(raw_classes)
            candidates = self._candidates(tag, ident, classes)
            if not candidates:
                continue
            text: str | None = None
            hit_rule: Rule | None = None
            for spec in sorted(candidates, key=lambda c: c.rule):
                rule = self.rules[spec.rule]
                if not active[spec.rule]:
                    continue
                if rule.scope == "inside_root" and root_ids is not None and id(tag) not in root_ids:
                    continue
                if spec.text_exact is not None and text is None:
                    text = tag.get_text(" ", strip=True)
                if not spec.holds(tag, ident, classes, text):
                    continue
                if stats.text_len(tag) > rule.max_chars:
                    continue
                hit_rule = rule
                break
            if hit_rule is None or hit_rule.action != "drop":
                continue
            chars = stats.text_len(tag)
            tag.decompose()
            totals[hit_rule.id] = totals.get(hit_rule.id, 0) + chars
            if len(hits) < self.removed_cap:
                hits.append(RuleHit(rule_id=hit_rule.id, chars=chars))
        return hits, totals


DEFAULT_INDEX = RuleIndex.load()
