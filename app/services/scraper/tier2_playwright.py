"""Tier-2 fallback via a headless browser (Playwright) for JS-heavy sites.

Optional dependency. Install with::

    uv sync --extra browser
    uv run playwright install chromium
"""

from __future__ import annotations

import logging

from app.enums import FetchMethod
from app.services.scraper.base import ScrapedPage
from app.services.scraper.parse import clean_html

logger = logging.getLogger(__name__)

_TIMEOUT_MS = 20_000


async def fetch(url: str) -> list[ScrapedPage]:
    """Render ``url`` with headless Chromium and return its text. [] on failure."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.info("Playwright fallback skipped: install the 'browser' extra")
        return []

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=_TIMEOUT_MS)
                html = await page.content()
            finally:
                await browser.close()
    except Exception as exc:  # noqa: BLE001 - render failures shouldn't crash ingest
        logger.warning("Playwright render failed for %s: %s", url, exc)
        return []

    title, text = clean_html(html)
    if not text.strip():
        return []
    return [ScrapedPage(url=url, title=title, text=text, method=FetchMethod.headless)]
