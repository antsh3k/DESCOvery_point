"""Company ingest + read endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_session
from app.models import Company
from app.schemas.company import CompanyCreate, CompanyListItem, CompanyRead
from app.services.pipeline import create_pending_company, run_company_ingest

router = APIRouter(prefix="/companies", tags=["companies"])


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: CompanyCreate,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Company:
    """Return a shell company immediately; the scrape → extract → enrich
    pipeline runs in the background. The client polls status / progress."""
    url = payload.url.strip()
    if not url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="URL is required"
        )
    company = await create_pending_company(url, session, settings)
    background.add_task(run_company_ingest, company.id, settings)
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
