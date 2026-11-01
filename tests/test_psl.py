"""Tests for the pinned public suffix list parser."""

from __future__ import annotations

from poc.psl import load_psl, public_suffix, registrable_domain


def test_co_uk() -> None:
    psl = load_psl()
    assert public_suffix("bbc.co.uk", psl) == "co.uk"
    assert registrable_domain("https://www.bbc.co.uk/path", psl) == "bbc.co.uk"


def test_wildcard_ck() -> None:
    psl = load_psl()
    assert public_suffix("foo.ck", psl) == "foo.ck"
    assert registrable_domain("bar.foo.ck", psl) == "bar.foo.ck"


def test_exception_city_kawasaki() -> None:
    psl = load_psl()
    assert public_suffix("city.kawasaki.jp", psl) != "city.kawasaki.jp"
    assert registrable_domain("https://city.kawasaki.jp/", psl) == "city.kawasaki.jp"


def test_www_stripped_for_registrable() -> None:
    psl = load_psl()
    assert registrable_domain("https://www.example.com", psl) == "example.com"
    assert registrable_domain("example.com", psl) == "example.com"
