"""Load the curated fund seed into Postgres.

Idempotent: funds already present (matched by name) are skipped. Run with::

    uv run seed
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.enums import FundProvenance, MandateSource
from app.models import Fund

logger = logging.getLogger(__name__)

_SEED_FILE = Path(__file__).with_name("funds_seed.json")


async def load_seed() -> int:
    """Insert any seed funds not already present. Returns the number inserted."""
    records = json.loads(_SEED_FILE.read_text())
    inserted = 0
    async with SessionLocal() as session:
        existing = set(
            (await session.execute(select(Fund.name))).scalars().all()
        )
        for record in records:
            if record["name"] in existing:
                continue
            session.add(
                Fund(
                    **record,
                    provenance=FundProvenance.seed,
                    mandate_source=MandateSource.authoritative,
                    mandate_confidence=1.0,
                )
            )
            inserted += 1
        await session.commit()
    return inserted


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    count = asyncio.run(load_seed())
    logger.info("Seed complete: %d fund(s) inserted", count)


if __name__ == "__main__":
    main()
