"""Async database engine, session factory, and declarative base.

The same ``postgresql+psycopg`` URL drives both the async app engine (here) and
the sync engine Alembic uses for migrations — psycopg 3 supports both modes.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


_settings = get_settings()

engine = create_async_engine(_settings.database_url, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a scoped async session."""
    async with SessionLocal() as session:
        yield session
