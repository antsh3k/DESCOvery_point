"""Company ingest + read endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_session
from app.enums import EnrichmentStatus
from app.models import Company
from app.schemas.company import CompanyCreate, CompanyListItem, CompanyRead
from app.services.pipeline import (
    ExtractionError,
    ingest_and_extract,
    run_company_enrichment,
)

router = APIRouter(prefix="/companies", tags=["companies"])


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: CompanyCreate,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Company:
    try:
        company = await ingest_and_extract(payload.url, session, settings)
    except ExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    # Fire enrichment after the response is sent; the client polls the company
    # until enrichment_status leaves 'pending'/'running'.
    if company.enrichment_status == EnrichmentStatus.pending:
        background.add_task(run_company_enrichment, company.id, settings)
    return company


@router.get("", response_model=list[CompanyListItem])
async def list_companies(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=12, ge=1, le=100),
) -> list[Company]:
    """Most-recent analyses first — powers the landing page history."""
    rows = await session.execute(
        select(Company).order_by(Company.created_at.desc()).limit(limit)
    )
    return list(rows.scalars().all())


@router.get("/{company_id}", response_model=CompanyRead)
async def get_company(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Company:
    company = await session.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company
