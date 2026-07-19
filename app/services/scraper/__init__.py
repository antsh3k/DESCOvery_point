"""Tiered scraper entry point.

Tier 1 (HTTP + parse) runs by default. A detector decides whether the content
is too thin; if so and Tier 2 is configured (``SCRAPE_TIER2=tavily|playwright``),
we escalate and append the rendered/extracted pages. The public surface is
:func:`scrape_company`.
"""

from __future__ import annotations

import logging

from app.config import get_settings
from app.services.scraper import tier2_playwright, tier2_tavily
from app.services.scraper.base import ScrapedPage, ScrapeResult
from app.services.scraper.detector import needs_tier2
from app.services.scraper.tier1_http import fetch_site

__all__ = ["ScrapeResult", "ScrapedPage", "scrape_company"]

logger = logging.getLogger(__name__)


async def scrape_company(url: str, *, max_pages: int | None = None) -> ScrapeResult:
    settings = get_settings()
    max_pages = max_pages or settings.scrape_max_pages

    pages = await fetch_site(url, max_pages=max_pages)
    result = ScrapeResult(pages=pages)

    tier2 = settings.scrape_tier2.lower()
    if tier2 != "off" and _should_escalate(pages):
        logger.info("Tier-1 thin for %s; escalating to Tier-2 (%s)", url, tier2)
        extra = await _run_tier2(tier2, url, settings.tavily_api_key)
        result.pages.extend(extra)

    return result


async def _run_tier2(tier2: str, url: str, tavily_api_key: str) -> list[ScrapedPage]:
    if tier2 == "tavily":
        return await tier2_tavily.fetch(url, api_key=tavily_api_key)
    if tier2 == "playwright":
        return await tier2_playwright.fetch(url)
    logger.warning("Unknown SCRAPE_TIER2 value: %r", tier2)
    return []


def _should_escalate(pages: list[ScrapedPage]) -> bool:
    if not pages:
        return True
    combined = " ".join(p.text for p in pages)
    return needs_tier2(html="", text=combined)
