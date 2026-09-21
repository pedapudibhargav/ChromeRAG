"""Schema.org JSON-LD + Microdata → YAML front-matter for RAG chunk context."""

from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

INTERESTING_TYPES = {
    "TechArticle",
    "Article",
    "NewsArticle",
    "WebPage",
    "Product",
    "SoftwareApplication",
    "FAQPage",
    "HowTo",
    "BreadcrumbList",
    "Organization",
    "WebSite",
}


def _as_list(obj: Any) -> list[Any]:
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    return [obj]


def _type_name(node: dict[str, Any]) -> str:
    t = node.get("@type") or node.get("type") or ""
    if isinstance(t, list):
        return str(t[0]) if t else ""
    return str(t)


def _pick(node: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in node and node[k] not in (None, "", []):
            return node[k]
    return None


def parse_json_ld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Some sites concatenate multiple objects; try wrapping.
            try:
                data = json.loads(f"[{raw}]")
            except json.JSONDecodeError:
                continue
        for item in _as_list(data):
            if isinstance(item, dict) and "@graph" in item:
                for g in _as_list(item["@graph"]):
                    if isinstance(g, dict):
                        nodes.append(g)
            elif isinstance(item, dict):
                nodes.append(item)
    return nodes


def parse_microdata(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Lightweight microdata harvest (itemscope / itemtype / itemprop)."""
    nodes: list[dict[str, Any]] = []
    for el in soup.find_all(attrs={"itemscope": True}):
        if not isinstance(el, Tag):
            continue
        itemtype = el.get("itemtype") or ""
        type_name = str(itemtype).rstrip("/").split("/")[-1] if itemtype else "Thing"
        props: dict[str, Any] = {"@type": type_name}
        for prop in el.find_all(attrs={"itemprop": True}):
            if not isinstance(prop, Tag):
                continue
            # Prefer nested itemscopes as separate nodes
            if prop.has_attr("itemscope") and prop is not el:
                continue
            name = prop.get("itemprop")
            if not name:
                continue
            val = prop.get("content") or prop.get("href") or prop.get_text(" ", strip=True)
            if not val:
                continue
            key = str(name)
            if key in props:
                existing = props[key]
                if isinstance(existing, list):
                    existing.append(val)
                else:
                    props[key] = [existing, val]
            else:
                props[key] = val
        if len(props) > 1:
            nodes.append(props)
    return nodes


def fuse_front_matter(
    soup: BeautifulSoup,
    url: str | None = None,
) -> dict[str, Any]:
    """Collapse JSON-LD + microdata + basic meta into a flat front-matter dict."""
    json_ld = parse_json_ld(soup)
    micro = parse_microdata(soup)

    fm: dict[str, Any] = {}
    if url:
        fm["url"] = url

    title_tag = soup.find("title")
    if title_tag:
        fm["title"] = title_tag.get_text(" ", strip=True)

    desc = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if desc and desc.get("content"):
        fm["description"] = desc["content"]

    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        fm.setdefault("title", og_title["content"])

    primary: dict[str, Any] | None = None
    for node in json_ld + micro:
        t = _type_name(node)
        if t in INTERESTING_TYPES - {"BreadcrumbList", "Organization", "WebSite"}:
            primary = node
            break
    if primary is None and json_ld:
        primary = json_ld[0]

    if primary:
        t = _type_name(primary)
        if t:
            fm["type"] = t
        headline = _pick(primary, "headline", "name", "title")
        if isinstance(headline, str):
            fm["title"] = headline
        description = _pick(primary, "description")
        if isinstance(description, str):
            fm["description"] = description
        date_mod = _pick(primary, "dateModified", "datePublished", "lastUpdated")
        if isinstance(date_mod, str):
            fm["lastUpdated"] = date_mod
        author = _pick(primary, "author")
        if isinstance(author, dict):
            name = author.get("name")
            if name:
                fm["author"] = name
        elif isinstance(author, str):
            fm["author"] = author

    crumbs = []
    for node in json_ld:
        if _type_name(node) == "BreadcrumbList":
            for el in _as_list(node.get("itemListElement")):
                if isinstance(el, dict):
                    name = el.get("name") or (el.get("item") or {}).get("name") if isinstance(el.get("item"), dict) else el.get("name")
                    if not name and isinstance(el.get("item"), str):
                        name = el.get("item")
                    if isinstance(el.get("item"), dict):
                        name = el["item"].get("name") or name
                    if name:
                        crumbs.append(str(name))
    if crumbs:
        fm["breadcrumb"] = " > ".join(crumbs)

    fm["_sources"] = {
        "json_ld_count": len(json_ld),
        "microdata_count": len(micro),
        "json_ld_types": sorted({_type_name(n) for n in json_ld if _type_name(n)}),
        "microdata_types": sorted({_type_name(n) for n in micro if _type_name(n)}),
    }
    return fm
