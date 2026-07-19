"""Persisted results of a matching run."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin, UUIDMixin


class Match(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "matches"

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fund_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("funds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)

    passed_hard_filters: Mapped[bool] = mapped_column(Boolean, default=False)
    numeric_score: Mapped[float | None] = mapped_column(Numeric(6, 2))
    thesis_score: Mapped[float | None] = mapped_column(Numeric(6, 2))
    strategy_score: Mapped[float | None] = mapped_column(Numeric(6, 2))
    composite_score: Mapped[float | None] = mapped_column(Numeric(6, 2))

    matched_on: Mapped[dict | None] = mapped_column(JSONB)
    rationale: Mapped[str | None] = mapped_column(Text)
    rank: Mapped[int | None] = mapped_column()

    weights_used: Mapped[dict | None] = mapped_column(JSONB)
