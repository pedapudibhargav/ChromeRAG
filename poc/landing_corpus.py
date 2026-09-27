"""Build and fetch the landing-page benchmark (company marketing sites).

For each company in poc/landing_companies.json the corpus has up to five pages chosen from
the homepage's own links, in page order, without looking at any extractor's output:
the homepage, the first pricing/plans page, and the first product/platform/solutions pages.
Documentation, blog, careers, login and legal links are skipped, so the cohort is
marketing pages only.

  --plan   fetch homepages and write poc/landing_urls.json (published with the repository)
  --fetch  fetch every listed page into data/landing_raw/ (robots.txt respected,
           one request per second per host), in the same layout as data/raw/

Usage:
  python -m poc.landing_corpus --plan --fetch
  python -m poc.run_landing_eval
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from poc.crawl_site_groups import DELAY_S, HOST_WORKERS, _allowed
from poc.fetch_pages import HEADERS, _ssl_verify, sniff_signals
from poc.run_corpus_comparison import ROOT

COMPANIES = ROOT / "poc" / "landing_companies.json"
URLS = ROOT / "poc" / "landing_urls.json"
RAW = ROOT / "data" / "landing_raw"
MAX_PAGES = 5
MAX_PRODUCT = 4

_PRICING = re.compile(r"(^|/)(pricing|plans)(/|$|\.)", re.I)
_PRODUCT = re.compile(
    r"(^|/)(products?|platform|solutions?|features?|services|capabilities|industries|use-cases)(/|$)",
    re.I,
)
_SKIP = re.compile(
    r"(^|/)(docs?|documentation|developers?|api|blog|news|press|newsroom|careers?|jobs|login|"
    r"log-in|signin|sign-in|signup|sign-up|register|account|legal|privacy|terms|cookie|"
    r"support|help|community|events?|webinars?|resources|investors?|contact|search)(/|$)",
    re.I,
)
_LOCALE = re.compile(r"^/([a-z]{2})(-[a-z]{2})?(/|$)", re.I)
_EXT = re.compile(r"\.(pdf|png|jpe?g|gif|svg|zip|mp4|xml|json)$", re.I)


def _site(netloc: str) -> str:
    parts = netloc.lower().split(":")[0].split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else netloc.lower()


def _candidate(href: str, base: str) -> str | None:
    url = urljoin(base, href).split("#", 1)[0]
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.query or _EXT.search(parsed.path):
        return None
    if _site(parsed.netloc) != _site(urlparse(base).netloc):
        return None
    locale = _LOCALE.match(parsed.path)
    if locale and locale.group(1).lower() not in {"en", "us"}:
        return None
    if _SKIP.search(parsed.path):
        return None
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def choose_pages(homepage: str, html: str) -> list[tuple[str, str]]:
    """(role, url) pairs from the homepage's links, in document order."""
    chosen: list[tuple[str, str]] = [("homepage", homepage)]
    seen = {homepage.rstrip("/")}
    pricing: str | None = None
    products: list[str] = []
    for a in BeautifulSoup(html, "lxml").find_all("a", href=True):
        url = _candidate(a["href"], homepage)
        if not url or url.rstrip("/") in seen:
            continue
        path = urlparse(url).path
        if pricing is None and _PRICING.search(path):
            pricing = url
            seen.add(url.rstrip("/"))
        elif len(products) < MAX_PRODUCT and _PRODUCT.search(path):
            products.append(url)
            seen.add(url.rstrip("/"))
    if pricing:
        chosen.append(("pricing", pricing))
    chosen.extend(("product", u) for u in products)
    return chosen[:MAX_PAGES]


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _save(page_id: str, url: str, response: httpx.Response, company: dict, role: str) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"{page_id}.html").write_text(response.text, encoding="utf-8")
    meta = {
        "id": page_id,
        "url": str(response.url),
        "requested_url": url,
        "category": role,
        "company": company["name"],
        "sector": company["sector"],
        "status_code": response.status_code,
        "signals": sniff_signals(response.text),
    }
    (RAW / f"{page_id}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _get(client: httpx.Client, url: str, robots: dict) -> httpx.Response | None:
    if not _allowed(client, url, robots):
        return None
    try:
        r = client.get(url)
        r.raise_for_status()
        return r
    except httpx.HTTPError:
        return None


def plan() -> dict:
    companies = json.loads(COMPANIES.read_text(encoding="utf-8"))["companies"]
    result: dict[str, dict] = {}

    def one(company: dict) -> tuple[str, dict]:
        robots: dict = {}
        with httpx.Client(follow_redirects=True, timeout=30.0, headers=HEADERS, verify=_ssl_verify()) as client:
            r = _get(client, company["homepage"], robots)
            if r is None:
                return company["name"], {"sector": company["sector"], "pages": [], "note": "homepage not fetched"}
            _save(f"{_slug(company['name'])}-00", company["homepage"], r, company, "homepage")
            pages = choose_pages(str(r.url), r.text)
            return company["name"], {
                "sector": company["sector"],
                "pages": [{"role": role, "url": url} for role, url in pages],
            }

    with ThreadPoolExecutor(max_workers=HOST_WORKERS) as pool:
        for name, entry in pool.map(one, companies):
            result[name] = entry
    payload = {
        "description": (
            "Landing-page benchmark URLs chosen by poc/landing_corpus.py from each company's "
            "homepage links (homepage, first pricing page, first product/solutions pages)."
        ),
        "companies": result,
    }
    URLS.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def fetch() -> dict:
    companies = {c["name"]: c for c in json.loads(COMPANIES.read_text(encoding="utf-8"))["companies"]}
    listed = json.loads(URLS.read_text(encoding="utf-8"))["companies"]
    by_host: dict[str, list[tuple[str, str, dict, str]]] = defaultdict(list)
    for name, entry in listed.items():
        for i, page in enumerate(entry["pages"]):
            page_id = f"{_slug(name)}-{i:02d}"
            by_host[urlparse(page["url"]).netloc].append((page_id, page["url"], companies[name], page["role"]))
    counts: Counter[str] = Counter()

    def host_jobs(jobs: list[tuple[str, str, dict, str]]) -> None:
        robots: dict = {}
        with httpx.Client(follow_redirects=True, timeout=30.0, headers=HEADERS, verify=_ssl_verify()) as client:
            for page_id, url, company, role in jobs:
                if (RAW / f"{page_id}.meta.json").exists():
                    counts["ok"] += 1
                    continue
                time.sleep(DELAY_S)
                r = _get(client, url, robots)
                if r is None:
                    counts["failed_or_disallowed"] += 1
                    continue
                _save(page_id, url, r, company, role)
                counts["ok"] += 1

    with ThreadPoolExecutor(max_workers=HOST_WORKERS) as pool:
        list(pool.map(host_jobs, by_host.values()))
    return dict(counts)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--plan", action="store_true")
    p.add_argument("--fetch", action="store_true")
    args = p.parse_args()
    if not (args.plan or args.fetch):
        p.error("pass --plan and/or --fetch")
    if args.plan:
        payload = plan()
        pages = [pg for e in payload["companies"].values() for pg in e["pages"]]
        print(f"Planned {len(pages)} pages from {len(payload['companies'])} companies:", Counter(pg["role"] for pg in pages))
    if args.fetch:
        print("Fetched:", fetch())


if __name__ == "__main__":
    main()
