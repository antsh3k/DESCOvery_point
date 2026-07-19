"""Tier-1 scraper: plain HTTP fetch + HTML parse.

Fetches the homepage, discovers a handful of high-signal internal pages
(about / products / services / …), and returns cleaned visible text plus the
source URL for each page. No browser, no JS execution.
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.enums import FetchMethod
from app.services.scraper.base import ScrapedPage
from app.services.scraper.parse import clean_html

logger = logging.getLogger(__name__)

_USER_AGENT = "descovery-point/0.1 (+https://github.com/antsh3k/DESCOvery_point)"
_TIMEOUT = httpx.Timeout(15.0)
_PRIORITY_KEYWORDS = (
    "about",
    "product",
    "service",
    "solution",
    "what-we-do",
    "company",
    "platform",
    "overview",
)


async def fetch_site(url: str, *, max_pages: int) -> list[ScrapedPage]:
    """Fetch the homepage plus prioritized internal pages (up to ``max_pages``)."""
    url = _normalize(url)
    pages: list[ScrapedPage] = []
    async with httpx.AsyncClient(
        headers={"User-Agent": _USER_AGENT},
        timeout=_TIMEOUT,
        follow_redirects=True,
    ) as client:
        home_html = await _get(client, url)
        if home_html is None:
            return pages
        pages.append(_to_page(url, home_html))

        for link in _pick_internal_links(url, home_html, limit=max_pages - 1):
            html = await _get(client, link)
            if html is not None:
                pages.append(_to_page(link, html))
    return pages


async def _get(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        if "text/html" not in resp.headers.get("content-type", ""):
            return None
        return resp.text
    except httpx.HTTPError as exc:
        logger.info("fetch failed for %s: %s", url, exc)
        return None


def _to_page(url: str, html: str) -> ScrapedPage:
    title, text = clean_html(html)
    return ScrapedPage(url=url, title=title, text=text, method=FetchMethod.http)


def _pick_internal_links(base_url: str, html: str, *, limit: int) -> list[str]:
    if limit <= 0:
        return []
    base_host = urlparse(base_url).netloc
    soup = BeautifulSoup(html, "html.parser")
    scored: dict[str, int] = {}
    for anchor in soup.find_all("a", href=True):
        href = urljoin(base_url, anchor["href"]).split("#")[0].rstrip("/")
        parsed = urlparse(href)
        if parsed.scheme not in ("http", "https") or parsed.netloc != base_host:
            continue
        if href == base_url.rstrip("/"):
            continue
        score = sum(kw in href.lower() for kw in _PRIORITY_KEYWORDS)
        # Keep the best score seen for a given URL.
        scored[href] = max(scored.get(href, 0), score)
    ranked = sorted(scored, key=lambda u: scored[u], reverse=True)
    return ranked[:limit]


def _normalize(url: str) -> str:
    if not urlparse(url).scheme:
        return f"https://{url}"
    return url
