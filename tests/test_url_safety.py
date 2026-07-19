"""SSRF guard: only public http(s) hosts may be fetched.

IP-literal hosts resolve without any real DNS query, so these stay
network-free like the rest of the suite.
"""

from types import SimpleNamespace

import pytest

import app.services.scraper as scraper
from app.services.scraper.url_safety import UnsafeURLError, assert_public_http_url, normalize_url


def test_normalize_adds_scheme_to_bare_domain():
    assert normalize_url("acme.com") == "https://acme.com"


def test_normalize_leaves_existing_scheme():
    assert normalize_url("http://acme.com") == "http://acme.com"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint
        "http://10.0.0.5/",
        "http://172.16.0.1/",
        "http://192.168.1.1/",
        "http://[::1]/",
        "http://0.0.0.0/",
    ],
)
def test_blocks_private_and_loopback_hosts(url):
    with pytest.raises(UnsafeURLError):
        assert_public_http_url(url)


@pytest.mark.parametrize("url", ["ftp://8.8.8.8/", "file:///etc/passwd", "gopher://8.8.8.8/"])
def test_blocks_non_http_schemes(url):
    with pytest.raises(UnsafeURLError):
        assert_public_http_url(url)


def test_allows_public_ip_literal():
    assert_public_http_url("http://8.8.8.8/") is None


async def test_scrape_company_refuses_unsafe_url(monkeypatch):
    called = {"fetch": False}

    async def fake_fetch_site(url, *, max_pages):
        called["fetch"] = True
        return []

    monkeypatch.setattr(scraper, "fetch_site", fake_fetch_site)
    monkeypatch.setattr(
        scraper, "get_settings", lambda: SimpleNamespace(scrape_max_pages=5, scrape_tier2="off")
    )

    result = await scraper.scrape_company("http://127.0.0.1/")

    assert result.pages == []
    assert called["fetch"] is False
