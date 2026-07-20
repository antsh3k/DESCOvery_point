"""CLI entry point for the fund-embeddings backfill.

Computes + stores ``thesis_embedding`` for every fund with mandate text
(thesis/sectors/stage) that doesn't have one yet — pure embedding calls, no
LLM generation, safe and cheap to re-run::

    uv run backfill-embeddings
"""

from __future__ import annotations

import asyncio
import logging

from app.config import get_settings
from app.services.matching.embeddings import backfill_fund_embeddings

logger = logging.getLogger(__name__)


async def _main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY is not set — nothing to do")
        return
    stats = await backfill_fund_embeddings(
        api_key=settings.openai_api_key, model=settings.openai_embedding_model
    )
    logger.info("Done: %s", stats)


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
