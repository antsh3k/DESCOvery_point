"""Orchestrates the EDGAR fund-ingestion pipeline: gather candidates from
Form D / Form ADV, skip anything already in the DB, infer a mandate for each
new one (bounded concurrency, hard limit), and insert as ``Fund`` rows.

Never fabricates a mandate — every field still comes from ``extract_fund``
reading the fund's own site (or is left null), same as the manual
``/funds/from-url`` flow. What EDGAR contributes is the *candidate universe*:
real, currently-active fund identities, discovered from authoritative
regulatory filings instead of hand curation.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select

from app.config import Settings, get_settings
from app.db import SessionLocal
from app.enums import FundProvenance, MandateSource
from app.models import Fund
from app.services.edgar.candidates import FundCandidate, merge_candidates, normalize_name
from app.services.edgar.mandate import infer_mandate, resolve_website
from app.services.edgar.parse_form_adv import parse_form_adv
from app.services.edgar.parse_form_d import parse_form_d
from app.services.llm import LLMError, get_llm_client

logger = logging.getLogger(__name__)

# ai_inferred from scraping the adviser's own site (same as url_extracted
# funds), but the site was never hand-reviewed for this specific vehicle —
# a bit lower than a human-confirmed url_extracted fund would earn.
_EDGAR_CONFIDENCE = 0.6
_CONCURRENCY = 8
# Generous headroom over `limit` so no-website / scrape / extract failures
# don't stall short of the target — see ``skipped_by_cap`` for what's dropped.
_ATTEMPT_BUDGET_MULTIPLIER = 4


@dataclass
class IngestStats:
    candidates_found: int = 0
    skipped_existing: int = 0
    skipped_by_cap: int = 0
    attempted: int = 0
    added: int = 0
    skipped_no_website: int = 0
    skipped_scrape_or_extract_failed: int = 0
    skipped_insert_failed: int = 0
    added_names: list[str] = field(default_factory=list)


@dataclass
class BackfillStats:
    candidates_found: int = 0
    matched: int = 0
    unmatched: int = 0
    updated_names: list[str] = field(default_factory=list)


def _gather_candidates(
    form_d_quarters: list[str], include_form_adv: bool, settings: Settings
) -> list[FundCandidate]:
    data_dir = Path(settings.edgar_data_dir)
    candidate_groups: list[list[FundCandidate]] = []
    for quarter in form_d_quarters:
        quarter_dir = data_dir / "form_d" / quarter
        if quarter_dir.exists():
            candidate_groups.append(parse_form_d(quarter_dir))
        else:
            logger.warning("Form D quarter %s not downloaded; skipping", quarter)
    if include_form_adv:
        adv_dir = data_dir / "form_adv"
        if adv_dir.exists():
            candidate_groups.append(parse_form_adv(adv_dir))
        else:
            logger.warning("Form ADV bulk data not downloaded; skipping")
    return merge_candidates(*candidate_groups) if candidate_groups else []


async def backfill_regulatory_metadata(
    *,
    form_d_quarters: list[str],
    include_form_adv: bool,
    settings: Settings | None = None,
) -> BackfillStats:
    """Re-parse the bulk data and fill in regulatory fields (gross assets,
    investor count, auditor, prime broker, custodian, filing date, ...) on
    existing ``provenance=edgar`` funds, matched by normalized name.

    Pure CSV parsing + a DB update — no scraping, no LLM calls, safe to
    re-run any time the parsers gain new fields without repeating the slow
    scrape+extract step.
    """
    settings = settings or get_settings()
    stats = BackfillStats()

    candidates = _gather_candidates(form_d_quarters, include_form_adv, settings)
    stats.candidates_found = len(candidates)
    if not candidates:
        logger.warning("No candidate sources available — nothing to backfill")
        return stats
    by_name = {c.dedupe_key: c for c in candidates}

    async with SessionLocal() as session:
        funds = (
            await session.execute(select(Fund).where(Fund.provenance == FundProvenance.edgar))
        ).scalars().all()
        for fund in funds:
            candidate = by_name.get(normalize_name(fund.name))
            if candidate is None:
                stats.unmatched += 1
                continue
            fund.fund_type_raw = candidate.fund_type_raw
            fund.gross_asset_value_usd = candidate.gross_asset_value_usd
            fund.amount_raised_usd = candidate.amount_raised_usd
            fund.investor_count = candidate.investor_count
            fund.filing_date = candidate.filing_date
            fund.auditor_name = candidate.auditor_name
            fund.prime_broker_name = candidate.prime_broker_name
            fund.custodian_name = candidate.custodian_name
            fund.regulatory_id = candidate.regulatory_id
            stats.matched += 1
            stats.updated_names.append(fund.name)
        await session.commit()

    logger.info(
        "Backfill done: candidates=%d matched=%d unmatched=%d",
        stats.candidates_found, stats.matched, stats.unmatched,
    )
    return stats


async def ingest_edgar_funds(
    *,
    form_d_quarters: list[str],
    include_form_adv: bool,
    limit: int,
    settings: Settings | None = None,
) -> IngestStats:
    settings = settings or get_settings()
    stats = IngestStats()

    candidates = _gather_candidates(form_d_quarters, include_form_adv, settings)
    stats.candidates_found = len(candidates)
    if not candidates:
        logger.warning("No candidate sources available — nothing to ingest")
        return stats
    # Website-known candidates first (cheaper, more reliable than a
    # web_search resolution); AUM / offering size as the tiebreaker.
    candidates.sort(key=lambda c: (c.website_url is None, -c.significance))

    try:
        llm = get_llm_client(settings)
    except LLMError as exc:
        logger.warning("No LLM configured (%s); cannot infer mandates", exc)
        return stats

    async with SessionLocal() as session:
        existing_names = {
            normalize_name(n)
            for n in (await session.execute(select(Fund.name))).scalars().all()
        }

    fresh = [c for c in candidates if c.dedupe_key not in existing_names]
    stats.skipped_existing = len(candidates) - len(fresh)

    attempt_budget = limit * _ATTEMPT_BUDGET_MULTIPLIER
    queue = fresh[:attempt_budget]
    stats.skipped_by_cap = len(fresh) - len(queue)
    if stats.skipped_by_cap:
        logger.info(
            "Capping attempts at %d of %d fresh candidates (raise --limit to reach more)",
            attempt_budget, len(fresh),
        )

    sem = asyncio.Semaphore(_CONCURRENCY)
    lock = asyncio.Lock()

    async def _worker(candidate: FundCandidate) -> None:
        async with sem:
            async with lock:
                if stats.added >= limit:
                    return
                stats.attempted += 1

            website = candidate.website_url
            if not website:
                website = await resolve_website(
                    candidate, api_key=settings.anthropic_api_key, model=settings.anthropic_model
                )
            if not website:
                stats.skipped_no_website += 1
                return

            mandate = await infer_mandate(
                candidate, website, llm=llm, max_pages=settings.scrape_max_pages
            )
            if mandate is None:
                stats.skipped_scrape_or_extract_failed += 1
                return

            async with lock:
                if stats.added >= limit:
                    return
                try:
                    async with SessionLocal() as session:
                        fund = Fund(
                            **mandate.model_dump(),
                            provenance=FundProvenance.edgar,
                            mandate_source=MandateSource.ai_inferred,
                            mandate_confidence=_EDGAR_CONFIDENCE,
                            fund_type_raw=candidate.fund_type_raw,
                            gross_asset_value_usd=candidate.gross_asset_value_usd,
                            amount_raised_usd=candidate.amount_raised_usd,
                            investor_count=candidate.investor_count,
                            filing_date=candidate.filing_date,
                            auditor_name=candidate.auditor_name,
                            prime_broker_name=candidate.prime_broker_name,
                            custodian_name=candidate.custodian_name,
                            regulatory_id=candidate.regulatory_id,
                        )
                        session.add(fund)
                        await session.commit()
                except Exception as exc:  # noqa: BLE001 - a bad row must not abort the batch
                    logger.warning("Insert failed for %r: %s", mandate.name, exc)
                    stats.skipped_insert_failed += 1
                    return
                stats.added += 1
                stats.added_names.append(mandate.name)
                logger.info("Added %r (%d/%d)", mandate.name, stats.added, limit)

    await asyncio.gather(*(_worker(c) for c in queue))

    logger.info(
        "EDGAR ingest done: found=%d skipped_existing=%d skipped_by_cap=%d "
        "attempted=%d added=%d skipped_no_website=%d skipped_scrape_or_extract_failed=%d",
        stats.candidates_found, stats.skipped_existing, stats.skipped_by_cap,
        stats.attempted, stats.added, stats.skipped_no_website,
        stats.skipped_scrape_or_extract_failed,
    )
    return stats
