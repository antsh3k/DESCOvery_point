"""CLI entry point for EDGAR fund ingestion.

Downloads (or reuses cached) SEC bulk data, discovers Private-Equity-Fund
candidates, infers a mandate for each new one, and inserts it as a Fund row::

    uv run ingest-edgar
    uv run ingest-edgar --source form_d --quarter 2026q2 --limit 20
    uv run ingest-edgar --skip-download  # reuse whatever's already cached

``--backfill-metadata`` re-parses the bulk data and fills in regulatory
fields (gross assets, investor count, auditor, prime broker, custodian,
filing date) on funds already in the DB, matched by name. Pure CSV parsing —
no scraping, no LLM calls — safe to re-run any time the parsers gain fields::

    uv run ingest-edgar --backfill-metadata

``--bulk-register`` registers every fresh candidate as a Fund row with full
regulatory metadata but no investment mandate (``mandate_source=pending`` —
sectors/check-size/thesis stay empty until a later scrape+extract pass).
Pure CSV parsing + DB inserts, so it scales to the whole ~55k-candidate ADV
pool in minutes rather than the hours the mandate pipeline would take::

    uv run ingest-edgar --bulk-register            # register everything fresh
    uv run ingest-edgar --bulk-register --limit 5000
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from app.config import get_settings
from app.services.edgar.fetch import download_form_adv, download_form_d
from app.services.edgar.ingest import (
    backfill_regulatory_metadata,
    bulk_register_funds,
    ingest_edgar_funds,
)

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
    parser.add_argument(
        "--backfill-metadata",
        action="store_true",
        help="Fill in regulatory fields on existing funds instead of ingesting new ones "
        "(no scraping/LLM calls — safe and fast to re-run)",
    )
    parser.add_argument(
        "--bulk-register",
        action="store_true",
        help="Register every fresh candidate with regulatory data but no mandate "
        "(mandate_source=pending) instead of the slow scrape+LLM pipeline. "
        "--limit here means 'how many to register' (default: unbounded).",
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

    if args.backfill_metadata:
        stats = await backfill_regulatory_metadata(
            form_d_quarters=quarters if include_form_d else [],
            include_form_adv=include_form_adv,
            settings=settings,
        )
        logger.info(
            "Backfilled %d fund(s) (%d unmatched): %s",
            stats.matched, stats.unmatched, ", ".join(stats.updated_names) or "(none)",
        )
        return

    if args.bulk_register:
        stats = await bulk_register_funds(
            form_d_quarters=quarters if include_form_d else [],
            include_form_adv=include_form_adv,
            limit=args.limit,
            settings=settings,
        )
        logger.info(
            "Bulk-registered %d fund(s) (found=%d, skipped_existing=%d)",
            stats.registered, stats.candidates_found, stats.skipped_existing,
        )
        return

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
