"""Fund schemas — API I/O and the LLM mandate-extraction shape."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.enums import FundProvenance, MandateSource


class FundMandate(BaseModel):
    """A fund's investment mandate — the target the matcher scores against."""

    name: str
    firm: str | None = None
    website_url: str | None = None
    source_url: str | None = None
    sectors: list[str] = Field(default_factory=list)
    geographies: list[str] = Field(default_factory=list)
    check_size_min_usd_m: float | None = None
    check_size_max_usd_m: float | None = None
    ebitda_min_usd_m: float | None = None
    ebitda_max_usd_m: float | None = None
    revenue_min_usd_m: float | None = None
    revenue_max_usd_m: float | None = None
    stage: str | None = None
    thesis: str | None = None


class FundCreate(FundMandate):
    """Manual fund creation payload."""


class FundRead(FundMandate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provenance: FundProvenance
    mandate_source: MandateSource
    mandate_confidence: float | None
    created_at: datetime
    updated_at: datetime

    # Regulatory metadata (Form ADV / Form D) — straight from the filing,
    # not LLM-inferred; null for seed/manual/url_extracted funds.
    fund_type_raw: str | None = None
    gross_asset_value_usd: float | None = None
    amount_raised_usd: float | None = None
    investor_count: int | None = None
    filing_date: date | None = None
    auditor_name: str | None = None
    prime_broker_name: str | None = None
    custodian_name: str | None = None
    regulatory_id: str | None = None


class FundFromURL(BaseModel):
    url: str
