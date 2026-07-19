"""Tier-2 fallback via Claude's server-side ``web_fetch`` tool.

Anthropic's infrastructure fetches the URL (which sidesteps the bot protection
and client-side rendering that defeat the plain-HTTP Tier-1), and we pull the
fetched page text back out of the ``web_fetch_tool_result`` blocks as
``ScrapedPage``s — so the extractor and matcher downstream are unchanged. No
API key beyond the one the app already uses, and no headless browser to install.

Requires a model that supports the ``web_fetch_20260209`` tool
(Claude Opus 4.6+, Sonnet 4.6, or Sonnet 5+).
"""

from __future__ import annotations

import logging

from starlette.concurrency import run_in_threadpool

from app.enums import FetchMethod
from app.services.scraper.base import ScrapedPage

logger = logging.getLogger(__name__)

_MAX_TOKENS = 4096
_MAX_RESUMES = 4  # guard the server-tool pause/resume loop
_WEB_FETCH_TOOL = {
    "type": "web_fetch_20260209",
    "name": "web_fetch",
    "max_uses": 3,
    "max_content_tokens": 20_000,
}
_PROMPT = (
    "Use the web_fetch tool to retrieve this company's website: {url}\n"
    "Fetch the homepage, and if it links to obvious about / products / services "
    "pages, fetch a couple of those too. Return the pages' content; do not "
    "summarise or add commentary."
)


async def fetch(url: str, *, api_key: str, model: str) -> list[ScrapedPage]:
    """Fetch ``url`` via Claude's ``web_fetch`` tool. Returns [] on failure."""
    if not api_key:
        logger.info("Claude web_fetch fallback skipped: ANTHROPIC_API_KEY not set")
        return []

    def _run() -> list[ScrapedPage]:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        messages = [{"role": "user", "content": _PROMPT.format(url=url)}]
        pages: list[ScrapedPage] = []
        for _ in range(_MAX_RESUMES):
            resp = client.messages.create(
                model=model,
                max_tokens=_MAX_TOKENS,
                tools=[_WEB_FETCH_TOOL],
                messages=messages,
            )
            pages.extend(_pages_from_response(resp, url))
            # Server-side tool loop can pause; re-send to let it resume.
            if resp.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": resp.content})
        return _dedupe(pages)

    try:
        return await run_in_threadpool(_run)
    except Exception as exc:  # noqa: BLE001 - network/model errors shouldn't crash ingest
        logger.warning("Claude web_fetch failed for %s: %s", url, exc)
        return []


def _pages_from_response(resp, fallback_url: str) -> list[ScrapedPage]:
    pages: list[ScrapedPage] = []
    for block in resp.content:
        if getattr(block, "type", None) != "web_fetch_tool_result":
            continue
        result = getattr(block, "content", None)
        # A failed fetch is a bare error object, not a web_fetch_result.
        if getattr(result, "type", None) != "web_fetch_result":
            logger.info(
                "web_fetch returned no content for %s: %r", fallback_url, result
            )
            continue
        document = getattr(result, "content", None)
        text = _document_text(document)
        if text.strip():
            pages.append(
                ScrapedPage(
                    url=getattr(result, "url", None) or fallback_url,
                    title=_document_title(document),
                    text=" ".join(text.split()),
                    method=FetchMethod.claude,
                )
            )
    return pages


def _document_text(document) -> str:
    source = getattr(document, "source", None)
    data = getattr(source, "data", None)
    return data if isinstance(data, str) else ""


def _document_title(document) -> str | None:
    title = getattr(document, "title", None)
    return title if isinstance(title, str) else None


def _dedupe(pages: list[ScrapedPage]) -> list[ScrapedPage]:
    seen: set[str] = set()
    unique: list[ScrapedPage] = []
    for page in pages:
        if page.url in seen:
            continue
        seen.add(page.url)
        unique.append(page)
    return unique
