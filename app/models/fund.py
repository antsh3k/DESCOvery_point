"""PE fund with its investment mandate (the match target)."""

from sqlalchemy import Enum, Numeric, String, Text
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
    stage: Mapped[str | None] = mapped_column(String(128))
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
