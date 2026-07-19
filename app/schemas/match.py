"""Match schemas — API output and LLM judge/rerank shapes."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class ThesisJudgment(BaseModel):
    """LLM verdict on how well a company fits a single fund's thesis/strategy."""

    thesis_score: float = Field(ge=0, le=100)
    strategy_score: float = Field(ge=0, le=100)
    justification: str
    plausible_fit: bool = Field(
        default=True,
        description=(
            "False only when the fund is a clear mismatch that should be excluded "
            "from the shortlist (e.g. the company's sector is plainly outside the "
            "fund's mandate). Defaults to True so an omission never over-excludes."
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
    numeric_score: float | None
    thesis_score: float | None
    strategy_score: float | None
    composite_score: float | None
    matched_on: dict | None
    rationale: str | None
    rank: int | None
    weights_used: dict | None
