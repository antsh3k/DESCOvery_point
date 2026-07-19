"""Enumerations shared across models and schemas."""

from enum import StrEnum


class CompanyStatus(StrEnum):
    pending = "pending"
    scraped = "scraped"
    extracted = "extracted"
    failed = "failed"


class FetchMethod(StrEnum):
    http = "http"
    headless = "headless"
    tavily = "tavily"


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
