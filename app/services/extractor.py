"""Turn scraped text into a structured :class:`CompanyProfile` via the LLM."""

from __future__ import annotations

from app.schemas.company import CompanyProfile
from app.services.llm.base import LLMClient
from app.services.scraper import ScrapeResult

# Cap prompt size; homepages + a few pages comfortably fit well under this.
_MAX_CHARS = 20_000


def extract_company_profile(
    scrape: ScrapeResult, llm: LLMClient
) -> CompanyProfile:
    """Extract a company profile from scraped pages (sync; offload in async code)."""
    text = scrape.text[:_MAX_CHARS]
    return llm.extract_company(text=text, source_urls=scrape.source_urls)
