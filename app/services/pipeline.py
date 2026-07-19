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
from app.db import SessionLocal
from app.enums import CompanyStatus, EnrichmentStatus, FetchMethod
from app.models import AppSettings, Company, CompanySource, Fund, Match
from app.schemas.company import CompanyEnrichment, CompanyProfile, ExtractedSource
from app.services.enrichment import enrich_company
from app.services.extractor import extract_company_profile
from app.services.llm import LLMError, get_llm_client
from app.services.matching import run_match
from app.services.matching.score import DEFAULT_WEIGHTS
from app.services.scraper import scrape_company

logger = logging.getLogger(__name__)

_SNIPPET_CHARS = 300
_MAX_COMPETITORS = 5


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
    # Enrichment (web search) runs as a background job so the request returns
    # fast; see run_company_enrichment. Mark it queued, or skipped if disabled.
    company.enrichment_status = (
        EnrichmentStatus.pending
        if enrichment_enabled(settings)
        else EnrichmentStatus.skipped
    )
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
        ownership_status=company.ownership_status,
        investors=list(company.investors or []),
        competitors=list(company.competitors or []),
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


# -- enrichment -----------------------------------------------------------


def enrichment_enabled(settings: Settings) -> bool:
    return settings.enrich_source.lower() == "claude"


async def run_company_enrichment(company_id: uuid.UUID, settings: Settings) -> None:
    """Background job: search the web for supplemental firmographics and fold
    them into an already-extracted company. Runs on its own session (the
    request's session is long gone by the time this fires) and never raises —
    failures are recorded on ``enrichment_status``."""
    async with SessionLocal() as session:
        company = await session.get(Company, company_id)
        if company is None:
            logger.warning("Enrichment target %s no longer exists", company_id)
            return

        company.enrichment_status = EnrichmentStatus.running
        await session.commit()

        try:
            profile = company_to_profile(company)
            enrichment = await enrich_company(
                profile,
                company.url,
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model,
            )
            if enrichment is not None:
                merged = merge_enrichment(profile, enrichment)
                _apply_enrichment_fields(company, merged)
                _attach_search_sources(session, company, enrichment.sources)
            company.enrichment_status = EnrichmentStatus.done
            await session.commit()
        except Exception:  # noqa: BLE001 - a failed job must not leave a torn state
            logger.exception("Enrichment job failed for %s", company_id)
            await session.rollback()
            company = await session.get(Company, company_id)
            if company is not None:
                company.enrichment_status = EnrichmentStatus.failed
                await session.commit()


def merge_enrichment(
    profile: CompanyProfile, enrichment: CompanyEnrichment
) -> CompanyProfile:
    """Fold search results into the profile. Website extraction stays
    authoritative — enrichment only fills fields the site left empty."""
    merged = profile.model_copy(deep=True)

    if merged.size_employees is None and enrichment.size_employees is not None:
        merged.size_employees = enrichment.size_employees
    if merged.revenue_estimate_usd_m is None and enrichment.revenue_estimate_usd_m is not None:
        merged.revenue_estimate_usd_m = enrichment.revenue_estimate_usd_m
    if not merged.ownership_status and enrichment.ownership_status:
        merged.ownership_status = enrichment.ownership_status
    if not merged.investors and enrichment.investors:
        merged.investors = list(enrichment.investors)
    if not merged.competitors and enrichment.competitors:
        merged.competitors = list(enrichment.competitors[:_MAX_COMPETITORS])

    # Namespace enrichment confidences so they don't clobber extraction's.
    for key, value in (enrichment.confidence or {}).items():
        merged.confidence.setdefault(f"enriched.{key}", value)

    return merged


# -- internals ------------------------------------------------------------


def _maybe_llm(settings: Settings):
    try:
        return get_llm_client(settings)
    except LLMError as exc:
        logger.info("matching without LLM (%s); numeric-only ranking", exc)
        return None


def _apply_enrichment_fields(company: Company, merged: CompanyProfile) -> None:
    """Persist only the fields enrichment can fill; ``merge_enrichment`` has
    already enforced that website values win, so this is a straight write.
    ``raw_extracted`` (the original extraction output) is left untouched."""
    company.size_employees = merged.size_employees
    company.revenue_estimate_usd_m = merged.revenue_estimate_usd_m
    company.ownership_status = merged.ownership_status
    company.investors = merged.investors
    company.competitors = merged.competitors
    company.extraction_confidence = merged.confidence


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
    company.ownership_status = profile.ownership_status
    company.investors = profile.investors
    company.competitors = profile.competitors
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


def _attach_search_sources(
    session: AsyncSession, company: Company, sources: list[ExtractedSource]
) -> None:
    session.add_all(
        CompanySource(
            company_id=company.id,
            source_url=source.url,
            page_title=source.title,
            fetched_at=datetime.now(timezone.utc),
            fetch_method=FetchMethod.search,
            snippet=(source.snippet[:_SNIPPET_CHARS] if source.snippet else None),
        )
        for source in sources
        if source.url
    )


def _f(value) -> float | None:
    return float(value) if value is not None else None
