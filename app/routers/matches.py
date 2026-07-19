"""Matching endpoints: run the engine, read persisted results."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_session
from app.models import Company, Match
from app.schemas.match import MatchRead
from app.services.pipeline import run_company_match

router = APIRouter(prefix="/companies/{company_id}", tags=["matches"])


@router.post("/match", response_model=list[MatchRead])
async def match_company(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> list[Match]:
    company = await session.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    matches = await run_company_match(company, session, settings)
    return _shortlist(matches)


@router.get("/matches", response_model=list[MatchRead])
async def list_matches(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> list[Match]:
    rows = (
        await session.execute(
            select(Match).where(Match.company_id == company_id)
        )
    ).scalars().all()
    return _shortlist(list(rows))


def _shortlist(matches: list[Match]) -> list[Match]:
    """Passed matches, ranked; unranked/failed excluded from the shortlist."""
    ranked = [m for m in matches if m.passed_hard_filters and m.rank is not None]
    ranked.sort(key=lambda m: m.rank)
    return ranked
