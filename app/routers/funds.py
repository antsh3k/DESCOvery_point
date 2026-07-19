"""Fund endpoints: list, manual create, and create-from-URL (extract + confirm)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.config import Settings, get_settings
from app.db import get_session
from app.enums import FundProvenance, MandateSource
from app.models import Fund
from app.schemas.fund import FundCreate, FundFromURL, FundRead
from app.services.llm import LLMError, get_llm_client
from app.services.scraper import scrape_company

router = APIRouter(prefix="/funds", tags=["funds"])


@router.get("", response_model=list[FundRead])
async def list_funds(session: AsyncSession = Depends(get_session)) -> list[Fund]:
    rows = (await session.execute(select(Fund).order_by(Fund.name))).scalars().all()
    return list(rows)


@router.post("", response_model=FundRead, status_code=status.HTTP_201_CREATED)
async def create_fund(
    payload: FundCreate,
    session: AsyncSession = Depends(get_session),
) -> Fund:
    fund = Fund(
        **payload.model_dump(),
        provenance=FundProvenance.manual,
        mandate_source=MandateSource.authoritative,
    )
    session.add(fund)
    await session.commit()
    await session.refresh(fund)
    return fund


@router.post("/from-url", response_model=FundRead, status_code=status.HTTP_201_CREATED)
async def create_fund_from_url(
    payload: FundFromURL,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Fund:
    """Scrape a fund site, LLM-extract its mandate, and store it for confirmation.

    Saved as ``url_extracted`` / ``ai_inferred`` — the dashboard flags it so the
    user can review before relying on it.
    """
    scrape = await scrape_company(payload.url, max_pages=settings.scrape_max_pages)
    if not scrape.pages:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not fetch any pages from {payload.url}",
        )
    try:
        llm = get_llm_client(settings)
        mandate = await run_in_threadpool(
            llm.extract_fund, text=scrape.text[:20_000], source_url=payload.url
        )
    except LLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    fund = Fund(
        **mandate.model_dump(),
        provenance=FundProvenance.url_extracted,
        mandate_source=MandateSource.ai_inferred,
        mandate_confidence=None,
    )
    fund.source_url = fund.source_url or payload.url
    session.add(fund)
    await session.commit()
    await session.refresh(fund)
    return fund


@router.get("/{fund_id}", response_model=FundRead)
async def get_fund(
    fund_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Fund:
    fund = await session.get(Fund, fund_id)
    if fund is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found")
    return fund
