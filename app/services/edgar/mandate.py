"""Turn an EDGAR fund candidate into a mandate: resolve a website when the
bulk data didn't supply one, then reuse the existing scrape + LLM-extract
pipeline (the same primitives ``POST /funds/from-url`` uses) — no new
extraction logic here, just wiring.
"""

from __future__ import annotations

import logging
import re

from starlette.concurrency import run_in_threadpool

from app.schemas.fund import FundMandate
from app.services.edgar.candidates import FundCandidate
from app.services.llm import LLMClient
from app.services.scraper import scrape_company

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://[^\s\)\]\"']+")
_WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 3}
_MAX_TOKENS = 256
_EXTRACT_CHARS = 20_000


async def resolve_website(candidate: FundCandidate, *, api_key: str, model: str) -> str | None:
    """Ask Claude to find the fund/adviser's official website via web_search.
    Only called when EDGAR's own data didn't already supply one. Best-effort:
    returns None rather than raising on any failure."""
    if not api_key:
        return None

    identity = candidate.firm or candidate.name
    location = candidate.country or candidate.state or ""
    prompt = (
        f'Find the official website of the private equity firm or fund "{identity}"'
        f"{f' (based in {location})' if location else ''}. Reply with ONLY the "
        "single most likely URL and nothing else — no prose, no markdown. If you "
        "cannot find one with reasonable confidence, reply with exactly: NONE"
    )

    def _run() -> str | None:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model,
            max_tokens=_MAX_TOKENS,
            tools=[_WEB_SEARCH_TOOL],
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        match = _URL_RE.search(text)
        return match.group(0).rstrip(".,)") if match else None

    try:
        return await run_in_threadpool(_run)
    except Exception as exc:  # noqa: BLE001 - best-effort discovery, never abort the batch
        logger.warning("Website resolution failed for %s: %s", identity, exc)
        return None


async def infer_mandate(
    candidate: FundCandidate, website_url: str, *, llm: LLMClient, max_pages: int
) -> FundMandate | None:
    """Scrape ``website_url`` and LLM-extract a FundMandate. Returns None on a
    scrape or extraction failure — the caller just skips this candidate."""
    try:
        scrape = await scrape_company(website_url, max_pages=max_pages)
        if not scrape.pages:
            logger.info("No pages scraped for %s (%s)", candidate.name, website_url)
            return None
        mandate = await run_in_threadpool(
            llm.extract_fund, text=scrape.text[:_EXTRACT_CHARS], source_url=website_url
        )
    except Exception as exc:  # noqa: BLE001 - one bad candidate must not abort the batch
        logger.warning("Mandate inference failed for %s: %s", candidate.name, exc)
        return None

    # The site describes the firm; the filing gives us the specific fund's
    # legal name and adviser — keep those, take the mandate detail from the LLM.
    mandate.name = candidate.name
    mandate.firm = mandate.firm or candidate.firm
    mandate.source_url = mandate.source_url or website_url
    return mandate
