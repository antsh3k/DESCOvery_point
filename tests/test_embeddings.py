"""Semantic pre-filter: cosine similarity + text-building (no network — the
OpenAI call itself is exercised by mocking ``embed_text``'s dependency, not by
hitting the real API)."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.matching.embeddings import (
    company_embedding_text,
    cosine_similarity,
    embed_text,
    fund_embedding_text,
    semantic_fit,
)
from tests.fakes import make_fund


def test_cosine_similarity_identical_vectors_is_one():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_opposite_vectors_is_minus_one():
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == -1.0


def test_cosine_similarity_none_on_empty_or_mismatched_or_zero_vector():
    assert cosine_similarity([], [1.0]) is None
    assert cosine_similarity([1.0, 2.0], [1.0]) is None
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) is None


def test_fund_embedding_text_combines_thesis_sectors_stage():
    fund = make_fund(thesis="Buys B2B software companies.", sectors=["Software"], stage="buyout")
    text = fund_embedding_text(fund)
    assert "Buys B2B software companies." in text
    assert "Software" in text
    assert "buyout" in text


def test_fund_embedding_text_none_when_nothing_to_embed():
    fund = make_fund(thesis=None, sectors=[], stage=None)
    assert fund_embedding_text(fund) is None


def test_company_embedding_text_combines_available_fields():
    company = SimpleNamespace(
        summary="B2B SaaS for mid-market logistics.",
        industry="Software",
        sub_industry="Logistics SaaS",
        business_model="Subscription",
        products=["Routing", "Tracking"],
    )
    text = company_embedding_text(company)
    assert "B2B SaaS for mid-market logistics." in text
    assert "Software" in text and "Logistics SaaS" in text
    assert "Subscription" in text
    assert "Routing" in text


def test_semantic_fit_none_when_either_side_missing():
    fund_with_embedding = make_fund(thesis_embedding=[1.0, 0.0])
    fund_without = make_fund(thesis_embedding=None)
    assert semantic_fit(None, fund_with_embedding) is None
    assert semantic_fit([1.0, 0.0], fund_without) is None


def test_semantic_fit_rescales_cosine_similarity_to_0_100():
    fund = make_fund(thesis_embedding=[1.0, 0.0])
    assert semantic_fit([1.0, 0.0], fund) == 100.0  # identical -> cos=1 -> 100
    fund_opposite = make_fund(thesis_embedding=[-1.0, 0.0])
    assert semantic_fit([1.0, 0.0], fund_opposite) == 0.0  # opposite -> cos=-1 -> 0


def test_embed_text_none_without_api_key():
    assert embed_text("some text", api_key="", model="text-embedding-3-small") is None


def test_embed_text_none_for_empty_text():
    assert embed_text("   ", api_key="fake-key", model="text-embedding-3-small") is None
