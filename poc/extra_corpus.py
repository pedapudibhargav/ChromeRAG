"""Fetch extra held-out test pages: popular documentation sites and online shops (product pages).

Seeds are listed in poc/extra_seeds.json (written before any extractor ran on these pages). For each documentation
site: the start page plus up to 4 more pages found among its own links (same host, same section, chosen with a
seeded RNG). For each shop: up to 3 product pages found on the home page or on its catalogue page. robots.txt is
respected, one request per second per host. Output (git-ignored): data/extra_raw/<kind>/<id>.html + .meta.json.

  python -m poc.extra_corpus
"""

from __future__ import annotations

import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from poc.crawl_site_groups import DELAY_S, _allowed
from poc.fetch_pages import HEADERS, _ssl_verify

ROOT = Path(__file__).resolve().parents[1]
import os

_FINAL = os.environ.get("EXTRA_FINAL") == "1"  # the frozen final test: seeds written before any extractor ran on them
OUT = ROOT / "data" / ("extra_raw_final" if _FINAL else "extra_raw")
SEEDS = ROOT / "poc" / ("extra_seeds_final.json" if _FINAL else "extra_seeds.json")
SEED = 20261002
PER_SHOP = 6
_PRODUCT = re.compile(r"/(products?|p|dp|ip|pd|item|itm|shop/[^/]+/p)/[^/?#]+|[-/]p-?\d{4,}|/pdp/", re.I)
_BAD_EXT = re.compile(r"\.(pdf|png|jpe?g|gif|svg|zip|mp4|xml|json|css|js|ico|webp)$", re.I)


def _get(client: httpx.Client, url: str, robots: dict) -> httpx.Response | None:
    if not _allowed(client, url, robots):
        return None
    try:
        time.sleep(DELAY_S)
        r = client.get(url)
        r.raise_for_status()
        return r if "html" in r.headers.get("content-type", "") else None
    except httpx.HTTPError:
        return None


def _links(html: str, base: str) -> list[str]:
    out = []
    for a in BeautifulSoup(html, "lxml").find_all("a", href=True):
        url = urljoin(base, a["href"]).split("#")[0]
        p = urlparse(url)
        if p.scheme in ("http", "https") and not p.query and not _BAD_EXT.search(p.path):
            out.append(url)
    return list(dict.fromkeys(out))


def _save(kind: str, pid: str, site: str, requested: str, r: httpx.Response) -> None:
    d = OUT / kind
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{pid}.html").write_text(r.text, encoding="utf-8")
    (d / f"{pid}.meta.json").write_text(json.dumps({"id": pid, "site": site, "url": str(r.url), "requested": requested, "kind": kind}, indent=1))


def docs_site(name: str, seed_url: str) -> int:
    rng = random.Random(f"{SEED}-{name}")
    with httpx.Client(follow_redirects=True, timeout=30.0, headers=HEADERS, verify=_ssl_verify()) as client:
        robots: dict = {}
        r = _get(client, seed_url, robots)
        if r is None:
            return 0
        _save("docs", f"{name}-00", name, seed_url, r)
        base = urlparse(str(r.url))
        prefix = "/".join(base.path.split("/")[:3])  # same documentation section
        cands = [u for u in _links(r.text, str(r.url)) if urlparse(u).netloc == base.netloc and urlparse(u).path.startswith(prefix)
                 and urlparse(u).path.rstrip("/") != base.path.rstrip("/")]
        rng.shuffle(cands)
        n = 1
        for u in cands:
            if n >= 5:
                break
            rr = _get(client, u, robots)
            if rr is not None and len(rr.text) > 5000:
                _save("docs", f"{name}-{n:02d}", name, u, rr)
                n += 1
        return n


def shop(domain: str) -> int:
    rng = random.Random(f"{SEED}-{domain}")
    name = domain.split(".")[0]
    with httpx.Client(follow_redirects=True, timeout=30.0, headers=HEADERS, verify=_ssl_verify()) as client:
        robots: dict = {}
        found: list[str] = []
        for start in (f"https://www.{domain}/", f"https://{domain}/", f"https://{domain}/collections/all", f"https://www.{domain}/collections/all"):
            r = _get(client, start, robots)
            if r is None:
                continue
            host = urlparse(str(r.url)).netloc
            found = [u for u in _links(r.text, str(r.url)) if urlparse(u).netloc == host and _PRODUCT.search(urlparse(u).path)]
            if found:
                break
        rng.shuffle(found)
        n = 0
        for u in found:
            if n >= PER_SHOP:
                break
            rr = _get(client, u, robots)
            if rr is not None and len(rr.text) > 5000:
                _save("products", f"{name}-{n:02d}", name, u, rr)
                n += 1
        return n


def main() -> None:
    seeds = json.loads(SEEDS.read_text())
    import sys

    only = sys.argv[1] if len(sys.argv) > 1 else "all"
    d, s = [], []
    with ThreadPoolExecutor(max_workers=12) as pool:
        if only in ("all", "docs"):
            d = list(pool.map(lambda kv: docs_site(*kv), seeds["docs"].items()))
        if only in ("all", "products"):
            s = list(pool.map(shop, seeds["shops"]))
    print(f"docs: {sum(d)} pages from {sum(1 for x in d if x)} sites; products: {sum(s)} pages from {sum(1 for x in s if x)} shops")


if __name__ == "__main__":
    main()
