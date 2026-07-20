"""Company and its per-source provenance records."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.enums import CompanyStatus, EnrichmentStatus, FetchMethod
from app.models.mixins import TimestampMixin, UUIDMixin


class Company(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    # Canonicalized form of `url` (scheme/www./trailing-slash collapsed) used
    # to look up an already-analyzed company instead of re-scraping it.
    url_key: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(512))
    industry: Mapped[str | None] = mapped_column(String(256))
    sub_industry: Mapped[str | None] = mapped_column(String(256))
    location_country: Mapped[str | None] = mapped_column(String(128))
    location_region: Mapped[str | None] = mapped_column(String(128))

    size_employees: Mapped[int | None] = mapped_column()
    revenue_estimate_usd_m: Mapped[float | None] = mapped_column(Numeric(14, 2))
    ebitda_estimate_usd_m: Mapped[float | None] = mapped_column(Numeric(14, 2))

    products: Mapped[list] = mapped_column(JSONB, default=list)
    summary: Mapped[str | None] = mapped_column(Text)
    business_model: Mapped[str | None] = mapped_column(Text)

    ownership_status: Mapped[str | None] = mapped_column(String(128))
    investors: Mapped[list] = mapped_column(JSONB, default=list)
    competitors: Mapped[list] = mapped_column(JSONB, default=list)

    raw_extracted: Mapped[dict | None] = mapped_column(JSONB)
    extraction_confidence: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[CompanyStatus] = mapped_column(
        Enum(CompanyStatus, native_enum=False, length=32),
        default=CompanyStatus.pending,
        nullable=False,
    )
    enrichment_status: Mapped[EnrichmentStatus] = mapped_column(
        Enum(EnrichmentStatus, native_enum=False, length=32),
        default=EnrichmentStatus.pending,
        nullable=False,
    )
    # Append-only activity log powering the live "processing" view.
    progress: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    sources: Mapped[list["CompanySource"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CompanySource(UUIDMixin, Base):
    __tablename__ = "company_sources"

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    page_title: Mapped[str | None] = mapped_column(String(512))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetch_method: Mapped[FetchMethod] = mapped_column(
        Enum(FetchMethod, native_enum=False, length=32),
        default=FetchMethod.http,
        nullable=False,
    )
    snippet: Mapped[str | None] = mapped_column(Text)

    company: Mapped["Company"] = relationship(back_populates="sources")
