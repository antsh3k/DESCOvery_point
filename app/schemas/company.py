"""Company schemas — API I/O and the LLM extraction shape."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.enums import CompanyStatus, FetchMethod


class ExtractedSource(BaseModel):
    """A page the extractor relied on, cited on the dashboard."""

    url: str
    title: str | None = None
    snippet: str | None = None


class CompanyProfile(BaseModel):
    """Structured company facts produced by the LLM extractor.

    Numeric estimates are in USD millions to align with fund mandate ranges.
    Every numeric is optional: SMEs rarely disclose financials, and a missing
    value must never be treated as zero (see scoring rules).
    """

    name: str | None = None
    industry: str | None = None
    sub_industry: str | None = None
    location_country: str | None = None
    location_region: str | None = None
    size_employees: int | None = None
    revenue_estimate_usd_m: float | None = None
    ebitda_estimate_usd_m: float | None = None
    products: list[str] = Field(default_factory=list)
    business_model: str | None = None
    summary: str | None = None
    confidence: dict[str, float] = Field(
        default_factory=dict, description="Per-field confidence in [0, 1]."
    )
    sources: list[ExtractedSource] = Field(default_factory=list)


class CompanyCreate(BaseModel):
    url: str


class CompanySourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_url: str
    page_title: str | None
    fetch_method: FetchMethod
    snippet: str | None


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    name: str | None
    industry: str | None
    sub_industry: str | None
    location_country: str | None
    location_region: str | None
    size_employees: int | None
    revenue_estimate_usd_m: float | None
    ebitda_estimate_usd_m: float | None
    products: list
    summary: str | None
    business_model: str | None
    extraction_confidence: dict | None
    status: CompanyStatus
    sources: list[CompanySourceRead]
    created_at: datetime
    updated_at: datetime


class CompanyListItem(BaseModel):
    """Lightweight row for the 'recent analyses' list (no sources/summary)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    name: str | None
    industry: str | None
    location_country: str | None
    status: CompanyStatus
    created_at: datetime
