"""Single-row application settings (weights, provider, scrape config)."""

from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin, UUIDMixin


class AppSettings(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "settings"

    weight_thesis: Mapped[float] = mapped_column(Numeric(4, 3), default=0.40)
    weight_numeric: Mapped[float] = mapped_column(Numeric(4, 3), default=0.35)
    weight_strategy: Mapped[float] = mapped_column(Numeric(4, 3), default=0.25)

    llm_provider: Mapped[str] = mapped_column(String(32), default="anthropic")
    llm_model: Mapped[str | None] = mapped_column(String(128))
    scrape_max_pages: Mapped[int] = mapped_column(Integer, default=6)
