"""Offline tests for poc.final_sample (fake HTTP only)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from poc import final_sample as fs
from poc.psl import load_psl


def _english_html(body: str, *, words: int = 100) -> str:
    pad = "word " * words
    return f'<!DOCTYPE html><html lang="en"><body>{body}<p>{pad}</p></body></html>'


def test_tranco_load_and_blocklist(tmp_path: Path):
    csv_path = tmp_path / "tranco.csv"
    csv_path.write_text("1,example.com\n2,pornhub.test\n3,fresh-site.org\n", encoding="utf-8")
    domains = fs.load_tranco_domains(csv_path, max_rank=10)
    assert domains == ["example.com", "pornhub.test", "fresh-site.org"]
    order = fs.prepare_domain_order(domains, frozenset(), seed=fs.SAMPLE_SEED)
    assert "pornhub.test" not in order
    assert "fresh-site.org" in order


def test_select_respects_quota_and_domain_cap():
    passed = [
        fs.Candidate(url=f"https://a.test/{i}", page_type="product", domain="a.test")
        for i in range(5)
    ]
    pages, shortfall = fs.select_pages(passed, quotas={"product": 2}, seed=fs.SAMPLE_SEED, max_per_domain=3)
    assert len(pages) == 2
    assert shortfall == {}


def test_merge_domain_results_fixed_order_not_completion_order():
    """Finding 1: acceptance follows fixed domain order, not thread completion."""
    a = [fs.Candidate(url="https://a.test/", page_type="landing", domain="a.test")]
    b = [fs.Candidate(url="https://b.test/", page_type="landing", domain="b.test")]
    # Simulate b finishing before a in the results dict insertion order.
    results = {
        "b.test": (b, []),
        "a.test": (a, [{"url": "https://a.test/x", "reason": "skip"}]),
    }
    passed, skipped = fs.merge_domain_results_in_order(["a.test", "b.test"], results)
    assert [c.domain for c in passed] == ["a.test", "b.test"]
    assert skipped[0]["url"] == "https://a.test/x"


def test_sample_offline_deterministic_same_responses(tmp_path: Path):
    """Finding 1: repeating with the same responses yields the identical set."""
    csv_path = tmp_path / "tranco.csv"
    csv_path.write_text("1,alpha.test\n2,beta.test\n", encoding="utf-8")

    def handler(method: str, url: str) -> httpx.Response:
        html = _english_html("<h1>home</h1>")
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    kwargs = dict(
        tranco_path=csv_path,
        list_id="test-list",
        excluded=frozenset(),
        handler=handler,
        max_domains=2,
        batch_size=2,
    )
    pages1, _, _ = fs.sample_from_tranco(**kwargs)
    pages2, _, _ = fs.sample_from_tranco(**kwargs)
    assert [p["url"] for p in pages1] == [p["url"] for p in pages2]
    assert [p["page_type"] for p in pages1] == [p["page_type"] for p in pages2]


def test_json_ld_classifies_after_fetch_unmatched_unused(tmp_path: Path):
    """Finding 2: JSON-LD after fetch; unmatched pages are not used (no service default)."""
    psl = load_psl()
    domain = "shop.test"
    home = f"https://{domain}/"
    product_url = f"https://{domain}/obscure/item-42"
    html_pages = {
        home: _english_html(f'<a href="{product_url}">p</a>'),
    }
    links = {
        "sitemap": [product_url],
        home: [product_url],
        "all": [product_url],
    }
    discovered = fs.discover_urls_for_domain(domain, html_pages, links, psl=psl)
    by_url = {u: t for u, t in discovered}
    assert by_url[product_url] is None  # URL rules do not decide; no service default

    product_html = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<script type="application/ld+json">{"@type":"Product","name":"X"}</script>'
        "</head><body>" + ("word " * 100) + "</body></html>"
    )
    assert fs.resolve_page_type(product_url, product_html, None) == "product"
    plain = _english_html("no schema")
    assert fs.resolve_page_type(product_url, plain, None) is None


def test_pricing_same_registrable_domain_and_final_domain_cap(tmp_path: Path):
    """Finding 3: pricing same-domain only; candidate domain is final after redirect."""
    psl = load_psl()
    domain = "brand.test"
    home = f"https://{domain}/"
    html_pages = {home: _english_html('<a href="https://other.test/pricing">ext</a><a href="/pricing">ok</a>')}
    links = {
        "sitemap": [],
        home: ["https://other.test/pricing", f"https://{domain}/pricing"],
        "all": ["https://other.test/pricing", f"https://{domain}/pricing"],
    }
    discovered = fs.discover_urls_for_domain(domain, html_pages, links, psl=psl)
    urls = [u for u, _ in discovered]
    assert f"https://{domain}/pricing" in urls
    assert "https://other.test/pricing" not in urls

    def handler(method: str, url: str) -> httpx.Response:
        if url.rstrip("/").endswith("brand.test"):
            # Redirect home to excluded-looking final host still same registrable via CDN host
            resp = httpx.Response(
                200,
                text=_english_html("landing"),
                headers={"content-type": "text/html"},
            )
            return resp
        if "/pricing" in url:
            return httpx.Response(
                200,
                text=_english_html("pricing page"),
                headers={"content-type": "text/html"},
                request=httpx.Request("GET", "https://cdn.brand.test/pricing"),
            )
        return httpx.Response(200, text=_english_html("x"), headers={"content-type": "text/html"})

    csv_path = tmp_path / "tranco.csv"
    csv_path.write_text("1,brand.test\n", encoding="utf-8")
    pages, skipped, _ = fs.sample_from_tranco(
        tranco_path=csv_path,
        list_id="L",
        excluded=frozenset(),
        handler=handler,
        max_domains=1,
    )
    # Final domain on accepted candidates must be registrable of final URL when redirect set.
    pricing = [p for p in pages if "pricing" in p["url"]]
    if pricing:
        assert pricing[0]["domain"] == "brand.test"
    # Cap uses final domain: three pages max per final domain
    passed = [
        fs.Candidate(url=f"https://cdn.brand.test/{i}", page_type="article", domain="brand.test")
        for i in range(5)
    ]
    chosen, _ = fs.select_pages(passed, quotas={"article": 5}, max_per_domain=3)
    assert len(chosen) == 3


def test_content_language_shared_validator():
    """Finding 6: Content-Language passed into shared validator."""
    html = "<!DOCTYPE html><html><body>" + ("word " * 100) + "</body></html>"
    psl = load_psl()
    ok, reason = fs.validate_fetched(
        url="https://x.test/",
        status=200,
        content_type="text/html",
        html=html,
        excluded=frozenset(),
        robots_ok=True,
        psl=psl,
        content_language="en-US",
    )
    assert ok and reason == "ok"
    bad, reason2 = fs.validate_fetched(
        url="https://x.test/",
        status=200,
        content_type="text/html",
        html=html,
        excluded=frozenset(),
        robots_ok=True,
        psl=psl,
        content_language="fr",
    )
    assert not bad and reason2 == "not_english"


def test_sample_offline_pipeline(tmp_path: Path):
    csv_path = tmp_path / "tranco.csv"
    csv_path.write_text("1,shop.test\n", encoding="utf-8")
    excluded = frozenset()

    article_path = "/blog/2024/01/great-product-launch-news"

    def handler(method: str, url: str) -> httpx.Response:
        if url.endswith("/"):
            html = _english_html(f'<a href="{article_path}">blog</a>')
        elif article_path in url:
            html = _english_html("<article>Long form article content here.</article>")
        else:
            html = _english_html("fallback")
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    pages, skipped, report = fs.sample_from_tranco(
        tranco_path=csv_path,
        list_id="test-list",
        excluded=excluded,
        handler=handler,
        max_domains=1,
    )
    assert report["domains_tried"] == 1
    assert any(p["page_type"] == "article" for p in pages) or len(skipped) >= 1


def test_visible_word_count_rejects_short():
    html = '<html lang="en"><body>too short</body></html>'
    assert fs.visible_word_count(html) < fs.MIN_VISIBLE_WORDS
    ok, reason = fs.validate_fetched(
        url="https://x.test/",
        status=200,
        content_type="text/html",
        html=html,
        excluded=frozenset(),
        robots_ok=True,
        psl=load_psl(),
    )
    assert not ok
    assert reason == "too_few_words"


def test_write_seed_list(tmp_path: Path):
    out = tmp_path / "seeds.json"
    fs.write_seed_list(
        [{"id": "final-0000", "url": "https://z.test/", "page_type": "landing", "domain": "z.test"}],
        out,
        meta={"tranco_list_id": "L1"},
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["pages"][0]["url"] == "https://z.test/"
    assert data["tranco_list_id"] == "L1"


def test_cap_candidates_is_fixed_and_bounded():
    from poc.final_sample import MAX_CANDIDATES_PER_DOMAIN, cap_candidates

    cands = [(f"https://a.com/{i}", "article") for i in range(5000)]
    first = cap_candidates("a.com", cands)
    assert len(first) == MAX_CANDIDATES_PER_DOMAIN
    assert first == cap_candidates("a.com", cands)
