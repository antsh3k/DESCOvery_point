"""Company ingest + read endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_session
from app.models import Company
from app.schemas.company import CompanyCreate, CompanyRead
from app.services.pipeline import ExtractionError, ingest_and_extract

router = APIRouter(prefix="/companies", tags=["companies"])


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: CompanyCreate,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Company:
    try:
        return await ingest_and_extract(payload.url, session, settings)
    except ExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc


@router.get("/{company_id}", response_model=CompanyRead)
async def get_company(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Company:
    company = await session.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company
