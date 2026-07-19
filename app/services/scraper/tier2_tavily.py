"""Tier-2 fallback via Tavily's extract API (no browser required)."""

from __future__ import annotations

import logging

from starlette.concurrency import run_in_threadpool

from app.enums import FetchMethod
from app.services.scraper.base import ScrapedPage

logger = logging.getLogger(__name__)


async def fetch(url: str, *, api_key: str) -> list[ScrapedPage]:
    """Extract cleaned content for ``url`` via Tavily. Returns [] on failure."""
    if not api_key:
        logger.info("Tavily fallback skipped: TAVILY_API_KEY not set")
        return []

    def _extract() -> dict:
        from tavily import TavilyClient

        return TavilyClient(api_key=api_key).extract(urls=[url])

    try:
        data = await run_in_threadpool(_extract)
    except Exception as exc:  # noqa: BLE001 - network/SDK errors shouldn't crash ingest
        logger.warning("Tavily extract failed for %s: %s", url, exc)
        return []

    pages: list[ScrapedPage] = []
    for result in data.get("results", []):
        text = result.get("raw_content") or result.get("content") or ""
        if text.strip():
            pages.append(
                ScrapedPage(
                    url=result.get("url", url),
                    title=None,
                    text=" ".join(text.split()),
                    method=FetchMethod.tavily,
                )
            )
    return pages
