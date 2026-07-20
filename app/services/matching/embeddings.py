"""Semantic pre-filter: OpenAI embeddings of a fund's thesis/sectors/stage,
compared via cosine similarity against a company's profile text, to help rank
Stage-1 survivors before the LLM-cost-bounded judge stage — a companion signal
to the deterministic size fit (:mod:`.mandate`), not a replacement for it.
Size answers "is the target in the fund's box"; this answers "does the fund's
actual thesis relate to this business" — a semantic question that sector
substring-matching can't reliably answer (see :mod:`.filters`).

Anthropic has no embeddings API, so this always uses OpenAI regardless of
which provider is configured for chat/completions — ``openai_api_key`` needs
setting separately from ``anthropic_api_key`` for any of this to do anything.
Embeddings are strictly an optimisation: every function here degrades to
``None`` on a missing key, empty text, or API failure, exactly like every
other soft signal in the matching engine — never a hard requirement.
"""

from __future__ import annotations

import logging
import math

from sqlalchemy import select

logger = logging.getLogger(__name__)


def embed_text(text: str, *, api_key: str, model: str) -> list[float] | None:
    """Embed a single string. None on a missing key, empty text, or API error."""
    if not api_key or not text or not text.strip():
        return None
    try:
        import openai  # imported lazily so the app boots without the key

        client = openai.OpenAI(api_key=api_key)
        resp = client.embeddings.create(model=model, input=text)
        return list(resp.data[0].embedding)
    except Exception as exc:  # noqa: BLE001 - embeddings are a best-effort optimisation
        logger.warning("Embedding failed: %s", exc)
        return None


def fund_embedding_text(fund) -> str | None:
    """Text summarising a fund's mandate for embedding — thesis is the core
    signal; sectors/stage add structure when thesis is thin or missing.
    None when there's nothing to embed (most `pending` funds)."""
    parts: list[str] = []
    if fund.thesis:
        parts.append(fund.thesis)
    if fund.sectors:
        parts.append("Sectors: " + ", ".join(fund.sectors))
    if fund.stage:
        parts.append(f"Stage: {fund.stage}")
    text = "\n".join(parts).strip()
    return text or None


def company_embedding_text(company) -> str | None:
    """Text summarising a company for embedding — mirrors fund_embedding_text
    so both sides land in the same semantic space."""
    parts: list[str] = []
    if getattr(company, "summary", None):
        parts.append(company.summary)
    industry = getattr(company, "industry", None)
    if industry:
        sub = getattr(company, "sub_industry", None)
        parts.append(f"Industry: {industry}" + (f" / {sub}" if sub else ""))
    if getattr(company, "business_model", None):
        parts.append(f"Business model: {company.business_model}")
    products = getattr(company, "products", None)
    if products:
        parts.append("Products: " + ", ".join(products))
    text = "\n".join(parts).strip()
    return text or None


def cosine_similarity(a: list[float], b: list[float]) -> float | None:
    if not a or not b or len(a) != len(b):
        return None
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return None
    return dot / (norm_a * norm_b)


def semantic_fit(company_embedding: list[float] | None, fund) -> float | None:
    """Cosine similarity between the company's embedding and the fund's
    stored thesis embedding, rescaled from [-1, 1] to 0-100. None when either
    side has no embedding — never scored as zero."""
    fund_embedding = getattr(fund, "thesis_embedding", None)
    if company_embedding is None or fund_embedding is None:
        return None
    sim = cosine_similarity(list(company_embedding), list(fund_embedding))
    if sim is None:
        return None
    return (sim + 1.0) / 2.0 * 100.0


async def backfill_fund_embeddings(*, api_key: str, model: str) -> dict:
    """Compute + store ``thesis_embedding`` for every fund with embeddable
    text (thesis/sectors/stage) that doesn't have one yet. Skips funds with
    nothing to embed — most ``pending`` funds have no mandate text at all —
    rather than embedding an empty string. Safe to re-run.
    """
    from app.db import SessionLocal
    from app.models import Fund

    stats = {"eligible": 0, "embedded": 0, "skipped_no_text": 0, "failed": 0}

    async with SessionLocal() as session:
        funds = (
            await session.execute(select(Fund).where(Fund.thesis_embedding.is_(None)))
        ).scalars().all()

    for fund in funds:
        text = fund_embedding_text(fund)
        if text is None:
            stats["skipped_no_text"] += 1
            continue
        stats["eligible"] += 1
        vector = embed_text(text, api_key=api_key, model=model)
        if vector is None:
            stats["failed"] += 1
            continue
        async with SessionLocal() as session:
            db_fund = await session.get(Fund, fund.id)
            db_fund.thesis_embedding = vector
            await session.commit()
        stats["embedded"] += 1

    logger.info("Embedding backfill done: %s", stats)
    return stats
