"""Tiered scraper entry point.

Tier 1 (HTTP + parse) runs by default. A detector decides whether the content
is too thin; if so and Tier 2 is configured (``SCRAPE_TIER2=claude``), we
escalate to Claude's server-side ``web_fetch`` tool and append the fetched
pages. The public surface is :func:`scrape_company`.
"""

from __future__ import annotations

import logging

from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.services.scraper import tier2_claude
from app.services.scraper.base import ScrapedPage, ScrapeResult
from app.services.scraper.detector import needs_tier2
from app.services.scraper.tier1_http import fetch_site
from app.services.scraper.url_safety import UnsafeURLError, assert_public_http_url, normalize_url

__all__ = ["ScrapeResult", "ScrapedPage", "scrape_company"]

logger = logging.getLogger(__name__)


async def scrape_company(url: str, *, max_pages: int | None = None) -> ScrapeResult:
    settings = get_settings()
    max_pages = max_pages or settings.scrape_max_pages

    url = normalize_url(url)
    try:
        await run_in_threadpool(assert_public_http_url, url)
    except UnsafeURLError as exc:
        logger.warning("Refusing to scrape %s: %s", url, exc)
        return ScrapeResult(pages=[])

    pages = await fetch_site(url, max_pages=max_pages)
    result = ScrapeResult(pages=pages)

    tier2 = settings.scrape_tier2.lower()
    if tier2 != "off" and _should_escalate(pages):
        logger.info("Tier-1 thin for %s; escalating to Tier-2 (%s)", url, tier2)
        extra = await _run_tier2(tier2, url, settings)
        result.pages.extend(extra)

    return result


async def _run_tier2(tier2: str, url: str, settings) -> list[ScrapedPage]:
    if tier2 == "claude":
        return await tier2_claude.fetch(
            url, api_key=settings.anthropic_api_key, model=settings.anthropic_model
        )
    logger.warning("Unknown SCRAPE_TIER2 value: %r", tier2)
    return []


def _should_escalate(pages: list[ScrapedPage]) -> bool:
    if not pages:
        return True
    combined = " ".join(p.text for p in pages)
    return needs_tier2(html="", text=combined)
