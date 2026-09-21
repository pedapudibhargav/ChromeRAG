"""Fetch HTML fixtures for POC benchmarks (not part of the chromerag library).

Uses public registries / sites. Optional SSL_EXTRA_CA env for local TLS interception.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

# Seed fixtures (expanded corpus lives in poc/corpus_urls.json).
TARGETS: list[dict[str, str]] = [
    {"id": "aws-ec2-pricing", "url": "https://aws.amazon.com/ec2/pricing/on-demand/", "category": "cloud_pricing_table"},
    {"id": "aws-s3-docs", "url": "https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html", "category": "cloud_docs"},
    {"id": "aws-lambda-pricing", "url": "https://aws.amazon.com/lambda/pricing/", "category": "cloud_pricing_table"},
    {"id": "aws-ec2-instance-types", "url": "https://aws.amazon.com/ec2/instance-types/", "category": "cloud_docs_tables"},
    {"id": "aws-ec2-home", "url": "https://aws.amazon.com/ec2/", "category": "cloud_product"},
    {"id": "aws-lambda-home", "url": "https://aws.amazon.com/lambda/", "category": "cloud_product"},
    {"id": "stripe-docs-home", "url": "https://docs.stripe.com/", "category": "api_docs"},
    {"id": "stripe-docs-payments", "url": "https://docs.stripe.com/payments", "category": "api_docs"},
    {"id": "twilio-docs", "url": "https://www.twilio.com/docs", "category": "api_docs"},
    {"id": "twilio-docs-sms", "url": "https://www.twilio.com/docs/sms", "category": "api_docs"},
    {"id": "nvidia-dgx", "url": "https://www.nvidia.com/en-us/data-center/dgx-platform/", "category": "hardware_marketing"},
    {"id": "nvidia-h100", "url": "https://www.nvidia.com/en-us/data-center/h100/", "category": "hardware_marketing"},
    {"id": "salesforce-product", "url": "https://www.salesforce.com/products/", "category": "saas_marketing"},
    {"id": "microsoft-azure-docs", "url": "https://learn.microsoft.com/en-us/azure/architecture/browse/", "category": "cloud_docs"},
    {"id": "microsoft-azure-overview", "url": "https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/overview", "category": "cloud_docs"},
    {"id": "cloudflare-workers", "url": "https://developers.cloudflare.com/workers/", "category": "api_docs"},
    {"id": "cloudflare-workers-get-started", "url": "https://developers.cloudflare.com/workers/get-started/guide/", "category": "api_docs"},
    {"id": "cloudflare-workers-routing", "url": "https://developers.cloudflare.com/workers/configuration/routing/", "category": "api_docs"},
    {"id": "github-docs-actions", "url": "https://docs.github.com/en/actions", "category": "api_docs"},
    {"id": "github-docs-actions-quickstart", "url": "https://docs.github.com/en/actions/quickstart", "category": "api_docs"},
    {"id": "github-docs-actions-about", "url": "https://docs.github.com/en/actions/learn-github-actions/understanding-github-actions", "category": "api_docs"},
    {"id": "digitalocean-docs", "url": "https://docs.digitalocean.com/", "category": "cloud_docs"},
    {"id": "hashicorp-terraform", "url": "https://developer.hashicorp.com/terraform/docs", "category": "api_docs"},
    {"id": "kubernetes-docs", "url": "https://kubernetes.io/docs/home/", "category": "api_docs"},
    {"id": "docker-docs", "url": "https://docs.docker.com/", "category": "api_docs"},
]


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _ssl_verify() -> str | bool:
    """Use system CAs; optionally append SSL_EXTRA_CA if set in the environment."""
    extra = os.environ.get("SSL_EXTRA_CA")
    system_candidates = [
        Path(os.environ["SSL_CERT_FILE"]) if os.environ.get("SSL_CERT_FILE") else None,
        Path("/etc/ssl/certs/ca-certificates.crt"),
        Path("/etc/ssl/cert.pem"),
    ]
    system = next((p for p in system_candidates if p and p.exists()), None)
    if extra and Path(extra).exists() and system:
        combined = Path(tempfile.gettempdir()) / "chromerag-ca-bundle.crt"
        combined.write_bytes(system.read_bytes() + b"\n" + Path(extra).read_bytes())
        return str(combined)
    if system:
        return str(system)
    return True


def sniff_signals(html: str) -> dict:
    return {
        "has_json_ld": bool(re.search(r"application/ld\+json", html, re.I)),
        "has_microdata": bool(re.search(r"\bitemscope\b", html, re.I)),
        "has_table": "<table" in html.lower(),
        "bytes": len(html.encode("utf-8", errors="ignore")),
    }


def slug_id(url: str, fallback: str) -> str:
    from urllib.parse import urlparse

    p = urlparse(url)
    host = (p.netloc or "site").lower().removeprefix("www.")
    host = re.sub(r"[^a-z0-9]+", "-", host).strip("-")
    path = re.sub(r"[^a-z0-9]+", "-", (p.path or "").lower()).strip("-")
    raw = f"{host}-{path}" if path else host
    raw = raw[:80].strip("-") or fallback
    return raw


def load_targets(corpus_path: Path | None = None) -> list[dict[str, str]]:
    path = corpus_path or (ROOT / "poc" / "corpus_urls.json")
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data.get("urls", data if isinstance(data, list) else [])
        out = []
        for i, row in enumerate(rows):
            if isinstance(row, str):
                out.append(
                    {
                        "id": slug_id(row, f"page-{i:03d}"),
                        "url": row,
                        "category": "corpus",
                    }
                )
            elif isinstance(row, dict) and row.get("url"):
                out.append(
                    {
                        "id": row.get("id") or slug_id(row["url"], f"page-{i:03d}"),
                        "url": row["url"],
                        "category": row.get("category", "corpus"),
                    }
                )
        # de-dupe by id
        seen: set[str] = set()
        unique = []
        for t in out:
            if t["id"] in seen:
                t = {**t, "id": f"{t['id']}-{len(seen)}"}
            seen.add(t["id"])
            unique.append(t)
        return unique
    return list(TARGETS)


def fetch_all(
    timeout: float = 45.0,
    *,
    corpus_path: Path | None = None,
    limit: int | None = None,
) -> list[dict]:
    targets = load_targets(corpus_path)
    if limit is not None:
        targets = targets[:limit]
    results: list[dict] = []
    verify = _ssl_verify()
    with httpx.Client(
        follow_redirects=True,
        timeout=timeout,
        headers=HEADERS,
        verify=verify,
    ) as client:
        for t in targets:
            entry = {**t, "ok": False, "error": None, "path": None, "signals": {}}
            try:
                r = client.get(t["url"])
                r.raise_for_status()
                html = r.text
                path = RAW / f"{t['id']}.html"
                path.write_text(html, encoding="utf-8")
                meta = {
                    "id": t["id"],
                    "url": str(r.url),
                    "requested_url": t["url"],
                    "category": t["category"],
                    "status_code": r.status_code,
                    "signals": sniff_signals(html),
                }
                (RAW / f"{t['id']}.meta.json").write_text(
                    json.dumps(meta, indent=2), encoding="utf-8"
                )
                entry.update(
                    ok=True,
                    path=str(path),
                    signals=meta["signals"],
                    final_url=str(r.url),
                )
                print(
                    f"OK  {t['id']}  jsonld={meta['signals']['has_json_ld']}  "
                    f"bytes={meta['signals']['bytes']}"
                )
            except Exception as exc:  # noqa: BLE001 — POC harness
                entry["error"] = str(exc)
                print(f"FAIL {t['id']}: {exc}")
            results.append(entry)
    summary_path = RAW / "_fetch_summary.json"
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    ok = sum(1 for r in results if r.get("ok"))
    print(f"\nFetched {ok}/{len(results)} pages → {RAW}")
    return results


if __name__ == "__main__":
    fetch_all()
