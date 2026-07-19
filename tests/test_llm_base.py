"""LLM base: JSON extraction and schema coercion (provider-agnostic)."""

import json

import pytest

from app.schemas.company import CompanyProfile
from app.services.llm.base import LLMClient, LLMError, _extract_json_object


class CannedLLM(LLMClient):
    def __init__(self, payload: str) -> None:
        self._payload = payload

    def _raw_complete(self, *, system: str, user: str) -> str:
        return self._payload


def test_extract_json_plain():
    assert _extract_json_object('{"a": 1}') == {"a": 1}


def test_extract_json_fenced():
    assert _extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_surrounded_by_prose():
    assert _extract_json_object('Sure!\n{"a": 1}\nDone') == {"a": 1}


def test_extract_company_coerces_schema():
    payload = json.dumps(
        {
            "name": "Acme",
            "industry": "Software",
            "summary": "B2B SaaS",
            "confidence": {"industry": 0.9},
            "sources": [{"url": "https://acme.com"}],
        }
    )
    profile = CannedLLM(payload).extract_company(text="…", source_urls=["https://acme.com"])
    assert isinstance(profile, CompanyProfile)
    assert profile.name == "Acme"
    assert profile.sources[0].url == "https://acme.com"


def test_non_json_raises_llm_error():
    with pytest.raises(LLMError):
        CannedLLM("no json here").extract_company(text="x", source_urls=[])
