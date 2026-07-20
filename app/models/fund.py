"""PE fund with its investment mandate (the match target)."""

from datetime import date

from sqlalchemy import Date, Enum, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.enums import FundProvenance, MandateSource
from app.models.mixins import TimestampMixin, UUIDMixin


class Fund(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "funds"

    name: Mapped[str] = mapped_column(String(512), nullable=False)
    firm: Mapped[str | None] = mapped_column(String(512))
    website_url: Mapped[str | None] = mapped_column(String(2048))
    source_url: Mapped[str | None] = mapped_column(String(2048))

    # --- Mandate ---
    sectors: Mapped[list] = mapped_column(JSONB, default=list)
    geographies: Mapped[list] = mapped_column(JSONB, default=list)
    check_size_min_usd_m: Mapped[float | None] = mapped_column(Numeric(14, 2))
    check_size_max_usd_m: Mapped[float | None] = mapped_column(Numeric(14, 2))
    ebitda_min_usd_m: Mapped[float | None] = mapped_column(Numeric(14, 2))
    ebitda_max_usd_m: Mapped[float | None] = mapped_column(Numeric(14, 2))
    revenue_min_usd_m: Mapped[float | None] = mapped_column(Numeric(14, 2))
    revenue_max_usd_m: Mapped[float | None] = mapped_column(Numeric(14, 2))
    # Usually a short label ("buyout"), but some real fund sites describe
    # strategy/stage in a full sentence — wide enough not to truncate those.
    stage: Mapped[str | None] = mapped_column(String(512))
    thesis: Mapped[str | None] = mapped_column(Text)

    provenance: Mapped[FundProvenance] = mapped_column(
        Enum(FundProvenance, native_enum=False, length=32),
        default=FundProvenance.seed,
        nullable=False,
    )
    mandate_source: Mapped[MandateSource] = mapped_column(
        Enum(MandateSource, native_enum=False, length=32),
        default=MandateSource.authoritative,
        nullable=False,
    )
    mandate_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))

    # --- Regulatory metadata (Form ADV / Form D — straight from the filing,
    # not LLM-inferred; null for seed/manual/url_extracted funds) ---
    fund_type_raw: Mapped[str | None] = mapped_column(String(128))
    gross_asset_value_usd: Mapped[float | None] = mapped_column(Numeric(20, 2))
    amount_raised_usd: Mapped[float | None] = mapped_column(Numeric(20, 2))
    investor_count: Mapped[int | None] = mapped_column(Integer)
    filing_date: Mapped[date | None] = mapped_column(Date)
    auditor_name: Mapped[str | None] = mapped_column(String(512))
    prime_broker_name: Mapped[str | None] = mapped_column(String(512))
    custodian_name: Mapped[str | None] = mapped_column(String(512))
    regulatory_id: Mapped[str | None] = mapped_column(String(128))
