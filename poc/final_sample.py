"""Mechanical Tranco sampling + locked final page fetch (P04).

Discovers URLs per evaluations/2026-11-final/PROTOCOL.md, freezes seed_page_list.json,
then fetches via poc.final_collect.collect. Offline tests inject a fake HTTP handler.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from chromerag.schema_fusion import parse_json_ld
from poc.extra_corpus import (
    _FORUM,
    _LISTING,
    _PRODUCT,
    _SERVICE,
    _is_article,
)
from poc.fetch_pages import HEADERS
from poc.final_collect import (
    DEFAULT_OUT,
    MAX_PAGES_PER_DOMAIN,
    MIN_VISIBLE_WORDS,
    SAMPLE_SEED,
    build_ca_bundle,
    build_excluded,
    collect,
    domain_for_url,
    is_excluded_domain,
    normalize_url,
    validate_fetched,
    visible_word_count,
)
from poc.final_collect import _robots_ok as robots_ok
from poc.final_collect import _wait_domain as wait_domain
from poc.psl import load_psl, registrable_domain

# Keep shared-validator symbols imported for callers/tests (defined in final_collect).
_SHARED_VALIDATOR = (MIN_VISIBLE_WORDS, visible_word_count, validate_fetched)

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "evaluations" / "2026-11-final"
DEFAULT_TRANCO = ROOT / "data" / "final" / "tranco.csv"
DEFAULT_LIST_ID = ROOT / "data" / "final" / "tranco_list_id.txt"
DEFAULT_SEEDS_OUT = EVAL_DIR / "seed_page_list.json"
DEFAULT_SKIPPED = DEFAULT_OUT / "skipped.jsonl"
DEFAULT_SAMPLE_REPORT = DEFAULT_OUT / "sample_report.json"

MAX_RANK = 200_000
MAX_DOMAINS_TRIED = 8000
DOMAIN_BATCH_SIZE = 128
MAX_CANDIDATES_PER_DOMAIN = 12
DOMAIN_DEADLINE_SECONDS = 150.0

DOMAIN_KEYWORD_BLOCKLIST = (
    "porn",
    "xxx",
    "adult",
    "sexchat",
    "escort",
    "hentai",
    "gambl",
    "casino",
    "betting",
    "poker",
    "slot",
    "wager",
    "onlyfans",
)

QUOTAS: dict[str, int] = {
    "article": 119,
    "forum": 51,
    "listing": 27,
    "service": 88,
    "product": 10,
    "collection": 5,
    "landing": 10,
}

_BAD_EXT = re.compile(r"\.(pdf|png|jpe?g|gif|svg|zip|mp4|xml|css|js|ico|webp)$", re.I)
_PRICING_PATH = re.compile(r"^/pricing/?$", re.I)


@dataclass(frozen=True)
class Candidate:
    url: str
    page_type: str
    domain: str


HttpHandler = Callable[[str, str], httpx.Response]


def load_tranco_domains(
    csv_path: Path,
    *,
    max_rank: int = MAX_RANK,
) -> list[str]:
    """Return registrable domains for ranks 1..max_rank (column rank,domain)."""
    lines = csv_path.read_text(encoding="utf-8", errors="replace").splitlines()
    domains: list[str] = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",")
        if len(parts) < 2:
            continue
        try:
            rank = int(parts[0].strip())
        except ValueError:
            continue
        if rank > max_rank:
            continue
        dom = parts[1].strip().lower()
        if dom:
            domains.append(dom)
    return domains


def domain_blocked_by_keywords(domain: str) -> bool:
    d = domain.lower()
    return any(k in d for k in DOMAIN_KEYWORD_BLOCKLIST)


def prepare_domain_order(
    domains: list[str],
    excluded: frozenset[str],
    *,
    seed: int = SAMPLE_SEED,
) -> list[str]:
    psl = load_psl()
    kept: list[str] = []
    seen: set[str] = set()
    for dom in domains:
        rd = registrable_domain(f"https://{dom}/", psl) or dom
        if rd in seen:
            continue
        seen.add(rd)
        if is_excluded_domain(rd, excluded):
            continue
        if domain_blocked_by_keywords(rd):
            continue
        kept.append(rd)
    rng = random.Random(seed)
    rng.shuffle(kept)
    return kept


def json_ld_types(html: str) -> set[str]:
    soup = BeautifulSoup(html, "lxml")
    types: set[str] = set()
    for node in parse_json_ld(soup):
        t = node.get("@type")
        if isinstance(t, list):
            types.update(str(x) for x in t)
        elif t:
            types.add(str(t))
    return types


def classify_url(url: str, *, ld_types: set[str] | None = None) -> str | None:
    path = urlparse(url).path or "/"
    ld = ld_types or set()
    ld_lower = {t.lower() for t in ld}
    if "product" in ld_lower:
        return "product"
    if "collectionpage" in ld_lower or "itemlist" in ld_lower:
        return "collection"
    if _PRODUCT.search(path):
        return "product"
    if "/collections/" in path.lower():
        return "collection"
    if path in ("/", "") or _PRICING_PATH.match(path):
        return "landing"
    if _FORUM.search(path):
        return "forum"
    if _LISTING.search(path):
        return "listing"
    if _is_article(path):
        return "article"
    if _SERVICE.search(path):
        return "service"
    return None


def resolve_page_type(url: str, html: str, url_type: str | None) -> str | None:
    """URL rules first; JSON-LD only after fetch when URL rules do not decide."""
    if url_type:
        return url_type
    return classify_url(url, ld_types=json_ld_types(html))


def _response_final_url(response: httpx.Response, fallback: str) -> str:
    try:
        candidate = str(response.url)
    except RuntimeError:
        return fallback
    return candidate if "://" in candidate else fallback


def discover_urls_for_domain(
    domain: str,
    html_pages: dict[str, str],
    links: dict[str, list[str]],
    *,
    psl,
) -> list[tuple[str, str | None]]:
    """Return (url, url_page_type|None) in fixed order. JSON-LD applied after fetch."""
    del html_pages  # classification of unmatched URLs happens post-fetch
    out: list[tuple[str, str | None]] = []
    seen: set[str] = set()

    def add(url: str, ptype: str | None) -> None:
        nu = normalize_url(url)
        if nu in seen:
            return
        seen.add(nu)
        out.append((nu, ptype))

    for sm_url in sorted(links.get("sitemap", [])):
        if registrable_domain(sm_url, psl) != domain:
            continue
        add(sm_url, classify_url(sm_url))

    home = f"https://{domain}/"
    add(home, "landing")
    for link in links.get(home, []):
        if not _PRICING_PATH.match(urlparse(link).path or ""):
            continue
        if registrable_domain(link, psl) != domain:
            continue
        add(link, "landing")

    for link in sorted(links.get("all", [])):
        p = urlparse(link)
        if registrable_domain(link, psl) != domain:
            continue
        if _BAD_EXT.search(p.path or ""):
            continue
        pt = classify_url(link)
        if pt:
            add(link, pt)
    return out


def quotas_met_with_cap(
    passed: list[Candidate],
    *,
    quotas: dict[str, int] | None = None,
    max_per_domain: int = MAX_PAGES_PER_DOMAIN,
) -> bool:
    """True when select_pages can fill every quota under the per-domain cap."""
    _, shortfall = select_pages(
        passed,
        quotas=quotas or QUOTAS,
        seed=SAMPLE_SEED,
        max_per_domain=max_per_domain,
    )
    return not shortfall


def select_pages(
    passed: list[Candidate],
    *,
    quotas: dict[str, int] | None = None,
    seed: int = SAMPLE_SEED,
    max_per_domain: int = MAX_PAGES_PER_DOMAIN,
) -> tuple[list[dict], dict[str, int]]:
    quotas = dict(quotas or QUOTAS)
    by_type: dict[str, list[Candidate]] = {k: [] for k in quotas}
    for c in passed:
        if c.page_type in by_type:
            by_type[c.page_type].append(c)
    rng = random.Random(seed)
    chosen: list[dict] = []
    domain_counts: Counter[str] = Counter()
    filled = {k: 0 for k in quotas}
    for ptype, need in quotas.items():
        pool = list(by_type.get(ptype, []))
        rng.shuffle(pool)
        for cand in pool:
            if filled[ptype] >= need:
                break
            if domain_counts[cand.domain] >= max_per_domain:
                continue
            pid = f"final-{len(chosen):04d}"
            chosen.append(
                {
                    "id": pid,
                    "url": cand.url,
                    "page_type": ptype,
                    "domain": cand.domain,
                }
            )
            domain_counts[cand.domain] += 1
            filled[ptype] += 1
    shortfall = {k: quotas[k] - filled[k] for k in quotas if filled[k] < quotas[k]}
    return chosen, shortfall


def _sitemap_locs(
    client: httpx.Client,
    domain: str,
    robots_cache: dict,
    domain_locks: dict,
    domain_last: dict,
    domain_meta: threading.Lock,
) -> list[str]:
    base = f"https://{domain}"
    sm_urls: list[str] = []
    try:
        wait_domain(domain, domain_locks, domain_last, domain_meta)
        r = client.get(f"{base}/robots.txt", timeout=15.0)
        if r.status_code < 400:
            for line in r.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    sm_urls.append(line.split(":", 1)[1].strip())
    except httpx.HTTPError:
        return []
    locs: list[str] = []
    for sm in sm_urls[:3]:
        if not robots_ok(client, sm, robots_cache):
            continue
        try:
            wait_domain(domain, domain_locks, domain_last, domain_meta)
            sr = client.get(sm, timeout=20.0)
            if sr.status_code == 200:
                locs.extend(re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sr.text, flags=re.I))
        except httpx.HTTPError:
            continue
    psl = load_psl()
    return sorted({normalize_url(u) for u in locs if registrable_domain(u, psl) == domain})[:100]


def _process_domain_offline(
    domain: str,
    handler: HttpHandler,
    excluded: frozenset[str],
    psl,
) -> tuple[list[Candidate], list[dict]]:
    passed: list[Candidate] = []
    skipped: list[dict] = []
    html_pages: dict[str, str] = {}
    link_map: dict[str, list[str]] = {"sitemap": [], "all": []}
    home = f"https://{domain}/"

    def log_skip(url: str, reason: str, page_type: str | None = None) -> None:
        skipped.append({"url": url, "domain": domain, "page_type": page_type, "reason": reason})

    try:
        r = handler("GET", home)
        html_pages[home] = r.text
        link_map[home] = _extract_links(r.text, home)
        link_map["all"].extend(link_map[home])
        link_map["sitemap"] = link_map.get("sitemap", [])
    except Exception as exc:  # noqa: BLE001
        log_skip(home, f"error:{type(exc).__name__}")
        return passed, skipped

    for url, url_type in discover_urls_for_domain(domain, html_pages, link_map, psl=psl):
        try:
            r = handler("GET", url)
        except Exception as exc:  # noqa: BLE001
            log_skip(url, f"error:{type(exc).__name__}", url_type)
            continue
        final = normalize_url(_response_final_url(r, url))
        ptype = resolve_page_type(final, r.text, url_type)
        if ptype is None:
            log_skip(final, "unclassified", None)
            continue
        final_domain = domain_for_url(final, psl)
        ok, reason = validate_fetched(
            url=final,
            status=r.status_code,
            content_type=r.headers.get("content-type", "text/html"),
            html=r.text,
            excluded=excluded,
            robots_ok=True,
            psl=psl,
            content_language=r.headers.get("content-language"),
        )
        if ok:
            passed.append(Candidate(url=final, page_type=ptype, domain=final_domain))
        else:
            log_skip(final, reason, ptype)
    return passed, skipped


def cap_candidates(domain: str, candidates: list[tuple[str, str | None]]) -> list[tuple[str, str | None]]:
    """A site can list thousands of sitemap URLs; try a fixed random few, chosen before any fetch."""
    shuffled = list(candidates)
    random.Random(f"{SAMPLE_SEED}:{domain}").shuffle(shuffled)
    return shuffled[:MAX_CANDIDATES_PER_DOMAIN]


def _process_domain_live(
    domain: str,
    client: httpx.Client,
    excluded: frozenset[str],
    psl,
    domain_locks: dict,
    domain_last: dict,
    domain_meta: threading.Lock,
    robots_cache: dict,
) -> tuple[list[Candidate], list[dict]]:
    passed: list[Candidate] = []
    skipped: list[dict] = []
    html_pages: dict[str, str] = {}
    link_map: dict[str, list[str]] = {"sitemap": [], "all": []}

    def log_skip(url: str, reason: str, page_type: str | None = None) -> None:
        skipped.append({"url": url, "domain": domain, "page_type": page_type, "reason": reason})

    home = f"https://{domain}/"
    wait_domain(domain, domain_locks, domain_last, domain_meta)
    if not robots_ok(client, home, robots_cache):
        log_skip(home, "robots_disallow", "landing")
        return passed, skipped
    try:
        r = client.get(home)
        html_pages[home] = r.text
        link_map[home] = _extract_links(r.text, home)
        link_map["all"].extend(link_map[home])
        link_map["sitemap"] = _sitemap_locs(
            client, domain, robots_cache, domain_locks, domain_last, domain_meta
        )
    except httpx.HTTPError as exc:
        log_skip(home, f"error:{type(exc).__name__[:40]}", "landing")
        return passed, skipped

    started = time.monotonic()
    for url, url_type in cap_candidates(domain, discover_urls_for_domain(domain, html_pages, link_map, psl=psl)):
        if time.monotonic() - started > DOMAIN_DEADLINE_SECONDS:
            log_skip(url, "domain_deadline", url_type)
            break
        wait_domain(domain, domain_locks, domain_last, domain_meta)
        if not robots_ok(client, url, robots_cache):
            log_skip(url, "robots_disallow", url_type)
            continue
        try:
            r = client.get(url)
        except httpx.HTTPError as exc:
            log_skip(url, f"error:{type(exc).__name__[:40]}", url_type)
            continue
        final = normalize_url(str(r.url))
        ptype = resolve_page_type(final, r.text, url_type)
        if ptype is None:
            log_skip(final, "unclassified", None)
            continue
        final_domain = domain_for_url(final, psl)
        ok, reason = validate_fetched(
            url=final,
            status=r.status_code,
            content_type=r.headers.get("content-type", ""),
            html=r.text,
            excluded=excluded,
            robots_ok=True,
            psl=psl,
            content_language=r.headers.get("content-language"),
        )
        if ok:
            passed.append(Candidate(url=final, page_type=ptype, domain=final_domain))
        else:
            log_skip(final, reason, ptype)
    return passed, skipped


def merge_domain_results_in_order(
    domain_batch: list[str],
    results_by_domain: dict[str, tuple[list[Candidate], list[dict]]],
) -> tuple[list[Candidate], list[dict]]:
    """Apply acceptance results in fixed shuffled domain order (not completion order)."""
    passed: list[Candidate] = []
    skipped: list[dict] = []
    for dom in domain_batch:
        got, sk = results_by_domain.get(dom, ([], []))
        passed.extend(got)
        skipped.extend(sk)
    return passed, skipped


def sample_from_tranco(
    *,
    tranco_path: Path,
    list_id: str,
    excluded: frozenset[str],
    handler: HttpHandler | None = None,
    max_domains: int = MAX_DOMAINS_TRIED,
    workers: int = 16,
    ca_bundle: Path | None = None,
    batch_size: int | None = None,
) -> tuple[list[dict], list[dict], dict]:
    """Discover and select pages. Returns (pages, skipped_rows, report)."""
    raw_domains = load_tranco_domains(tranco_path)
    domain_order = prepare_domain_order(raw_domains, excluded)[:max_domains]
    psl = load_psl()
    passed: list[Candidate] = []
    skipped: list[dict] = []
    domains_tried = 0
    size = batch_size or min(workers, DOMAIN_BATCH_SIZE)

    if handler is not None:
        for i in range(0, len(domain_order), size):
            batch = domain_order[i : i + size]
            results_by_domain: dict[str, tuple[list[Candidate], list[dict]]] = {}
            for domain in batch:
                results_by_domain[domain] = _process_domain_offline(domain, handler, excluded, psl)
            got, sk = merge_domain_results_in_order(batch, results_by_domain)
            passed.extend(got)
            skipped.extend(sk)
            domains_tried += len(batch)
            if quotas_met_with_cap(passed):
                break
    else:
        verify = build_ca_bundle(ca_bundle)
        domain_locks: dict[str, threading.Lock] = {}
        domain_last: dict[str, float] = {}
        domain_meta = threading.Lock()
        robots_cache: dict = {}
        with httpx.Client(
            follow_redirects=True,
            timeout=20.0,
            limits=httpx.Limits(max_connections=256, max_keepalive_connections=64),
            headers=HEADERS,
            verify=verify,
        ) as client:
            for i in range(0, len(domain_order), size):
                batch = domain_order[i : i + size]
                results_by_domain = {}
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futs = {
                        pool.submit(
                            _process_domain_live,
                            dom,
                            client,
                            excluded,
                            psl,
                            domain_locks,
                            domain_last,
                            domain_meta,
                            robots_cache,
                        ): dom
                        for dom in batch
                    }
                    # Wait for the whole batch, then merge in fixed domain order.
                    for fut, dom in futs.items():
                        try:
                            results_by_domain[dom] = fut.result()
                        except Exception as exc:  # one broken site must not end the run
                            results_by_domain[dom] = (
                                [],
                                [{"url": f"https://{dom}/", "domain": dom, "page_type": None,
                                  "reason": f"error:{type(exc).__name__[:40]}"}],
                            )
                got, sk = merge_domain_results_in_order(batch, results_by_domain)
                passed.extend(got)
                skipped.extend(sk)
                domains_tried += len(batch)
                counts = Counter(c.page_type for c in passed)
                print(f"domains={domains_tried} passed={len(passed)} {dict(counts)}", flush=True)
                if quotas_met_with_cap(passed):
                    break

    pages, shortfall = select_pages(passed)
    report = {
        "tranco_list_id": list_id,
        "tranco_csv": str(tranco_path.name),
        "domains_in_csv": len(raw_domains),
        "domains_tried": domains_tried,
        "candidates_passed": len(passed),
        "selected": len(pages),
        "quotas": QUOTAS,
        "shortfall": shortfall,
        "sample_seed": SAMPLE_SEED,
    }
    return pages, skipped, report

def _extract_links(html: str, base: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#"):
            continue
        out.append(urljoin(base, href))
    return out


def write_seed_list(pages: list[dict], path: Path, *, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sample_seed": SAMPLE_SEED,
        "max_pages_per_domain": MAX_PAGES_PER_DOMAIN,
        "quotas": QUOTAS,
        **meta,
        "pages": [{"id": p["id"], "url": p["url"], "page_type": p["page_type"]} for p in pages],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def append_skipped(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def read_list_id(path: Path) -> str:
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description="Tranco sample + fetch for P04 final pages")
    parser.add_argument("--inventory-csv", type=Path, required=True)
    parser.add_argument("--tranco", type=Path, default=DEFAULT_TRANCO)
    parser.add_argument("--list-id-file", type=Path, default=DEFAULT_LIST_ID)
    parser.add_argument("--seeds-out", type=Path, default=DEFAULT_SEEDS_OUT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--skipped", type=Path, default=DEFAULT_SKIPPED)
    parser.add_argument("--workers", type=int, default=128)
    parser.add_argument("--ca-bundle", type=Path, default=None)
    parser.add_argument(
        "--sample-only",
        action="store_true",
        help="Write seed list and reports only (requires pre-built handler data; for offline tests)",
    )
    parser.add_argument(
        "--fetch-only",
        action="store_true",
        help="Skip sampling; fetch existing --seeds-out",
    )
    args = parser.parse_args()
    excluded = build_excluded(args.inventory_csv)

    if not args.fetch_only:
        if not args.tranco.is_file():
            raise SystemExit(f"Missing Tranco CSV: {args.tranco} (download per PROTOCOL.md)")
        list_id = read_list_id(args.list_id_file)
        pages, skipped, report = sample_from_tranco(
            tranco_path=args.tranco,
            list_id=list_id,
            excluded=excluded,
            workers=args.workers,
            ca_bundle=args.ca_bundle,
        )
        write_seed_list(pages, args.seeds_out, meta={"tranco_list_id": list_id})
        append_skipped(args.skipped, skipped)
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "sample_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {args.seeds_out} ({len(pages)} pages); shortfall={report.get('shortfall')}")
        if args.sample_only:
            return

    from poc.final_collect import load_seed_pages

    manifest = args.manifest or (args.out / "manifest.jsonl")
    seed_pages = load_seed_pages(args.seeds_out)
    blocked = [p for p in seed_pages if is_excluded_domain(domain_for_url(p["url"]), excluded)]
    if blocked:
        raise SystemExit(f"Seed list contains {len(blocked)} excluded domain(s)")
    rows = collect(
        seed_pages,
        excluded=excluded,
        out_dir=args.out,
        manifest_path=manifest,
        workers=args.workers,
        ca_bundle=args.ca_bundle,
    )
    ok = sum(1 for r in rows if r.get("status") == "ok")
    print(f"Manifest {manifest}: {ok}/{len(seed_pages)} ok")


if __name__ == "__main__":
    main()
