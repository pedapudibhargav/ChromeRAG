"""Collect the human rating pages from approved sites only.

  discover  read robots.txt and sitemaps of approved sites, write candidate addresses
  collect   load only the addresses a safety check approved, in a real browser

Requests go only to the page's own site and its known content hosts, so advertising and
tracking hosts are never contacted. Pages are saved as loaded and are not cleaned, so every tool gets
the same input. A site that refuses is not retried.
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
import re
import subprocess
import time
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
SET_DIR = ROOT / "evaluations" / "2026-11-final" / "human_set"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
BROWSER = Path(__file__).with_name("human_set_browser.cjs")
SITE_DELAY_S = 5.0
RATE_LIMIT_WAIT_S = 120.0
CANDIDATES_PER_SITE = 12
MAX_SITEMAP_FILES = 4
MAX_SITEMAP_BYTES = 8_000_000
MIN_VISIBLE_WORDS = 80
# Content hosts these companies use for their own pages. Nothing else outside the site loads.
OWN_CONTENT_HOSTS = {
    "amazon.com": ["awsstatic.com", "amazonaws.com"],
    "microsoft.com": ["microsoft.com", "azureedge.net", "msecnd.net", "azure.net"],
    "google": ["gstatic.com", "googleapis.com"],
    "google.com": ["gstatic.com", "googleapis.com"],
    "google.dev": ["gstatic.com", "googleapis.com"],
    "github.com": ["githubassets.com", "githubusercontent.com"],
    "apple.com": ["cdn-apple.com"],
    "mozilla.org": ["mozilla.net"],
}
SKIP_PATH = re.compile(
    r"/(login|log-in|signin|sign-in|signup|sign-up|register|account|my-account|checkout|cart|basket|search|"
    r"careers?|jobs|tags?|users?|privacy|cookies?|terms|legal)(/|$|\?)|[?&]",
    re.I,
)
SKIP_FILE = re.compile(r"\.(pdf|zip|gz|xml|json|csv|xlsx?|docx?|pptx?|jpe?g|png|gif|svg|mp4|mp3)$", re.I)
OTHER_LOCALE = re.compile(r"^/(?!en(?:[-_][a-z]{2})?/)[a-z]{2}(?:[-_][a-z]{2})?(/|$)", re.I)
UNSAFE_TERMS = frozenset(
    """porn porno xxx nude nudity sex sexual sexually sexuality erotic escort std stds hiv syphilis gonorrhea chlamydia
    abortion miscarriage stillbirth rape assault suicide suicidal self-harm selfharm overdose
    gore graphic massacre murder homicide terrorism terrorist genocide torture beheading
    casino gambling betting poker lottery weapon weapons firearm firearms ammunition
    crypto cryptocurrency torrent warez""".split()
)
TEXT_TERM_HITS_MAX = 2
WALL = re.compile(r"sign in|log in|accept (all )?cookies|verify you are human|access denied|enable javascript", re.I)


def load_sites(path: Path = SET_DIR / "sites.json") -> list[dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    sites = []
    for group, entries in doc["groups"].items():
        for entry in entries:
            host, _, prefix = entry.partition("/")
            sites.append(
                {
                    "site": entry,
                    "host": host,
                    "prefix": f"/{prefix}" if prefix else "",
                    "group": group,
                    "scripts": group not in doc["scripts_off_groups"],
                }
            )
    return sites


def on_site(url: str, host: str) -> bool:
    found = (urlparse(url).hostname or "").lower()
    return found == host or found.endswith("." + host)


def url_terms(url: str) -> set[str]:
    return set(re.findall(r"[a-z]+(?:-[a-z]+)?", urlparse(url).path.lower())) & UNSAFE_TERMS


def url_allowed(url: str, site: dict) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and on_site(url, site["host"])
        and parsed.path.startswith(site["prefix"])
        and parsed.path.rstrip("/") != site["prefix"].rstrip("/")
        and not SKIP_PATH.search(url)
        and not SKIP_FILE.search(parsed.path)
        and not OTHER_LOCALE.match(parsed.path)
        and not url_terms(url)
    )


def gate_outcome(status: int, final_host: str, site: dict) -> str:
    """What a robots.txt reply means. Only a passing reply leads to any further request.

    pass         read the rules and go on (a missing file means no rules were published)
    refused      the site said no; respect it and never retry
    rate_limited the site asked us to slow down; wait once, then treat as refused
    off_list     it sent us to a host we did not approve; stop
    failed       a fault, not a refusal; try once more in a later run
    """
    if final_host and not (final_host == site["host"] or final_host.endswith("." + site["host"])):
        return "off_list"
    if status in {200, 404, 410}:
        return "pass"
    if status == 429:
        return "rate_limited"
    if status in {401, 403, 418, 451} or 300 <= status < 400:
        return "refused"
    return "failed"


def _get(client: httpx.Client, url: str, site: dict) -> httpx.Response | None:
    """One request, only ever to the approved site. Refusals are recorded by the caller."""
    if not on_site(url, site["host"]):
        return None
    time.sleep(SITE_DELAY_S)
    try:
        response = client.get(url)
    except httpx.HTTPError:
        return None
    if response.status_code != 200 or not on_site(str(response.url), site["host"]):
        return None
    return response


def _base_url(client: httpx.Client, site: dict) -> tuple[str, str, str]:
    """Return (base address, robots text, gate outcome), after at most one wait if asked to slow down."""
    bare = site["host"].count(".") >= 2
    base = f"https://{site['host']}" if bare else f"https://www.{site['host']}"
    outcome = "failed"
    for attempt in range(2):
        time.sleep(SITE_DELAY_S if attempt == 0 else RATE_LIMIT_WAIT_S)
        try:
            response = client.get(f"{base}/robots.txt")
        except httpx.HTTPError:
            return base, "", "failed"
        outcome = gate_outcome(response.status_code, (response.url.host or "").lower(), site)
        if outcome == "pass":
            return base, response.text if response.status_code == 200 else "", "pass"
        if outcome != "rate_limited":
            return base, "", outcome
    return base, "", "refused"


def _sitemap_urls(client: httpx.Client, sitemaps: list[str], site: dict, rng: random.Random) -> list[str]:
    found: list[str] = []
    queue = list(sitemaps)
    rng.shuffle(queue)
    reads = 0
    while queue and reads < MAX_SITEMAP_FILES:
        response = _get(client, queue.pop(0), site)
        reads += 1
        if response is None or len(response.content) > MAX_SITEMAP_BYTES:
            continue
        body = response.content
        if body[:2] == b"\x1f\x8b":
            try:
                body = gzip.decompress(body)
            except OSError:
                continue
        text = body[:MAX_SITEMAP_BYTES].decode("utf-8", errors="replace")
        locs = [x.strip() for x in re.findall(r"<loc>\s*(.*?)\s*</loc>", text)]
        if "<sitemapindex" in text:
            nested = [x for x in locs if on_site(x, site["host"])]
            rng.shuffle(nested)
            queue = nested + queue
        else:
            found.extend(locs)
    return found


def discover_site(client: httpx.Client, site: dict, rng: random.Random) -> dict:
    base, robots, outcome = _base_url(client, site)
    if outcome != "pass":
        return {**site, "status": f"gate_{outcome}", "candidates": []}
    parser = robotparser.RobotFileParser()
    parser.parse(robots.splitlines())
    urls = _sitemap_urls(client, parser.site_maps() or [f"{base}/sitemap.xml"], site, rng)
    source = "sitemap"
    if not [u for u in urls if url_allowed(u, site)] and parser.can_fetch("*", f"{base}{site['prefix']}/"):
        source = "start_page"
        page = _get(client, f"{base}{site['prefix']}/", site)
        urls = [urljoin(str(page.url), h) for h in re.findall(r'href="([^"#]+)"', page.text)] if page else []
    allowed = sorted({u for u in urls if url_allowed(u, site) and parser.can_fetch("*", u)})
    rng.shuffle(allowed)
    return {**site, "status": "ok" if allowed else "no_candidates", "source": source, "n_seen": len(urls),
            "candidates": allowed[:CANDIDATES_PER_SITE]}


def run_discover(args: argparse.Namespace) -> None:
    rng = random.Random(args.seed)
    out = args.out_dir / "candidates.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    verify = args.ca_bundle or True
    with httpx.Client(headers=HEADERS, verify=verify, timeout=30, follow_redirects=True) as client, out.open("a" if args.sites else "w") as f:
        for site in load_sites():
            if args.sites and site["site"] not in args.sites:
                continue
            row = discover_site(client, site, rng)
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(site["site"], row["status"], len(row["candidates"]), flush=True)


def allowed_hosts(site: dict) -> list[str]:
    parts = site["host"].split(".")
    own = ".".join(parts[-2:])
    return [own, *OWN_CONTENT_HOSTS.get(own, [])]


def page_problem(html: str, final_url: str, status: int, site: dict) -> str | None:
    """Mechanical checks on the loaded page, using no tool output."""
    from poc.final_page_filter import visible_text

    if status != 200:
        return f"status_{status}"
    if not on_site(final_url, site["host"]) or not url_allowed(final_url, site):
        return "left_allowed_pages"
    text = visible_text(html)
    words = re.findall(r"[a-z]+(?:-[a-z]+)?", text.lower())
    if len(words) < MIN_VISIBLE_WORDS:
        return "too_little_text"
    if len(words) < 200 and WALL.search(text):
        return "login_or_cookie_wall"
    if sum(w in UNSAFE_TERMS for w in words) > TEXT_TERM_HITS_MAX:
        return "unsafe_terms_in_text"
    return None


def load_page(url: str, site: dict) -> tuple[str, str, int, list[str]]:
    done = subprocess.run(
        ["node", str(BROWSER), url, ",".join(allowed_hosts(site)), "1" if site["scripts"] else "0", USER_AGENT],
        capture_output=True, text=True, timeout=120, check=False,
    )
    row = json.loads(done.stdout)
    if "error" in row:
        raise RuntimeError(row["error"])
    return row["html"], row["final_url"], row["status"], row["blocked_hosts"]


def run_collect(args: argparse.Namespace) -> None:
    approved = set(json.loads(args.approved.read_text(encoding="utf-8"))["approved"])
    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(x) for x in (args.out_dir / "candidates.jsonl").read_text().splitlines()]
    done = {}
    log_path = args.out_dir / "collect_log.jsonl"
    if log_path.exists():
        done = {json.loads(x)["url"]: json.loads(x) for x in log_path.read_text().splitlines()}
    n = sum("id" in r for r in done.values())
    with log_path.open("a") as log:
        for site in rows:
            kept = sum(r.get("site") == site["site"] and "id" in r for r in done.values())
            for url in site["candidates"]:
                if kept >= args.per_site or url not in approved or url in done:
                    continue
                time.sleep(SITE_DELAY_S)
                row = {"site": site["site"], "group": site["group"], "url": url}
                try:
                    # Scripts stay off unless the page has too little text without them.
                    html, final_url, status, blocked = load_page(url, {**site, "scripts": False})
                    problem = page_problem(html, final_url, status, site)
                    row["scripts_used"] = False
                    if problem == "too_little_text" and site["scripts"]:
                        time.sleep(SITE_DELAY_S)
                        html, final_url, status, blocked = load_page(url, site)
                        problem = page_problem(html, final_url, status, site)
                        row["scripts_used"] = True
                    row |= {"final_url": final_url, "status": status, "problem": problem, "blocked_hosts": blocked}
                except Exception as exc:  # noqa: BLE001
                    problem = type(exc).__name__
                    row["problem"] = problem
                if problem is None:
                    row["id"] = f"human-{n:04d}"
                    n += 1
                    kept += 1
                    (args.out_dir / f"{row['id']}.html").write_text(html, encoding="utf-8")
                log.write(json.dumps(row) + "\n")
                log.flush()
                print(site["site"], row.get("id") or row["problem"], flush=True)
                if str(problem) in {"status_401", "status_403", "status_429"}:
                    break


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("discover")
    d.add_argument("--out-dir", type=Path, required=True)
    d.add_argument("--seed", type=int, default=20261102)
    d.add_argument("--ca-bundle", default=None)
    d.add_argument("--sites", nargs="*", default=None, help="Only these sites; rows are added to the file")
    c = sub.add_parser("collect")
    c.add_argument("--out-dir", type=Path, required=True)
    c.add_argument("--approved", type=Path, required=True)
    c.add_argument("--per-site", type=int, default=3)
    args = p.parse_args()
    {"discover": run_discover, "collect": run_collect}[args.cmd](args)


if __name__ == "__main__":
    main()
