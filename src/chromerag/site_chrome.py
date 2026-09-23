"""Site-Template Chrome Elimination (STCE).

Mine blocks that repeat across pages of the same site/template and strip them
when they also look like chrome (nav, CTA, chat, subscribe).

Placement in pipeline:
  schema harvest → hard clean → **STCE** → structural chrome → density → DVDF

Caveats enforced here:
  - frequency alone is not enough (require chrome-like features)
  - never drop oversized blocks (long shared marketing blurbs stay unless clearly chrome)
  - group by host (+ optional path prefix) so /docs vs /products don't pollute each other
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from chromerag.density import link_density, text_density


_WS = re.compile(r"\s+")


@dataclass
class ChromeSignature:
    signature: str
    sample_text: str
    page_hits: int
    frequency: float
    avg_link_density: float
    avg_chars: float


@dataclass
class SiteChromeModel:
    """Learned chrome signatures for one site group."""

    group_key: str
    n_pages: int
    signatures: set[str] = field(default_factory=set)
    details: list[ChromeSignature] = field(default_factory=list)

    def should_strip(self, signature: str) -> bool:
        return signature in self.signatures


def site_group_key(url: str | None, path_prefix_depth: int = 1) -> str:
    if not url:
        return "unknown"
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower().removeprefix("www.")
    parts = [p for p in parsed.path.split("/") if p]
    prefix = "/".join(parts[:path_prefix_depth]) if parts else ""
    return f"{host}/{prefix}" if prefix else host


def block_signature(tag: Tag) -> str | None:
    """Stable fingerprint for cross-page matching (not full XPath — too brittle)."""
    if not isinstance(tag, Tag) or not tag.name:
        return None
    if tag.name in {"html", "body", "main", "article"}:
        return None

    classes = tag.get("class") or []
    if isinstance(classes, str):
        classes = [classes]
    class_part = ".".join(sorted(str(c).lower() for c in classes[:6]))
    id_part = str(tag.get("id") or "").lower()
    role = str(tag.get("role") or "").lower()

    text = _WS.sub(" ", tag.get_text(" ", strip=True))[:240].lower()
    # Prefer structural attrs; fall back to text hash for anonymous repeated widgets
    structural = f"{tag.name}|id={id_part}|class={class_part}|role={role}"
    if id_part or class_part or role:
        key = structural
    else:
        if len(text) < 20:
            return None
        key = f"{tag.name}|texthash={hashlib.md5(text.encode()).hexdigest()[:12]}"

    return hashlib.sha1(key.encode()).hexdigest()[:16]


def _chrome_like(
    tag: Tag,
    *,
    max_chars: int,
) -> bool:
    text = tag.get_text(" ", strip=True)
    n = len(text)
    if n == 0 or n > max_chars:
        return False
    ld = link_density(tag)
    td = text_density(tag)
    tokens = set()
    blob = " ".join(
        str(x)
        for x in (
            tag.get("id"),
            " ".join(tag.get("class") or []),
            tag.get("role"),
            tag.name,
        )
        if x
    ).lower()
    for tok in re.split(r"[\s_\-:/]+", blob):
        if tok:
            tokens.add(tok)

    chrome_tokens = {
        "nav",
        "navbar",
        "menu",
        "footer",
        "header",
        "cookie",
        "consent",
        "newsletter",
        "subscribe",
        "chat",
        "cta",
        "promo",
        "banner",
        "social",
        "sidebar",
    }
    phrase_hits = any(
        p in text.lower()
        for p in (
            "subscribe",
            "talk to sales",
            "contact sales",
            "request a demo",
            "cookie",
            "accept all",
            "sign in",
            "get started free",
        )
    )
    if tokens & chrome_tokens or phrase_hits:
        return True
    # Repeated chrome is often link-dense and not prose-dense
    if ld >= 0.45 and n < max_chars:
        return True
    if ld >= 0.30 and td < 0.20 and n < 800:
        return True
    return False


def collect_page_signatures(
    html: str,
    *,
    max_chars: int = 2500,
) -> dict[str, dict]:
    soup = BeautifulSoup(html, "lxml")
    body = soup.body or soup
    found: dict[str, dict] = {}
    for tag in body.find_all(["div", "nav", "aside", "header", "footer", "section", "ul"]):
        if not isinstance(tag, Tag):
            continue
        # Prefer mid-level nodes; skip tiny leaves
        text = tag.get_text(" ", strip=True)
        if len(text) < 30:
            continue
        sig = block_signature(tag)
        if not sig:
            continue
        # Keep shallowest occurrence of a signature on this page
        if sig in found:
            continue
        found[sig] = {
            "text": text[:200],
            "chars": len(text),
            "link_density": link_density(tag),
            "chrome_like": _chrome_like(tag, max_chars=max_chars),
            "tag": tag.name,
        }
    return found


def mine_site_chrome(
    pages: Iterable[tuple[str | None, str]],
    *,
    min_pages: int = 5,
    frequency: float = 0.70,
    max_block_chars: int = 2500,
    require_chrome_features: bool = True,
    path_prefix_depth: int = 1,
) -> dict[str, SiteChromeModel]:
    """
    pages: iterable of (url, html)
    Returns models keyed by site_group_key.

    Design guards (do not relax casually):
      - min_pages default 5 — with 2–3 pages frequency mining invents false chrome
      - require_chrome_features — frequency alone will strip shared product blurbs
      - path_prefix_depth default 1 — keep /docs vs /products models separate
    """
    grouped: dict[str, list[dict[str, dict]]] = defaultdict(list)
    for url, html in pages:
        key = site_group_key(url, path_prefix_depth=path_prefix_depth)
        grouped[key].append(collect_page_signatures(html, max_chars=max_block_chars))

    models: dict[str, SiteChromeModel] = {}
    for key, page_maps in grouped.items():
        n = len(page_maps)
        if n < min_pages:
            models[key] = SiteChromeModel(group_key=key, n_pages=n)
            continue

        # With barely enough pages, demand near-universal presence.
        effective_freq = frequency
        if n < 8:
            effective_freq = max(frequency, 0.80)

        hit_pages: Counter[str] = Counter()
        samples: dict[str, dict] = {}
        link_acc: dict[str, float] = defaultdict(float)
        char_acc: dict[str, float] = defaultdict(float)
        chrome_votes: dict[str, int] = defaultdict(int)

        for fmap in page_maps:
            for sig, meta in fmap.items():
                hit_pages[sig] += 1
                link_acc[sig] += float(meta["link_density"])
                char_acc[sig] += float(meta["chars"])
                if meta["chrome_like"]:
                    chrome_votes[sig] += 1
                samples.setdefault(sig, meta)

        details: list[ChromeSignature] = []
        selected: set[str] = set()
        for sig, hits in hit_pages.items():
            freq = hits / n
            if freq < effective_freq:
                continue
            avg_chars = char_acc[sig] / hits
            if avg_chars > max_block_chars:
                continue
            chrome_ratio = chrome_votes[sig] / hits
            if require_chrome_features and chrome_ratio < 0.5:
                continue
            selected.add(sig)
            details.append(
                ChromeSignature(
                    signature=sig,
                    sample_text=str(samples[sig]["text"]),
                    page_hits=hits,
                    frequency=freq,
                    avg_link_density=link_acc[sig] / hits,
                    avg_chars=avg_chars,
                )
            )

        details.sort(key=lambda d: (-d.frequency, -d.page_hits))
        models[key] = SiteChromeModel(
            group_key=key,
            n_pages=n,
            signatures=selected,
            details=details,
        )
    return models


def apply_site_chrome(soup: BeautifulSoup, model: SiteChromeModel | None) -> int:
    """Remove matching chrome blocks in-place. Returns number of nodes removed."""
    if model is None or not model.signatures:
        return 0
    body = soup.body or soup
    removed = 0
    for tag in list(body.find_all(["div", "nav", "aside", "header", "footer", "section", "ul"])):
        if not isinstance(tag, Tag):
            continue
        sig = block_signature(tag)
        if sig and model.should_strip(sig):
            tag.decompose()
            removed += 1
    return removed


def save_chrome_models(models: dict[str, SiteChromeModel], path: str | Path) -> None:
    """Persist learned chrome models as JSON (for learn-then-extract workflows)."""
    payload = {
        "version": 1,
        "models": {
            key: {
                "group_key": m.group_key,
                "n_pages": m.n_pages,
                "signatures": sorted(m.signatures),
                "details": [
                    {
                        "signature": d.signature,
                        "sample_text": d.sample_text,
                        "page_hits": d.page_hits,
                        "frequency": d.frequency,
                        "avg_link_density": d.avg_link_density,
                        "avg_chars": d.avg_chars,
                    }
                    for d in m.details
                ],
            }
            for key, m in models.items()
        },
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_chrome_models(path: str | Path) -> dict[str, SiteChromeModel]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[str, SiteChromeModel] = {}
    for key, raw in data.get("models", {}).items():
        details = [
            ChromeSignature(
                signature=d["signature"],
                sample_text=d.get("sample_text", ""),
                page_hits=int(d.get("page_hits", 0)),
                frequency=float(d.get("frequency", 0.0)),
                avg_link_density=float(d.get("avg_link_density", 0.0)),
                avg_chars=float(d.get("avg_chars", 0.0)),
            )
            for d in raw.get("details", [])
        ]
        out[key] = SiteChromeModel(
            group_key=raw.get("group_key", key),
            n_pages=int(raw.get("n_pages", 0)),
            signatures=set(raw.get("signatures", [])),
            details=details,
        )
    return out


def select_model_for_url(
    models: dict[str, SiteChromeModel],
    url: str | None,
    *,
    path_prefix_depth: int = 1,
) -> SiteChromeModel | None:
    """Pick the best matching chrome model for a URL (exact group, else host)."""
    if not models or not url:
        return None
    key = site_group_key(url, path_prefix_depth=path_prefix_depth)
    if key in models and models[key].signatures:
        return models[key]
    host = site_group_key(url, path_prefix_depth=0)
    if host in models and models[host].signatures:
        return models[host]
    # Prefix match: model key is host/prefix and url shares host
    for mkey, model in models.items():
        if model.signatures and (mkey == host or mkey.startswith(host + "/")):
            if key.startswith(mkey) or mkey.startswith(host):
                return model
    return None
