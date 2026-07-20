"""CLI entry point for EDGAR fund ingestion.

Downloads (or reuses cached) SEC bulk data, discovers Private-Equity-Fund
candidates, infers a mandate for each new one, and inserts it as a Fund row::

    uv run ingest-edgar
    uv run ingest-edgar --source form_d --quarter 2026q2 --limit 20
    uv run ingest-edgar --skip-download  # reuse whatever's already cached
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from app.config import get_settings
from app.services.edgar.fetch import download_form_adv, download_form_d
from app.services.edgar.ingest import ingest_edgar_funds

logger = logging.getLogger(__name__)

_DEFAULT_QUARTERS = ["2026q2"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=["form_d", "form_adv", "both"],
        default="both",
        help="Which EDGAR dataset(s) to ingest from (default: both)",
    )
    parser.add_argument(
        "--quarter",
        action="append",
        dest="quarters",
        default=None,
        help=f"Form D quarter to use, e.g. 2026q2 (repeatable; default: {_DEFAULT_QUARTERS})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max new funds to add (default: settings.edgar_ingest_limit)",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Reuse whatever is already cached under settings.edgar_data_dir instead of re-fetching",
    )
    return parser.parse_args()


async def _main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = _parse_args()
    settings = get_settings()

    quarters = args.quarters or _DEFAULT_QUARTERS
    include_form_d = args.source in ("form_d", "both")
    include_form_adv = args.source in ("form_adv", "both")

    if not args.skip_download:
        if include_form_d:
            for quarter in quarters:
                download_form_d(quarter, settings=settings)
        if include_form_adv:
            download_form_adv(settings=settings)

    stats = await ingest_edgar_funds(
        form_d_quarters=quarters if include_form_d else [],
        include_form_adv=include_form_adv,
        limit=args.limit or settings.edgar_ingest_limit,
        settings=settings,
    )
    logger.info("Added %d fund(s): %s", stats.added, ", ".join(stats.added_names) or "(none)")


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
