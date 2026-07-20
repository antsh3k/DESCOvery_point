"""High-level orchestration used by the routers.

Keeps request handlers thin: ingest+extract a company, and run the matcher and
persist results. Both flows degrade gracefully — a missing LLM key marks a
company ``failed`` on extraction, but matching still runs on numeric signals.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.db import SessionLocal
from app.enums import CompanyStatus, EnrichmentStatus, FetchMethod, MandateSource
from app.models import AppSettings, Company, CompanySource, Fund, Match
from app.schemas.company import CompanyEnrichment, CompanyProfile, ExtractedSource
from app.services.enrichment import enrich_company
from app.services.extractor import extract_company_profile
from app.services.llm import LLMError, get_llm_client
from app.services.matching import run_match
from app.services.matching.embeddings import company_embedding_text, embed_text
from app.services.matching.score import DEFAULT_WEIGHTS
from app.services.scraper import scrape_company
from app.services.scraper.url_safety import canonical_url_key, normalize_url

logger = logging.getLogger(__name__)

_SNIPPET_CHARS = 300
_MAX_COMPETITORS = 5


class ExtractionError(RuntimeError):
    """Raised when a company could not be scraped or extracted."""


async def get_or_create_company(
    url: str, session: AsyncSession, settings: Settings
) -> tuple[Company, bool]:
    """Look up a company by its canonical URL first and reuse it instead of
    re-scraping a site we've already analyzed. A previously failed attempt is
    retried in place rather than left stuck. Returns ``(company, should_ingest)``
    — the caller schedules :func:`run_company_ingest` only when ``True``."""
    key = canonical_url_key(url)
    existing = (
        await session.execute(select(Company).where(Company.url_key == key))
    ).scalar_one_or_none()

    if existing is not None and existing.status != CompanyStatus.failed:
        return await _get_with_sources(session, existing.id), False

    if existing is not None:
        await _requeue(existing, session, settings, "Retrying failed analysis")
        return await _get_with_sources(session, existing.id), True

    company = Company(
        url=normalize_url(url),
        url_key=key,
        status=CompanyStatus.pending,
        enrichment_status=(
            EnrichmentStatus.pending
            if enrichment_enabled(settings)
            else EnrichmentStatus.skipped
        ),
        progress=[_event("Queued for analysis")],
    )
    session.add(company)
    await session.commit()
    return await _get_with_sources(session, company.id), True


async def refresh_company(
    company: Company, session: AsyncSession, settings: Settings
) -> Company:
    """Re-queue an already-analyzed company for a fresh scrape → extract →
    enrich pass, so stale data (a site update, a headcount change) can be
    pulled in on manual request rather than only ever ingesting once."""
    await _requeue(company, session, settings, "Refresh requested")
    return await _get_with_sources(session, company.id)


async def _requeue(
    company: Company, session: AsyncSession, settings: Settings, label: str
) -> None:
    company.status = CompanyStatus.pending
    company.enrichment_status = (
        EnrichmentStatus.pending
        if enrichment_enabled(settings)
        else EnrichmentStatus.skipped
    )
    company.progress = [*(company.progress or []), _event(label)]
    # Old matches were scored against the profile this refresh is about to
    # replace; clear them so the UI can't show a shortlist for stale data.
    await session.execute(delete(Match).where(Match.company_id == company.id))
    await session.commit()


async def run_company_ingest(company_id: uuid.UUID, settings: Settings) -> None:
    """Background job: run the full scrape → extract → enrich pipeline on its
    own session, recording each stage in ``progress`` so the UI can render live
    activity. Never raises — failures land on ``status`` / ``enrichment_status``."""
    async with SessionLocal() as session:
        company = await session.get(Company, company_id)
        if company is None:
            logger.warning("Ingest target %s no longer exists", company_id)
            return

        # A no-op on a first-time ingest; clears stale rows from a prior pass
        # when this is a refresh or a retry of a previously failed company.
        await session.execute(delete(CompanySource).where(CompanySource.company_id == company.id))

        try:
            await _log(session, company, "Fetching website")
            scrape = await scrape_company(company.url, max_pages=settings.scrape_max_pages)
            if not scrape.pages:
                company.status = CompanyStatus.failed
                company.enrichment_status = EnrichmentStatus.skipped
                await _log(session, company, "Could not fetch any pages from the site")
                return

            methods = sorted({p.method.value for p in scrape.pages})
            company.status = CompanyStatus.scraped
            await _log(
                session, company,
                f"Read {len(scrape.pages)} page(s)", detail=f"via {', '.join(methods)}",
            )

            await _log(session, company, "Extracting company profile with the LLM")
            llm = get_llm_client(settings)
            profile = await run_in_threadpool(extract_company_profile, scrape, llm)
            _apply_profile(company, profile)
            _attach_sources(session, company, scrape)
            company.status = CompanyStatus.extracted
            await _log(session, company, "Profile extracted", detail=profile.name)
        except Exception:  # noqa: BLE001 - a failed job must not tear the row
            logger.exception("Ingest failed for %s", company_id)
            await session.rollback()
            company = await session.get(Company, company_id)
            if company is not None:
                company.status = CompanyStatus.failed
                company.enrichment_status = EnrichmentStatus.skipped
                await _log(session, company, "Analysis failed")
            return

        if enrichment_enabled(settings):
            await _enrich_in_session(session, company, settings)


async def _enrich_in_session(
    session: AsyncSession, company: Company, settings: Settings
) -> None:
    """Search the web for supplemental firmographics and fold them in. Assumes
    the company is already ``extracted``; records its own progress + status."""
    company.enrichment_status = EnrichmentStatus.running
    await _log(
        session, company,
        "Searching the web for firmographics",
        detail="LinkedIn, PitchBook, Crunchbase, news",
    )
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
            await _log(
                session, company,
                "Enrichment complete", detail=_enrichment_summary(enrichment),
            )
        else:
            company.enrichment_status = EnrichmentStatus.done
            await _log(session, company, "No supplemental data found")
    except Exception:  # noqa: BLE001
        logger.exception("Enrichment failed for %s", company.id)
        await session.rollback()
        company = await session.get(Company, company.id)
        if company is not None:
            company.enrichment_status = EnrichmentStatus.failed
            await _log(session, company, "Enrichment failed")


async def run_company_match(
    company: Company,
    session: AsyncSession,
    settings: Settings,
    *,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[Match]:
    # `pending` funds have no mandate at all (regulatory data only, from bulk
    # EDGAR registration) — matching them would mean every one trivially
    # passes the forgiving hard-filter and lands an LLM thesis-judge call
    # with nothing to judge. Excluded until they've been through mandate
    # extraction and promoted to `ai_inferred`.
    funds = (
        await session.execute(
            select(Fund).where(Fund.mandate_source != MandateSource.pending)
        )
    ).scalars().all()
    app_settings = await get_or_create_settings(session)
    weights = weights_from_settings(app_settings)

    profile = company_to_profile(company)
    llm = _maybe_llm(settings)
    company_embedding = await _company_embedding(profile, settings)

    results = await run_match(
        profile,
        list(funds),
        weights=weights,
        llm=llm,
        company_embedding=company_embedding,
        on_progress=on_progress,
    )

    run_id = uuid.uuid4()
    await session.execute(delete(Match).where(Match.company_id == company.id))
    matches = [
        Match(
            company_id=company.id,
            fund_id=uuid.UUID(r.fund_id),
            run_id=run_id,
            passed_hard_filters=r.passed_hard_filters,
            mandate_score=r.mandate_score,
            strategy_score=r.strategy_score,
            value_creation_score=r.value_creation_score,
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
        growth_trajectory=company.growth_trajectory,
        deal_stage=company.deal_stage,
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
        "mandate": _f(row.weight_mandate) or DEFAULT_WEIGHTS["mandate"],
        "strategy": _f(row.weight_strategy) or DEFAULT_WEIGHTS["strategy"],
        "value_creation": _f(row.weight_value_creation)
        or DEFAULT_WEIGHTS["value_creation"],
    }


# -- enrichment -----------------------------------------------------------


def enrichment_enabled(settings: Settings) -> bool:
    return settings.enrich_source.lower() == "claude"


def _enrichment_summary(enrichment: CompanyEnrichment) -> str | None:
    bits: list[str] = []
    if enrichment.investors:
        bits.append(f"{len(enrichment.investors)} investor(s)")
    if enrichment.competitors:
        bits.append(f"{len(enrichment.competitors)} competitor(s)")
    if enrichment.revenue_estimate_usd_m is not None:
        bits.append(f"~${enrichment.revenue_estimate_usd_m:g}M revenue")
    if enrichment.size_employees is not None:
        bits.append(f"{enrichment.size_employees} employees")
    if enrichment.growth_trajectory:
        bits.append(enrichment.growth_trajectory)
    return ", ".join(bits) or None


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
    if not merged.growth_trajectory and enrichment.growth_trajectory:
        merged.growth_trajectory = enrichment.growth_trajectory
    if not merged.deal_stage and enrichment.deal_stage:
        merged.deal_stage = enrichment.deal_stage

    # Namespace enrichment confidences so they don't clobber extraction's.
    for key, value in (enrichment.confidence or {}).items():
        merged.confidence.setdefault(f"enriched.{key}", value)

    return merged


# -- internals ------------------------------------------------------------


def _maybe_llm(settings: Settings):
    try:
        return get_llm_client(settings)
    except LLMError as exc:
        logger.info("matching without LLM (%s); size-fit-only ranking", exc)
        return None


async def _company_embedding(profile: CompanyProfile, settings: Settings) -> list[float] | None:
    """Embed the company's profile once per match run for the semantic
    pre-filter. None (silently) without an OpenAI key — embeddings are an
    optimisation, matching still works on size fit alone without them."""
    text = company_embedding_text(profile)
    if text is None:
        return None
    return await run_in_threadpool(
        embed_text, text, api_key=settings.openai_api_key, model=settings.openai_embedding_model
    )


def _apply_enrichment_fields(company: Company, merged: CompanyProfile) -> None:
    """Persist only the fields enrichment can fill; ``merge_enrichment`` has
    already enforced that website values win, so this is a straight write.
    ``raw_extracted`` (the original extraction output) is left untouched."""
    company.size_employees = merged.size_employees
    company.revenue_estimate_usd_m = merged.revenue_estimate_usd_m
    company.ownership_status = merged.ownership_status
    company.investors = merged.investors
    company.competitors = merged.competitors
    company.growth_trajectory = merged.growth_trajectory
    company.deal_stage = merged.deal_stage
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
    company.growth_trajectory = profile.growth_trajectory
    company.deal_stage = profile.deal_stage
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


def _event(label: str, detail: str | None = None) -> dict:
    return {
        "label": label,
        "detail": detail,
        "at": datetime.now(timezone.utc).isoformat(),
    }


async def _log(
    session: AsyncSession, company: Company, label: str, detail: str | None = None
) -> None:
    """Append an activity entry and commit so pollers see it promptly.
    Reassigns the list (rather than mutating) so SQLAlchemy flags it dirty."""
    company.progress = [*(company.progress or []), _event(label, detail)]
    await session.commit()


def _f(value) -> float | None:
    return float(value) if value is not None else None
