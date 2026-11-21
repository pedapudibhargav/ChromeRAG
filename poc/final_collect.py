"""Fetch locked evaluation pages into data/final/ with manifest (resumable, concurrent).

Prefer `python -m poc.final_sample` (Tranco sampling + fetch). This module fetches a
frozen `seed_page_list.json` only and owns the shared page-acceptance validator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from poc.fetch_pages import HEADERS, sniff_signals
from poc.final_domains import load_inventory_excluded_domains, load_wcxb_tree_domains, merged_excluded_domains
from poc.psl import load_psl, registrable_domain

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "final"
DEFAULT_MANIFEST = DEFAULT_OUT / "manifest.jsonl"
DEFAULT_WORKERS = 16
DOMAIN_DELAY_S = 1.0
WCXB_ROOT = ROOT / "data" / "wcxb"

SAMPLE_SEED = 20261101
MAX_PAGES_PER_DOMAIN = 3
MIN_VISIBLE_WORDS = 80


def normalize_url(url: str) -> str:
    """Lowercase host, strip www/fragment/trailing slash; keep query string."""
    p = urlparse(url.strip())
    host = (p.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = p.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    query = f"?{p.query}" if p.query else ""
    return f"{p.scheme.lower()}://{host}{path}{query}"


def visible_word_count(html: str) -> int:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return len(re.findall(r"\w+", text))


def is_english_page(html: str, content_language: str | None) -> bool:
    soup = BeautifulSoup(html, "lxml")
    html_tag = soup.find("html")
    lang = (html_tag.get("lang") if html_tag else "") or ""
    lang = str(lang).strip().lower()
    if lang:
        return lang.startswith("en")
    if content_language:
        first = content_language.split(",")[0].strip().lower()
        return first.startswith("en")
    return False


def validate_fetched(
    *,
    url: str,
    status: int,
    content_type: str,
    html: str,
    excluded: frozenset[str],
    robots_ok: bool,
    psl,
    content_language: str | None = None,
) -> tuple[bool, str]:
    """Shared acceptance rules for sampling and collection (PROTOCOL page acceptance)."""
    if not robots_ok:
        return False, "robots_disallow"
    final_domain = domain_for_url(url, psl)
    if is_excluded_domain(final_domain, excluded):
        return False, "excluded_domain"
    if status < 200 or status >= 300:
        return False, f"http_{status}"
    if "html" not in (content_type or "").lower():
        return False, "not_html"
    if not is_english_page(html, content_language):
        return False, "not_english"
    if visible_word_count(html) < MIN_VISIBLE_WORDS:
        return False, "too_few_words"
    return True, "ok"

def load_seed_pages(path: Path) -> list[dict]:
    """Load {"pages": [{"id", "url", "page_type"}, ...]} from seed_page_list.json."""
    data = json.loads(path.read_text(encoding="utf-8"))
    pages = data.get("pages", [])
    out: list[dict] = []
    for i, row in enumerate(pages):
        if not isinstance(row, dict) or not row.get("url"):
            continue
        url = str(row["url"])
        out.append(
            {
                "id": str(row.get("id") or f"final-{i:04d}"),
                "url": url,
                "page_type": str(row.get("page_type") or "unknown"),
            }
        )
    return out


def load_manifest(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    rows: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        pid = row.get("id") or normalize_url(str(row.get("url", "")))
        rows[str(pid)] = row
    return rows


def append_manifest(path: Path, row: dict, lock: threading.Lock) -> None:
    with lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def build_ca_bundle(extra_pem: Path | None) -> str | bool:
    if extra_pem is None or not extra_pem.exists():
        return True
    system_candidates = [
        Path("/etc/ssl/certs/ca-certificates.crt"),
        Path("/etc/ssl/cert.pem"),
    ]
    system = next((p for p in system_candidates if p.exists()), None)
    if system is None:
        return str(extra_pem)
    fd, name = tempfile.mkstemp(prefix="final-collect-ca-", suffix=".crt")
    with os.fdopen(fd, "wb") as fh:
        fh.write(system.read_bytes() + b"\n" + extra_pem.read_bytes())
    return name


def _domain_locks() -> tuple[dict[str, threading.Lock], dict[str, float], threading.Lock]:
    return {}, {}, threading.Lock()


def _wait_domain(domain: str, locks: dict[str, threading.Lock], last: dict[str, float], meta: threading.Lock) -> None:
    with meta:
        if domain not in locks:
            locks[domain] = threading.Lock()
        lock = locks[domain]
    with lock:
        now = time.monotonic()
        gap = now - last.get(domain, 0.0)
        if gap < DOMAIN_DELAY_S:
            time.sleep(DOMAIN_DELAY_S - gap)
        last[domain] = time.monotonic()


def _robots_ok(client: httpx.Client, url: str, cache: dict[str, robotparser.RobotFileParser | None]) -> bool:
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in cache:
        rp = robotparser.RobotFileParser()
        try:
            r = client.get(f"{base}/robots.txt", timeout=10.0)
            if r.status_code >= 400:
                cache[base] = None
            else:
                rp.parse(r.text.splitlines())
                cache[base] = rp
        except httpx.HTTPError:
            cache[base] = None
    rp = cache[base]
    if rp is None:
        return True
    return rp.can_fetch(HEADERS["User-Agent"], url)


def domain_for_url(url: str, psl=None) -> str:
    return registrable_domain(url, psl or load_psl())


def is_excluded_domain(domain: str, excluded: frozenset[str]) -> bool:
    return domain.lower() in excluded


def fetch_one(
    page: dict,
    *,
    client: httpx.Client,
    excluded: frozenset[str],
    out_dir: Path,
    robots_cache: dict[str, robotparser.RobotFileParser | None],
    domain_locks: dict[str, threading.Lock],
    domain_last: dict[str, float],
    domain_meta: threading.Lock,
    psl,
) -> dict:
    url = page["url"]
    pid = page["id"]
    domain = domain_for_url(url, psl)
    ts = datetime.now(UTC).isoformat()

    if is_excluded_domain(domain, excluded):
        return {
            "id": pid,
            "url": url,
            "domain": domain,
            "page_type": page.get("page_type"),
            "timestamp": ts,
            "status": "excluded_domain",
            "sha256": "",
        }

    _wait_domain(domain, domain_locks, domain_last, domain_meta)
    if not _robots_ok(client, url, robots_cache):
        return {
            "id": pid,
            "url": url,
            "domain": domain,
            "page_type": page.get("page_type"),
            "timestamp": ts,
            "status": "robots_disallow",
            "sha256": "",
        }

    try:
        r = client.get(url)
        final = str(r.url)
        final_domain = domain_for_url(final, psl)
        if is_excluded_domain(final_domain, excluded):
            return {
                "id": pid,
                "url": final,
                "domain": final_domain,
                "page_type": page.get("page_type"),
                "timestamp": ts,
                "status": "excluded_redirect",
                "sha256": "",
            }
        html = r.text
        ok, reason = validate_fetched(
            url=final,
            status=r.status_code,
            content_type=r.headers.get("content-type", ""),
            html=html,
            excluded=excluded,
            robots_ok=True,
            psl=psl,
            content_language=r.headers.get("content-language"),
        )
        if not ok:
            return {
                "id": pid,
                "url": final,
                "domain": final_domain,
                "page_type": page.get("page_type"),
                "timestamp": ts,
                "status": reason,
                "sha256": "",
            }
        digest = hashlib.sha256(html.encode("utf-8", errors="replace")).hexdigest()
        out_dir.mkdir(parents=True, exist_ok=True)
        html_path = out_dir / f"{pid}.html"
        html_path.write_text(html, encoding="utf-8")
        meta = {
            "id": pid,
            "url": final,
            "requested_url": url,
            "domain": final_domain,
            "page_type": page.get("page_type"),
            "timestamp": ts,
            "status": "ok",
            "sha256": digest,
            "signals": sniff_signals(html),
        }
        (out_dir / f"{pid}.meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        return meta
    except httpx.HTTPError as exc:
        return {
            "id": pid,
            "url": url,
            "domain": domain,
            "page_type": page.get("page_type"),
            "timestamp": ts,
            "status": "error",
            "sha256": "",
            "error": str(exc)[:200],
        }


def collect(
    pages: list[dict],
    *,
    excluded: frozenset[str],
    out_dir: Path = DEFAULT_OUT,
    manifest_path: Path = DEFAULT_MANIFEST,
    workers: int = DEFAULT_WORKERS,
    ca_bundle: Path | None = None,
    skip_ok: bool = True,
) -> list[dict]:
    existing = load_manifest(manifest_path)
    todo = []
    for p in pages:
        prev = existing.get(p["id"])
        if skip_ok and prev and prev.get("status") == "ok":
            continue
        todo.append(p)

    if not todo:
        return list(existing.values())

    verify = build_ca_bundle(ca_bundle)
    manifest_lock = threading.Lock()
    domain_locks, domain_last, domain_meta = _domain_locks()
    robots_cache: dict[str, robotparser.RobotFileParser | None] = {}
    psl = load_psl()
    results: list[dict] = list(existing.values())

    with httpx.Client(
        follow_redirects=True,
        timeout=45.0,
        headers=HEADERS,
        verify=verify,
    ) as client:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {
                pool.submit(
                    fetch_one,
                    page,
                    client=client,
                    excluded=excluded,
                    out_dir=out_dir,
                    robots_cache=robots_cache,
                    domain_locks=domain_locks,
                    domain_last=domain_last,
                    domain_meta=domain_meta,
                    psl=psl,
                ): page
                for page in todo
            }
            for fut in as_completed(futs):
                row = fut.result()
                append_manifest(manifest_path, row, manifest_lock)
                existing[row["id"]] = row
                results = list(existing.values())
    return results


def build_excluded(inventory_csv: Path, *, include_wcxb: bool = True) -> frozenset[str]:
    inv = load_inventory_excluded_domains(inventory_csv)
    wcxb = load_wcxb_tree_domains(WCXB_ROOT) if include_wcxb else frozenset()
    return merged_excluded_domains(inv, wcxb)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch P04 final evaluation pages (frozen seed list)")
    parser.add_argument("--seeds", type=Path, required=True, help="seed_page_list.json")
    parser.add_argument("--inventory-csv", type=Path, required=True, help="Author-held inventory.csv")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--ca-bundle", type=Path, default=None, help="Extra PEM merged with system CAs")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate seeds and exclusions only; no HTTP",
    )
    args = parser.parse_args()
    manifest = args.manifest or (args.out / "manifest.jsonl")
    pages = load_seed_pages(args.seeds)
    excluded = build_excluded(args.inventory_csv)
    blocked = [p for p in pages if is_excluded_domain(domain_for_url(p["url"]), excluded)]
    if blocked:
        names = ", ".join(sorted({domain_for_url(p["url"]) for p in blocked})[:5])
        raise SystemExit(f"Seed list contains {len(blocked)} excluded domain(s), e.g. {names}")
    if args.dry_run:
        print(f"OK {len(pages)} pages, {len(excluded)} excluded domains loaded")
        return
    rows = collect(
        pages,
        excluded=excluded,
        out_dir=args.out,
        manifest_path=manifest,
        workers=args.workers,
        ca_bundle=args.ca_bundle,
    )
    ok = sum(1 for r in rows if r.get("status") == "ok")
    print(f"Manifest {manifest}: {ok}/{len(pages)} ok ({len(rows)} rows total)")


if __name__ == "__main__":
    main()
