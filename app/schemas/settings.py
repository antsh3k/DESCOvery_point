"""Application settings schemas."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class SettingsUpdate(BaseModel):
    weight_mandate: float | None = Field(default=None, ge=0, le=1)
    weight_strategy: float | None = Field(default=None, ge=0, le=1)
    weight_value_creation: float | None = Field(default=None, ge=0, le=1)
    llm_provider: str | None = None
    llm_model: str | None = None
    scrape_max_pages: int | None = Field(default=None, ge=1, le=50)


class SettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    weight_mandate: float
    weight_strategy: float
    weight_value_creation: float
    llm_provider: str
    llm_model: str | None
    scrape_max_pages: int
