"""Match schemas — API output and LLM judge/rerank shapes."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class FitJudgment(BaseModel):
    """LLM verdict on how well a company fits a single fund, across three axes."""

    mandate_fit: float = Field(
        ge=0,
        le=100,
        description=(
            "How central the company's sector/business is to what the fund invests "
            "in — core to the thesis (high) vs merely adjacent (low)."
        ),
    )
    strategy_fit: float = Field(
        ge=0,
        le=100,
        description=(
            "How well the company's deal situation matches the fund's playbook — "
            "control vs minority, buyout vs growth vs turnaround vs roll-up — given "
            "its ownership, deal stage, and growth trajectory."
        ),
    )
    value_creation_fit: float = Field(
        ge=0,
        le=100,
        description=(
            "How well the fund's capabilities serve *this* company's needs — e.g. "
            "buy-and-build capital for a fragmented market, professionalising a "
            "founder-run business, sector operating expertise."
        ),
    )
    justification: str
    plausible_fit: bool = Field(
        default=True,
        description=(
            "False only when the fund is a clear mismatch that should be excluded "
            "from the shortlist (e.g. the company's sector is plainly outside the "
            "fund's mandate, or ownership makes the fund's deal type impossible). "
            "Defaults to True so an omission never over-excludes."
        ),
    )


class RerankItem(BaseModel):
    fund_id: str
    rank: int
    rationale: str


class RerankResult(BaseModel):
    items: list[RerankItem] = Field(default_factory=list)


class MatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    fund_id: uuid.UUID
    run_id: uuid.UUID
    passed_hard_filters: bool
    mandate_score: float | None
    strategy_score: float | None
    value_creation_score: float | None
    composite_score: float | None
    matched_on: dict | None
    rationale: str | None
    rank: int | None
    weights_used: dict | None
