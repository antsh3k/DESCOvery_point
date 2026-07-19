"""Tier-2 escalation logic in the scraper orchestrator."""

from types import SimpleNamespace

import app.services.scraper as scraper
from app.enums import FetchMethod
from app.services.scraper.base import ScrapedPage


def _settings(**kw) -> SimpleNamespace:
    base = dict(
        scrape_max_pages=5,
        scrape_tier2="claude",
        anthropic_api_key="key",
        anthropic_model="claude-sonnet-5",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _page(text: str) -> ScrapedPage:
    return ScrapedPage(url="https://x.com", title=None, text=text, method=FetchMethod.http)


async def test_escalates_to_claude_when_thin(monkeypatch):
    async def fake_fetch_site(url, *, max_pages):
        return [_page("tiny")]

    async def fake_claude(url, *, api_key, model):
        return [ScrapedPage(url=url, title=None, text="rich " * 200, method=FetchMethod.claude)]

    monkeypatch.setattr(scraper, "fetch_site", fake_fetch_site)
    monkeypatch.setattr(scraper, "get_settings", _settings)
    monkeypatch.setattr(scraper.tier2_claude, "fetch", fake_claude)

    result = await scraper.scrape_company("https://x.com")
    assert len(result.pages) == 2
    assert any(p.method == FetchMethod.claude for p in result.pages)


async def test_no_escalation_when_rich(monkeypatch):
    called = {"claude": False}

    async def fake_fetch_site(url, *, max_pages):
        return [_page("word " * 300)]

    async def fake_claude(url, *, api_key, model):
        called["claude"] = True
        return []

    monkeypatch.setattr(scraper, "fetch_site", fake_fetch_site)
    monkeypatch.setattr(scraper, "get_settings", _settings)
    monkeypatch.setattr(scraper.tier2_claude, "fetch", fake_claude)

    result = await scraper.scrape_company("https://x.com")
    assert called["claude"] is False
    assert len(result.pages) == 1


async def test_tier2_off_never_escalates(monkeypatch):
    async def fake_fetch_site(url, *, max_pages):
        return [_page("tiny")]

    monkeypatch.setattr(scraper, "fetch_site", fake_fetch_site)
    monkeypatch.setattr(scraper, "get_settings", lambda: _settings(scrape_tier2="off"))

    result = await scraper.scrape_company("https://x.com")
    assert len(result.pages) == 1
