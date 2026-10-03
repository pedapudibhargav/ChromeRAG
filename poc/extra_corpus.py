"""Fetch extra held-out test pages: popular documentation sites and online shops (product pages).

Seeds are listed in poc/extra_seeds.json (written before any extractor ran on these pages). For each documentation
site: the start page plus up to 4 more pages found among its own links (same host, same section, chosen with a
seeded RNG). For each shop: up to 3 product pages found on the home page or on its catalogue page. robots.txt is
respected, one request per second per host. Output (git-ignored): data/extra_raw/<kind>/<id>.html + .meta.json.

With EXTRA_FINAL2=1: articles, forums, listings and services from poc/extra_seeds_final2.json into
data/extra_raw_final2/<kind>/.

  python -m poc.extra_corpus
  EXTRA_FINAL2=1 python -m poc.extra_corpus --dry-check
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from poc.crawl_site_groups import DELAY_S, _allowed
from poc.fetch_pages import HEADERS, _ssl_verify

ROOT = Path(__file__).resolve().parents[1]

_FINAL2 = os.environ.get("EXTRA_FINAL2") == "1"
_FINAL = os.environ.get("EXTRA_FINAL") == "1"
if _FINAL2:
    OUT = ROOT / "data" / "extra_raw_final2"
    SEEDS = ROOT / "poc" / "extra_seeds_final2.json"
elif _FINAL:
    OUT = ROOT / "data" / "extra_raw_final"
    SEEDS = ROOT / "poc" / "extra_seeds_final.json"
else:
    OUT = ROOT / "data" / "extra_raw"
    SEEDS = ROOT / "poc" / "extra_seeds.json"

SEED = 20261002
PER_SHOP = 6
_PRODUCT = re.compile(r"/(products?|p|dp|ip|pd|item|itm|shop/[^/]+/p)/[^/?#]+|[-/]p-?\d{4,}|/pdp/", re.I)
_BAD_EXT = re.compile(r"\.(pdf|png|jpe?g|gif|svg|zip|mp4|xml|json|css|js|ico|webp)$", re.I)
_DATE = re.compile(r"/\d{4}/\d{2}/")
_EXCLUDE_ARTICLE = re.compile(r"tag|category|topic|author|page|search|login", re.I)
_FORUM = re.compile(r"/t/[^/]+/\d+|/questions/\d+/[^/]+|/(?:thread|topic|viewtopic)", re.I)
_LISTING = re.compile(r"/category|/tag|/browse|/list|/collections/", re.I)
_SERVICE = re.compile(r"pricing|features|product|solutions|platform|about|services", re.I)


def _hostname_id(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host.replace(".", "-")


def _slug_len(path: str) -> int:
    segs = [s for s in path.split("/") if s]
    return max((len(s) for s in segs), default=0)


def _is_article(path: str) -> bool:
    if _EXCLUDE_ARTICLE.search(path):
        return False
    segs = [s for s in path.strip("/").split("/") if s]
    if len(segs) < 2:
        return False
    if _DATE.search(path):
        return True
    return segs[-1].count("-") >= 3


def _pick_articles(cands: list[str], rng: random.Random, n: int) -> list[str]:
    scored = [(u, _slug_len(urlparse(u).path)) for u in cands if _is_article(urlparse(u).path)]
    scored.sort(key=lambda x: (-x[1], rng.random()))
    return [u for u, _ in scored[:n]]


def _pick_forums(cands: list[str], rng: random.Random, n: int) -> list[str]:
    hits = [u for u in cands if _FORUM.search(urlparse(u).path)]
    rng.shuffle(hits)
    return hits[:n]


def _listing_cands(links: list[str], seed_path: str, host: str) -> list[str]:
    first = seed_path.strip("/").split("/")[0] if seed_path.strip("/") else ""
    out: list[str] = []
    for u in links:
        p = urlparse(u)
        if p.netloc != host or p.path.rstrip("/") == seed_path.rstrip("/"):
            continue
        if first and p.path.startswith(f"/{first}"):
            out.append(u)
        elif _LISTING.search(p.path):
            out.append(u)
    return list(dict.fromkeys(out))


def _service_cands(links: list[str], seed_path: str, host: str) -> list[str]:
    out: list[str] = []
    for u in links:
        p = urlparse(u)
        if p.netloc != host or p.path.rstrip("/") == seed_path.rstrip("/"):
            continue
        if _SERVICE.search(p.path):
            out.append(u)
    return list(dict.fromkeys(out))


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


def _fetch_pages(site: str, seed_url: str, kind: str, *, save_seed: bool, max_extra: int) -> int:
    rng = random.Random(f"{SEED}-{site}")
    with httpx.Client(follow_redirects=True, timeout=30.0, headers=HEADERS, verify=_ssl_verify()) as client:
        robots: dict = {}
        r = _get(client, seed_url, robots)
        if r is None:
            return 0
        base = urlparse(str(r.url))
        host = base.netloc
        same = [u for u in _links(r.text, str(r.url)) if urlparse(u).netloc == host]
        n = 0
        if save_seed:
            if len(r.text) <= 5000:
                return 0
            _save(kind, f"{site}-00", site, seed_url, r)
            n = 1
        if kind == "articles":
            pool = _pick_articles(same, rng, max_extra)
        elif kind == "forums":
            pool = _pick_forums(same, rng, max_extra)
        elif kind == "listings":
            pool = _listing_cands(same, base.path, host)
            rng.shuffle(pool)
            pool = pool[:max_extra]
        else:
            pool = _service_cands(same, base.path, host)
            rng.shuffle(pool)
            pool = pool[:max_extra]
        for u in pool:
            rr = _get(client, u, robots)
            if rr is not None and len(rr.text) > 5000:
                _save(kind, f"{site}-{n:02d}", site, u, rr)
                n += 1
        return n


def articles_site(seed_url: str) -> int:
    return _fetch_pages(_hostname_id(seed_url), seed_url, "articles", save_seed=False, max_extra=4)


def forums_site(seed_url: str) -> int:
    return _fetch_pages(_hostname_id(seed_url), seed_url, "forums", save_seed=False, max_extra=4)


def listings_site(seed_url: str) -> int:
    return _fetch_pages(_hostname_id(seed_url), seed_url, "listings", save_seed=True, max_extra=2)


def services_site(seed_url: str) -> int:
    return _fetch_pages(_hostname_id(seed_url), seed_url, "services", save_seed=True, max_extra=2)


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


def _print_dry_summary() -> None:
    for kind in ("articles", "forums", "listings", "services"):
        metas = sorted((OUT / kind).glob("*.meta.json"))
        if not metas:
            print(f"{kind}: (none saved)")
            continue
        m = json.loads(metas[0].read_text())
        html = (OUT / kind / f"{m['id']}.html").read_text(encoding="utf-8", errors="ignore")
        print(f"{kind}: {m['url']} ({len(html)} bytes)")


def main() -> None:
    seeds = json.loads(SEEDS.read_text())
    dry = "--dry-check" in sys.argv
    only = next((a for a in sys.argv[1:] if not a.startswith("-")), "all")

    if _FINAL2:
        fns = {"articles": articles_site, "forums": forums_site, "listings": listings_site, "services": services_site}
        counts: dict[str, list[int]] = {k: [] for k in fns}
        with ThreadPoolExecutor(max_workers=12) as pool:
            for kind, fn in fns.items():
                if only not in ("all", kind):
                    continue
                urls = seeds[kind][:2] if dry else seeds[kind]
                counts[kind] = list(pool.map(fn, urls))
        for kind, xs in counts.items():
            if xs:
                print(f"{kind}: {sum(xs)} pages from {sum(1 for x in xs if x)} sites")
        if dry:
            _print_dry_summary()
        return

    d, s = [], []
    with ThreadPoolExecutor(max_workers=12) as pool:
        if only in ("all", "docs"):
            d = list(pool.map(lambda kv: docs_site(*kv), seeds["docs"].items()))
        if only in ("all", "products"):
            s = list(pool.map(shop, seeds["shops"]))
    print(f"docs: {sum(d)} pages from {sum(1 for x in d if x)} sites; products: {sum(s)} pages from {sum(1 for x in s if x)} shops")


if __name__ == "__main__":
    main()
