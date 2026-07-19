"""Read/update application settings (weights, provider, scrape config)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import AppSettings
from app.schemas.settings import SettingsRead, SettingsUpdate
from app.services.pipeline import get_or_create_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsRead)
async def read_settings(session: AsyncSession = Depends(get_session)) -> AppSettings:
    return await get_or_create_settings(session)


@router.put("", response_model=SettingsRead)
async def update_settings(
    payload: SettingsUpdate,
    session: AsyncSession = Depends(get_session),
) -> AppSettings:
    row = await get_or_create_settings(session)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(row, field, value)
    await session.commit()
    await session.refresh(row)
    return row
