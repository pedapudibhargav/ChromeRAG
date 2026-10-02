"""Learn which class and id names mark chrome, from human-labelled WCXB pages.

For every element that carries a class or id, compare its words with the page's reference
main content. An element whose words are almost all missing from the reference is noise; one
whose words are almost all present is content. A name is reported when, on many sites, it
marks noise nearly every time. Output is a ranked list for review: nothing is applied
automatically, and each accepted name still needs evidence and a fixture (rules/README.md).

Use the dev split only. The validation half is chosen by hashing the site name, so the same
site never appears in both halves.

  python -m poc.learn_tokens --split dev --out /tmp/cr/tokens.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from urllib.parse import urlparse

from bs4 import Tag

from chromerag.density import parse_html, strip_non_content_tags
from chromerag.hidden import remove_hidden_nodes, remove_skip_links
from poc.wcxb import load_split, tokenize

MIN_CHARS = 25
NOISE_MAX = 0.10
CONTENT_MIN = 0.80


def site_of(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return host


def half(site: str) -> str:
    return "learn" if int(hashlib.sha1(site.encode()).hexdigest(), 16) % 2 == 0 else "valid"


SPLIT = False  # set by --subtokens: report words inside class names (footer-links -> footer, links)


def names_of(tag: Tag) -> list[str]:
    out: list[str] = []
    values = [str(c).lower() for c in tag.get("class") or []] + [str(tag.get("id") or "").lower()]
    for value in values:
        if not (2 < len(value) < 40) or re.search(r"\d{3,}", value):
            continue
        if SPLIT:
            out.extend(part for part in re.split(r"[^a-z]+", value) if len(part) > 2)
        else:
            out.append(value)
    return list(dict.fromkeys(out))


def scan(split: str) -> dict[str, dict]:
    stats: dict[str, dict] = defaultdict(
        lambda: {"noise": Counter(), "content": Counter(), "sites_noise": defaultdict(set),
                 "sites_content": defaultdict(set), "chars_noise": 0, "chars_content": 0, "types": Counter()}
    )
    for page in load_split(split):
        ref = set(tokenize(page.main_content))
        if len(ref) < 30:
            continue
        site, h = site_of(page.url), None
        h = half(site)
        soup = parse_html(page.html)
        strip_non_content_tags(soup)
        remove_hidden_nodes(soup)
        remove_skip_links(soup)
        body = soup.body or soup
        for tag in body.find_all(True):
            names = names_of(tag)
            if not names:
                continue
            text = tag.get_text(" ", strip=True)
            if len(text) < MIN_CHARS:
                continue
            toks = tokenize(text)
            if not toks:
                continue
            frac = sum(1 for t in toks if t in ref) / len(toks)
            if frac <= NOISE_MAX:
                kind = "noise"
            elif frac >= CONTENT_MIN:
                kind = "content"
            else:
                continue
            for n in names:
                s = stats[n]
                s[kind][h] += 1
                s["sites_" + kind][h].add(site)
                s["chars_" + kind] += len(text)
                if kind == "noise":
                    s["types"][page.page_type] += 1
    return stats


def summarize(stats: dict[str, dict], min_sites: int) -> list[dict]:
    rows = []
    for name, s in stats.items():
        n_noise = sum(s["noise"].values())
        n_content = sum(s["content"].values())
        sites_noise = {x for v in s["sites_noise"].values() for x in v}
        if len(sites_noise) < min_sites:
            continue
        purity = n_noise / (n_noise + n_content)
        rows.append(
            {
                "name": name,
                "noise": n_noise,
                "content": n_content,
                "purity": round(purity, 3),
                "sites_noise": len(sites_noise),
                "learn_noise": s["noise"]["learn"], "learn_content": s["content"]["learn"],
                "valid_noise": s["noise"]["valid"], "valid_content": s["content"]["valid"],
                "chars_noise": s["chars_noise"],
                "chars_content": s["chars_content"],
                "types": dict(s["types"]),
            }
        )
    rows.sort(key=lambda r: (-r["purity"], -r["chars_noise"]))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=["dev"])
    ap.add_argument("--min-sites", type=int, default=4)
    ap.add_argument("--subtokens", action="store_true")
    ap.add_argument("--out", default="/tmp/cr/tokens.json")
    a = ap.parse_args()
    global SPLIT
    SPLIT = a.subtokens
    rows = summarize(scan(a.split), a.min_sites)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1)
    print(len(rows), "names ->", a.out)


if __name__ == "__main__":
    main()
