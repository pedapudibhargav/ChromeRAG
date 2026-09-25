"""Build and fetch a multi-page-per-site corpus for the STCE evaluation.

The public benchmark has one to nine pages per site, too few to learn a site
template. This script expands each documentation site group in the benchmark to
up to ``--per-group`` pages of the same group (host + first path segment):

  --plan   follow same-group links, in page order, from the stored benchmark HTML
           and write poc/stce_crawl_urls.json (published with the repository)
  --fetch  fetch that list into data/stce_crawl/ (robots.txt respected, one
           request per second), in the same layout as data/raw/

Usage:
  python -m poc.crawl_site_groups --plan     # needs data/raw from run_corpus_comparison
  python -m poc.crawl_site_groups --fetch    # network; reproduces data/stce_crawl/
  python -m poc.run_stce_eval --raw data/stce_crawl
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from chromerag.site_chrome import site_group_key
from poc.fetch_pages import HEADERS, _ssl_verify, sniff_signals
from poc.metrics import extract_anchors
from poc.run_corpus_comparison import MIN_CONTENT_ANCHORS, ROOT, load_ok_pages

URLS = ROOT / "poc" / "stce_crawl_urls.json"
CRAWL = ROOT / "data" / "stce_crawl"
DOC_CATEGORIES = {"docs", "api_docs", "cloud_docs", "api_docs_jsonld"}
PER_GROUP = 15
MIN_GROUP = 8
DELAY_S = 1.0
HOST_WORKERS = 16
_SKIP_EXT = re.compile(r"\.(pdf|png|jpe?g|gif|svg|zip|gz|tar|mp4|json|xml|txt|ya?ml)$", re.I)


def _normalize(href: str, base: str) -> str | None:
    url = urljoin(base, href).split("#", 1)[0]
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.query or _SKIP_EXT.search(parsed.path):
        return None
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def plan(*, per_group: int = PER_GROUP) -> dict:
    seeds: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for _, html, meta in load_ok_pages():
        if meta.get("category") not in DOC_CATEGORIES or not meta.get("url"):
            continue
        if extract_anchors(html)[2]["content_ngrams"] < MIN_CONTENT_ANCHORS:
            continue
        seeds[site_group_key(meta["url"])].append((meta["url"], html))

    groups: dict[str, list[str]] = {}
    for group in sorted(seeds):
        ordered: dict[str, None] = {}
        for url, _ in seeds[group]:
            ordered[_normalize(url, url) or url] = None
        for url, html in seeds[group]:
            for a in BeautifulSoup(html, "lxml").find_all("a", href=True):
                link = _normalize(a["href"], url)
                if link and site_group_key(link) == group:
                    ordered.setdefault(link, None)
        urls = list(ordered)[:per_group]
        if len(urls) >= MIN_GROUP:
            groups[group] = urls
    payload = {
        "description": (
            "Same-site page lists for the STCE evaluation: documentation site groups from "
            "poc/corpus_urls.json, expanded by following same-group links in page order."
        ),
        "per_group": per_group,
        "groups": groups,
    }
    URLS.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def _allowed(client: httpx.Client, url: str, cache: dict[str, robotparser.RobotFileParser]) -> bool:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in cache:
        rp = robotparser.RobotFileParser()
        try:
            r = client.get(f"{origin}/robots.txt")
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except httpx.HTTPError:
            rp.parse([])
        cache[origin] = rp
    return cache[origin].can_fetch(HEADERS["User-Agent"], url)


def _fetch_host(jobs: list[tuple[str, str]], counts: Counter[str]) -> None:
    """Fetch one host's pages sequentially, one request per DELAY_S."""
    robots: dict[str, robotparser.RobotFileParser] = {}
    with httpx.Client(follow_redirects=True, timeout=30.0, headers=HEADERS, verify=_ssl_verify()) as client:
        for page_id, url in jobs:
            if (CRAWL / f"{page_id}.meta.json").exists():
                counts["ok"] += 1
                continue
            if not _allowed(client, url, robots):
                counts["skipped_robots"] += 1
                continue
            time.sleep(DELAY_S)
            try:
                r = client.get(url)
                r.raise_for_status()
            except httpx.HTTPError:
                counts["failed"] += 1
                continue
            (CRAWL / f"{page_id}.html").write_text(r.text, encoding="utf-8")
            meta = {
                "id": page_id,
                "url": str(r.url),
                "requested_url": url,
                "category": "docs",
                "status_code": r.status_code,
                "signals": sniff_signals(r.text),
            }
            (CRAWL / f"{page_id}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
            counts["ok"] += 1


def fetch() -> dict:
    groups = json.loads(URLS.read_text(encoding="utf-8"))["groups"]
    CRAWL.mkdir(parents=True, exist_ok=True)
    by_host: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for group, urls in groups.items():
        slug = re.sub(r"[^a-z0-9]+", "-", group.lower()).strip("-")
        for i, url in enumerate(urls):
            by_host[urlparse(url).netloc].append((f"{slug}-{i:02d}", url))
    counts: Counter[str] = Counter()
    # Hosts run in parallel; each host is fetched sequentially at one request per second.
    with ThreadPoolExecutor(max_workers=HOST_WORKERS) as pool:
        for future in [pool.submit(_fetch_host, jobs, counts) for jobs in by_host.values()]:
            future.result()
    return dict(counts)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--plan", action="store_true")
    p.add_argument("--fetch", action="store_true")
    p.add_argument("--per-group", type=int, default=PER_GROUP)
    args = p.parse_args()
    if not (args.plan or args.fetch):
        p.error("pass --plan and/or --fetch")
    if args.plan:
        payload = plan(per_group=args.per_group)
        n = sum(len(v) for v in payload["groups"].values())
        print(f"Planned {len(payload['groups'])} site groups, {n} URLs -> {URLS}")
    if args.fetch:
        print(f"Fetched into {CRAWL}: {fetch()}")


if __name__ == "__main__":
    main()
