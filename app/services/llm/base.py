"""Provider-agnostic LLM client.

Subclasses implement a single primitive, :meth:`_raw_complete`, that turns a
(system, user) pair into raw text. The base class layers JSON-schema prompting,
tolerant parsing, and the high-level ``extract`` / ``judge`` / ``rerank`` calls
on top, so every provider shares identical behaviour.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.schemas.company import CompanyProfile
from app.schemas.fund import FundMandate
from app.schemas.match import RerankResult, ThesisJudgment

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Raised when the model output cannot be coerced into the target schema."""


class LLMClient(ABC):
    """Base class for all LLM providers."""

    @abstractmethod
    def _raw_complete(self, *, system: str, user: str) -> str:
        """Return the model's raw text response for a (system, user) prompt."""

    # -- structured helper ------------------------------------------------

    def _complete_schema(self, *, system: str, user: str, schema: type[T]) -> T:
        instruction = (
            "Respond with a single JSON object and nothing else — no prose, no "
            "markdown fences. It must conform to this JSON schema:\n"
            f"{json.dumps(schema.model_json_schema())}"
        )
        text = self._raw_complete(system=system, user=f"{user}\n\n{instruction}")
        payload = _extract_json_object(text)
        try:
            return schema.model_validate(payload)
        except ValidationError as exc:  # noqa: TRY003 - context matters here
            logger.warning("LLM output failed validation for %s: %s", schema.__name__, exc)
            raise LLMError(f"Invalid {schema.__name__} from model") from exc

    # -- high-level operations -------------------------------------------

    def extract_company(self, *, text: str, source_urls: list[str]) -> CompanyProfile:
        system = (
            "You are an analyst extracting structured facts about a company from "
            "its website. Only use information supported by the provided text. Do "
            "not invent figures. Financial estimates are in USD millions; leave any "
            "field null when the text does not support it (missing is not zero). For "
            "each field you populate, add a 0-1 confidence to `confidence` and cite "
            "the source URL(s) you relied on in `sources`."
        )
        user = (
            f"Known source URLs: {source_urls}\n\n"
            f"Website text:\n\"\"\"\n{text}\n\"\"\""
        )
        return self._complete_schema(system=system, user=user, schema=CompanyProfile)

    def extract_fund(self, *, text: str, source_url: str | None) -> FundMandate:
        system = (
            "You are extracting a private-equity fund's investment mandate from its "
            "website. Capture target sectors, geographies, cheque size, EBITDA and "
            "revenue ranges (USD millions), stage, and a concise thesis. Leave fields "
            "null when unsupported by the text; do not fabricate ranges."
        )
        user = f"Source URL: {source_url}\n\nWebsite text:\n\"\"\"\n{text}\n\"\"\""
        return self._complete_schema(system=system, user=user, schema=FundMandate)

    def judge_thesis(
        self, *, company: CompanyProfile, fund: dict
    ) -> ThesisJudgment:
        system = (
            "You judge how well a target company fits a PE fund. Score 0-100 on two "
            "axes: `thesis_score` (does the business match what the fund is trying to "
            "build?) and `strategy_score` (buy-and-build / add-on / operational fit). "
            "Give a one-to-two sentence justification."
        )
        user = (
            f"Company profile:\n{company.model_dump_json(indent=2)}\n\n"
            f"Fund mandate:\n{json.dumps(fund, default=str, indent=2)}"
        )
        return self._complete_schema(system=system, user=user, schema=ThesisJudgment)

    def rerank(self, *, company: CompanyProfile, candidates: list[dict]) -> RerankResult:
        system = (
            "You are re-ranking the top candidate PE funds for a target company. "
            "Re-order them best-first and, for each, write a concise 'why this fits' "
            "justification grounded in the company profile and the fund's mandate. "
            "Return every candidate's fund_id with a 1-based rank and rationale."
        )
        user = (
            f"Company profile:\n{company.model_dump_json(indent=2)}\n\n"
            f"Candidate funds (with current scores):\n"
            f"{json.dumps(candidates, default=str, indent=2)}"
        )
        return self._complete_schema(system=system, user=user, schema=RerankResult)


def _extract_json_object(text: str) -> dict:
    """Best-effort extraction of the first JSON object from model text."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{") : text.rfind("}") + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError as exc:
                raise LLMError("Model did not return valid JSON") from exc
        raise LLMError("Model did not return a JSON object")
