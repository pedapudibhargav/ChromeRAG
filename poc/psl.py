"""Minimal Public Suffix List parser (wildcard and exception rules)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_PSL = Path(__file__).resolve().parent / "public_suffix_list.dat"


@dataclass
class PublicSuffixList:
    rules: frozenset[str]
    wildcards: frozenset[str]
    exceptions: frozenset[str]
    version_line: str


def _parse_dat(text: str) -> PublicSuffixList:
    rules: set[str] = set()
    wildcards: set[str] = set()
    exceptions: set[str] = set()
    version_line = ""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            if line.startswith("// VERSION:"):
                version_line = line.removeprefix("// VERSION:").strip()
            continue
        if line.startswith("!"):
            exceptions.add(line[1:].lower())
        elif line.startswith("*."):
            wildcards.add(line[2:].lower())
        else:
            rules.add(line.lower())
    return PublicSuffixList(
        rules=frozenset(rules),
        wildcards=frozenset(wildcards),
        exceptions=frozenset(exceptions),
        version_line=version_line,
    )


@lru_cache(maxsize=4)
def load_psl(path: str | Path = DEFAULT_PSL) -> PublicSuffixList:
    return _parse_dat(Path(path).read_text(encoding="utf-8"))


def public_suffix(host: str, psl: PublicSuffixList | None = None) -> str:
    """Longest public suffix for *host* (no port, lowercase)."""
    psl = psl or load_psl()
    host = host.lower().strip(".")
    if not host or host.startswith("."):
        return host
    labels = host.split(".")
    n = len(labels)
    for i in range(n):
        suffix = ".".join(labels[i:])
        if suffix in psl.exceptions:
            if i + 1 < n:
                return ".".join(labels[i + 1 :])
            continue
        if suffix in psl.rules:
            return suffix
        if i + 1 < n:
            wild_rest = ".".join(labels[i + 1 :])
            if wild_rest in psl.wildcards:
                return suffix
    return labels[-1] if labels else host


def registrable_domain(url_or_host: str, psl: PublicSuffixList | None = None) -> str:
    """eTLD+1 from a URL or hostname (``www.`` stripped)."""
    psl = psl or load_psl()
    if "://" in url_or_host or url_or_host.startswith("//"):
        host = urlparse(url_or_host).netloc.split(":")[0]
    else:
        host = url_or_host.split(":")[0]
    host = host.lower().removeprefix("www.").strip(".")
    if not host:
        return ""
    ps = public_suffix(host, psl)
    labels = host.split(".")
    ps_labels = ps.split(".")
    if len(labels) <= len(ps_labels):
        return host
    reg_labels = labels[-(len(ps_labels) + 1) :]
    return ".".join(reg_labels)
