"""Unit tests for poc.human_set_collect; no network."""

from __future__ import annotations

from poc import human_set_collect as c


def _site(entry: str) -> dict:
    return next(s for s in c.load_sites() if s["site"] == entry)


def test_only_approved_pages_are_allowed():
    so = _site("stackoverflow.com/questions")
    assert so["scripts"] is False
    assert c.url_allowed("https://stackoverflow.com/questions/1/how-to-sort", so)
    assert not c.url_allowed("https://stackoverflow.com/users/1/x", so)
    assert not c.url_allowed("https://stackoverflow.com.evil.test/questions/1/x", so)
    assert not c.url_allowed("http://stackoverflow.com/questions/1/x", so)
    aws = _site("aws.amazon.com")
    assert aws["scripts"] is True
    assert c.url_allowed("https://aws.amazon.com/s3/pricing/", aws)
    assert not c.url_allowed("https://aws.amazon.com/de/s3/", aws)
    assert not c.url_allowed("https://aws.amazon.com/s3/?x=1", aws)


def test_sensitive_address_is_rejected():
    nhs = _site("nhs.uk")
    assert c.url_allowed("https://www.nhs.uk/conditions/asthma/", nhs)
    assert not c.url_allowed("https://www.nhs.uk/conditions/suicide/", nhs)


def test_no_news_or_left_out_sites():
    hosts = {s["host"] for s in c.load_sites()}
    assert not hosts & {"reuters.com", "bbc.com", "reddit.com", "discussions.apple.com"}


def test_gate_outcomes():
    nasa = _site("nasa.gov")
    assert c.gate_outcome(200, "www.nasa.gov", nasa) == "pass"
    assert c.gate_outcome(404, "www.nasa.gov", nasa) == "pass"
    assert c.gate_outcome(403, "www.nasa.gov", nasa) == "refused"
    assert c.gate_outcome(418, "www.nasa.gov", nasa) == "refused"
    assert c.gate_outcome(429, "www.nasa.gov", nasa) == "rate_limited"
    assert c.gate_outcome(200, "q.com", nasa) == "off_list"
    assert c.gate_outcome(503, "www.nasa.gov", nasa) == "failed"
