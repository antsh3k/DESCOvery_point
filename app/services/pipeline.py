"""High-level orchestration used by the routers.

Keeps request handlers thin: ingest+extract a company, and run the matcher and
persist results. Both flows degrade gracefully — a missing LLM key marks a
company ``failed`` on extraction, but matching still runs on numeric signals.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.enums import CompanyStatus, FetchMethod
from app.models import AppSettings, Company, CompanySource, Fund, Match
from app.schemas.company import CompanyProfile
from app.services.extractor import extract_company_profile
from app.services.llm import LLMError, get_llm_client
from app.services.matching import run_match
from app.services.matching.score import DEFAULT_WEIGHTS
from app.services.scraper import scrape_company

logger = logging.getLogger(__name__)

_SNIPPET_CHARS = 300


class ExtractionError(RuntimeError):
    """Raised when a company could not be scraped or extracted."""


async def ingest_and_extract(
    url: str, session: AsyncSession, settings: Settings
) -> Company:
    company = Company(url=url, status=CompanyStatus.pending)
    session.add(company)
    await session.flush()

    scrape = await scrape_company(url, max_pages=settings.scrape_max_pages)
    if not scrape.pages:
        company.status = CompanyStatus.failed
        await session.commit()
        raise ExtractionError(f"Could not fetch any pages from {url}")
    company.status = CompanyStatus.scraped

    try:
        llm = get_llm_client(settings)
        profile = await run_in_threadpool(extract_company_profile, scrape, llm)
    except LLMError as exc:
        company.status = CompanyStatus.failed
        await session.commit()
        raise ExtractionError(str(exc)) from exc

    _apply_profile(company, profile)
    _attach_sources(session, company, scrape)
    company.status = CompanyStatus.extracted
    await session.commit()
    # Re-load with sources eagerly populated so response serialization does
    # not emit a lazy-load on the async session.
    return await _get_with_sources(session, company.id)


async def run_company_match(
    company: Company, session: AsyncSession, settings: Settings
) -> list[Match]:
    funds = (await session.execute(select(Fund))).scalars().all()
    app_settings = await get_or_create_settings(session)
    weights = weights_from_settings(app_settings)

    profile = company_to_profile(company)
    llm = _maybe_llm(settings)

    results = await run_match(profile, list(funds), weights=weights, llm=llm)

    run_id = uuid.uuid4()
    await session.execute(delete(Match).where(Match.company_id == company.id))
    matches = [
        Match(
            company_id=company.id,
            fund_id=uuid.UUID(r.fund_id),
            run_id=run_id,
            passed_hard_filters=r.passed_hard_filters,
            numeric_score=r.numeric_score,
            thesis_score=r.thesis_score,
            strategy_score=r.strategy_score,
            composite_score=r.composite_score,
            matched_on=r.matched_on,
            rationale=r.rationale,
            rank=r.rank,
            weights_used=r.weights_used,
        )
        for r in results
    ]
    session.add_all(matches)
    await session.commit()
    return matches


def company_to_profile(company: Company) -> CompanyProfile:
    return CompanyProfile(
        name=company.name,
        industry=company.industry,
        sub_industry=company.sub_industry,
        location_country=company.location_country,
        location_region=company.location_region,
        size_employees=company.size_employees,
        revenue_estimate_usd_m=_f(company.revenue_estimate_usd_m),
        ebitda_estimate_usd_m=_f(company.ebitda_estimate_usd_m),
        products=list(company.products or []),
        business_model=company.business_model,
        summary=company.summary,
        confidence=company.extraction_confidence or {},
    )


async def get_or_create_settings(session: AsyncSession) -> AppSettings:
    row = (await session.execute(select(AppSettings).limit(1))).scalar_one_or_none()
    if row is None:
        row = AppSettings()
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


def weights_from_settings(row: AppSettings) -> dict[str, float]:
    return {
        "thesis": _f(row.weight_thesis) or DEFAULT_WEIGHTS["thesis"],
        "numeric": _f(row.weight_numeric) or DEFAULT_WEIGHTS["numeric"],
        "strategy": _f(row.weight_strategy) or DEFAULT_WEIGHTS["strategy"],
    }


# -- internals ------------------------------------------------------------


def _maybe_llm(settings: Settings):
    try:
        return get_llm_client(settings)
    except LLMError as exc:
        logger.info("matching without LLM (%s); numeric-only ranking", exc)
        return None


def _apply_profile(company: Company, profile: CompanyProfile) -> None:
    company.name = profile.name
    company.industry = profile.industry
    company.sub_industry = profile.sub_industry
    company.location_country = profile.location_country
    company.location_region = profile.location_region
    company.size_employees = profile.size_employees
    company.revenue_estimate_usd_m = profile.revenue_estimate_usd_m
    company.ebitda_estimate_usd_m = profile.ebitda_estimate_usd_m
    company.products = profile.products
    company.summary = profile.summary
    company.business_model = profile.business_model
    company.raw_extracted = profile.model_dump(mode="json")
    company.extraction_confidence = profile.confidence


async def _get_with_sources(session: AsyncSession, company_id: uuid.UUID) -> Company:
    result = await session.execute(
        select(Company)
        .where(Company.id == company_id)
        .options(selectinload(Company.sources))
    )
    return result.scalar_one()


def _attach_sources(session: AsyncSession, company: Company, scrape) -> None:
    # Build rows with the FK set explicitly rather than appending to the
    # lazy `company.sources` collection, which would emit a lazy-load SELECT
    # outside a greenlet context on the async session.
    session.add_all(
        CompanySource(
            company_id=company.id,
            source_url=page.url,
            page_title=page.title,
            fetched_at=datetime.now(timezone.utc),
            fetch_method=page.method or FetchMethod.http,
            snippet=(page.text[:_SNIPPET_CHARS] or None),
        )
        for page in scrape.pages
    )


def _f(value) -> float | None:
    return float(value) if value is not None else None
