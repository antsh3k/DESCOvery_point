"""Parse a downloaded Form D quarterly bulk export into fund candidates.

Schema (verified against the real 2026Q2 dataset from
https://www.sec.gov/data-research/sec-markets-data/form-d-data-sets):

- ``OFFERING.tsv`` — one row per Form D filing's offering details, keyed by
  ``ACCESSIONNUMBER``. ``INDUSTRYGROUPTYPE`` / ``INVESTMENTFUNDTYPE`` classify
  pooled investment funds ("Private Equity Fund", "Hedge Fund", "Venture
  Capital Fund", "Other Investment Fund").
- ``ISSUERS.tsv`` — the filing issuer (the fund entity itself for a pooled
  fund), keyed by the same ``ACCESSIONNUMBER``, with ``CIK``/``ENTITYNAME``/
  address fields.
- ``FORMDSUBMISSION.tsv`` — one row per filing, keyed by ``ACCESSIONNUMBER``,
  with ``FILING_DATE`` (format ``DD-MON-YYYY``, e.g. ``30-JUN-2026``).

Form D carries no website field for the issuer, so every candidate here needs
website resolution (see ``mandate.py``) before it can be scraped. Its
``TOTALOFFERINGAMOUNT`` is capital *raised* in this offering — a related but
distinct figure from Form ADV's Gross Asset Value (current fund AUM).
"""

from __future__ import annotations

import csv
import logging
from datetime import date, datetime
from pathlib import Path

from app.services.edgar.candidates import FundCandidate

logger = logging.getLogger(__name__)

_TARGET_INDUSTRY_GROUP = "Pooled Investment Fund"
_TARGET_FUND_TYPE = "Private Equity Fund"
_EDGAR_COMPANY_URL = (
    "https://www.sec.gov/cgi-bin/browse-edgar"
    "?action=getcompany&CIK={cik}&type=D&dateb=&owner=include&count=40"
)


def parse_form_d(quarter_dir: Path) -> list[FundCandidate]:
    """Return one candidate per Private-Equity-Fund issuer in this quarter."""
    issuers = _load_issuers(quarter_dir / "ISSUERS.tsv")
    filing_dates = _load_filing_dates(quarter_dir / "FORMDSUBMISSION.tsv")

    candidates: list[FundCandidate] = []
    skipped_no_issuer = 0
    with (quarter_dir / "OFFERING.tsv").open(encoding="latin-1", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if (
                row.get("INDUSTRYGROUPTYPE") != _TARGET_INDUSTRY_GROUP
                or row.get("INVESTMENTFUNDTYPE") != _TARGET_FUND_TYPE
            ):
                continue
            issuer = issuers.get(row["ACCESSIONNUMBER"])
            if issuer is None:
                skipped_no_issuer += 1
                continue
            amount_raised = _parse_amount(row.get("TOTALOFFERINGAMOUNT"))
            candidates.append(
                FundCandidate(
                    name=issuer["name"],
                    firm=None,
                    website_url=None,
                    source_url=_EDGAR_COMPANY_URL.format(cik=issuer["cik"]),
                    state=None,
                    country=issuer["location"],
                    significance=amount_raised,
                    origin="form_d",
                    fund_type_raw=row.get("INVESTMENTFUNDTYPE") or None,
                    amount_raised_usd=amount_raised or None,
                    filing_date=filing_dates.get(row["ACCESSIONNUMBER"]),
                    regulatory_id=issuer["cik"],
                )
            )

    if skipped_no_issuer:
        logger.info(
            "Form D %s: skipped %d offering row(s) with no matching issuer",
            quarter_dir.name,
            skipped_no_issuer,
        )
    logger.info(
        "Form D %s: %d private-equity-fund candidate(s)", quarter_dir.name, len(candidates)
    )
    return candidates


def _load_issuers(path: Path) -> dict[str, dict]:
    issuers: dict[str, dict] = {}
    with path.open(encoding="latin-1", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row.get("IS_PRIMARYISSUER_FLAG", "").upper() != "YES":
                continue
            issuers[row["ACCESSIONNUMBER"]] = {
                "cik": row["CIK"].lstrip("0") or "0",
                "name": row["ENTITYNAME"],
                # STATEORCOUNTRYDESCRIPTION is always human-readable (a US
                # state name, or a country name for foreign filers); the
                # paired STATEORCOUNTRY is a terse code, not worth surfacing.
                "location": row.get("STATEORCOUNTRYDESCRIPTION") or None,
            }
    return issuers


def _load_filing_dates(path: Path) -> dict[str, date]:
    dates: dict[str, date] = {}
    with path.open(encoding="latin-1", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            parsed = _parse_filing_date(row.get("FILING_DATE"))
            if parsed is not None:
                dates[row["ACCESSIONNUMBER"]] = parsed
    return dates


def _parse_filing_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%d-%b-%Y").date()
    except ValueError:
        return None


def _parse_amount(raw: str | None) -> float:
    if not raw:
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0  # e.g. "Indefinite"
