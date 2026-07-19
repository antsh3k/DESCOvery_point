"""Enumerations shared across models and schemas."""

from enum import StrEnum


class CompanyStatus(StrEnum):
    pending = "pending"
    scraped = "scraped"
    extracted = "extracted"
    failed = "failed"


class EnrichmentStatus(StrEnum):
    """Lifecycle of the background firmographics-enrichment job."""

    pending = "pending"  # queued, not yet started
    running = "running"  # web search in progress
    done = "done"
    failed = "failed"
    skipped = "skipped"  # enrichment disabled (ENRICH_SOURCE=off)


class FetchMethod(StrEnum):
    http = "http"
    claude = "claude"
    search = "search"


class FundProvenance(StrEnum):
    seed = "seed"
    edgar = "edgar"
    manual = "manual"
    url_extracted = "url_extracted"


class MandateSource(StrEnum):
    authoritative = "authoritative"
    ai_inferred = "ai_inferred"


class LLMProvider(StrEnum):
    anthropic = "anthropic"
    openai = "openai"
