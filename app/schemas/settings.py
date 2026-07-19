"""Application settings schemas."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class SettingsUpdate(BaseModel):
    weight_thesis: float | None = Field(default=None, ge=0, le=1)
    weight_numeric: float | None = Field(default=None, ge=0, le=1)
    weight_strategy: float | None = Field(default=None, ge=0, le=1)
    llm_provider: str | None = None
    llm_model: str | None = None
    scrape_max_pages: int | None = Field(default=None, ge=1, le=50)


class SettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    weight_thesis: float
    weight_numeric: float
    weight_strategy: float
    llm_provider: str
    llm_model: str | None
    scrape_max_pages: int
