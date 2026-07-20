"""Test doubles."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.schemas.company import CompanyProfile
from app.schemas.match import FitJudgment, RerankItem, RerankResult
from app.services.llm.base import LLMClient


class FakeLLM(LLMClient):
    """Deterministic LLM: scores by fund name, reranks in reverse order."""

    def _raw_complete(self, *, system: str, user: str) -> str:  # pragma: no cover
        raise NotImplementedError("FakeLLM overrides high-level methods")

    def judge_fit(self, *, company: CompanyProfile, fund: dict) -> FitJudgment:
        sectors = " ".join(fund.get("sectors", [])).lower()
        base = 90.0 if "software" in sectors else 50.0
        # A healthcare-only fund is a clear mismatch for the software companies
        # these tests use — exercise the plausibility exclusion path.
        plausible = "healthcare" not in sectors or "software" in sectors
        return FitJudgment(
            mandate_fit=base,
            strategy_fit=base - 10,
            value_creation_fit=base - 20,
            justification=f"Fit assessment for {fund['name']}",
            plausible_fit=plausible,
        )

    def rerank(self, *, company: CompanyProfile, candidates: list[dict]) -> RerankResult:
        # Reverse the incoming order to prove rerank actually reorders.
        items = [
            RerankItem(
                fund_id=c["fund_id"],
                rank=i,
                rationale=f"Why {c['name']} fits: strong alignment.",
            )
            for i, c in enumerate(reversed(candidates), start=1)
        ]
        return RerankResult(items=items)


def make_fund(**overrides) -> SimpleNamespace:
    defaults = dict(
        id=uuid.uuid4(),
        name="Test Fund",
        firm="Test Firm",
        sectors=["Software"],
        geographies=["UK"],
        check_size_min_usd_m=10,
        check_size_max_usd_m=100,
        ebitda_min_usd_m=2,
        ebitda_max_usd_m=30,
        revenue_min_usd_m=10,
        revenue_max_usd_m=120,
        stage="buyout",
        thesis="B2B software buyouts.",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)
