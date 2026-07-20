"""Matching endpoints: run the engine, read persisted results.

``POST /match`` streams progress as newline-delimited JSON rather than
blocking silently for the ~1-2 minutes a large fund universe can take — the
LLM judge (Stage 3) is the slow part, so progress is reported per fund judged.
Each line is one JSON object:

    {"type": "start", "total_funds": 4207}
    {"type": "progress", "done": 12, "total": 87}
    ...
    {"type": "done", "matches": [...]}   # same shape as GET /matches
    {"type": "error", "detail": "..."}    # instead of "done", on failure
"""

from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_session
from app.models import Company, Match
from app.schemas.match import MatchRead
from app.services.pipeline import run_company_match

router = APIRouter(prefix="/companies/{company_id}", tags=["matches"])


@router.post("/match")
async def match_company(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    company = await session.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    return StreamingResponse(
        _match_stream(company, session, settings), media_type="application/x-ndjson"
    )


async def _match_stream(company: Company, session: AsyncSession, settings: Settings):
    queue: asyncio.Queue = asyncio.Queue()

    def on_progress(done: int, total: int) -> None:
        queue.put_nowait({"type": "progress", "done": done, "total": total})

    async def run() -> None:
        try:
            matches = await run_company_match(
                company, session, settings, on_progress=on_progress
            )
            shortlist = _shortlist(matches)
            await queue.put(
                {
                    "type": "done",
                    "matches": [
                        MatchRead.model_validate(m).model_dump(mode="json")
                        for m in shortlist
                    ],
                }
            )
        except Exception as exc:  # noqa: BLE001 - surface to the client, don't crash the stream
            await queue.put({"type": "error", "detail": str(exc)})

    yield json.dumps({"type": "start"}) + "\n"
    task = asyncio.create_task(run())
    while True:
        item = await queue.get()
        yield json.dumps(item) + "\n"
        if item["type"] in ("done", "error"):
            break
    await task


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
