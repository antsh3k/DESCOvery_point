"""Parse the downloaded Form ADV bulk export (Nov 2011-Dec 2024, ERA + IA)
into fund candidates.

Schema (reverse-engineered against the real bulk files — SEC ships no public
data dictionary for the CSV column layout, only the PDF form instructions):

- ``*_ADV_Base*.csv`` — one row per filing amendment, keyed by ``FilingID``.
  ``1A`` = adviser legal name, ``1E1`` = CRD number, ``DateSubmitted`` = when
  filed (used to pick each fund's most recent record across amendments).
- ``*_Schedule_D_1I.csv`` — the adviser's own website(s), keyed by
  ``FilingID``.
- ``*_Schedule_D_7B1.csv`` — the core private-fund table: one row per private
  fund an adviser discloses, keyed by ``FilingID`` + ``ReferenceID``, with a
  stable ``Fund ID`` (an "805-" identifier) across amendments, ``Fund Name``,
  ``Fund Type`` ("Private Equity Fund" / "Hedge Fund" / "Venture Capital
  Fund" / ...), and ``Gross Asset Value``.
- ``*_Schedule_D_7B1A28_websites.csv`` — the fund's *own* website(s), keyed
  by ``ReferenceID`` (preferred over the adviser's site when present).
- ``*_Schedule_D_7B1A23.csv`` — the fund's auditor ("Name of Auditing Firm"),
  keyed by ``ReferenceID``.
- ``*_Schedule_D_7B1A24.csv`` — the fund's prime broker ("Name of Prime
  Broker") and whether it also custodies assets ("Custodian" Y/N), keyed by
  ``ReferenceID``.

Both the ERA (Exempt Reporting Adviser) and IA (registered Investment
Adviser) file families share this layout under different filename prefixes.
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path

from app.services.edgar.candidates import FundCandidate

logger = logging.getLogger(__name__)

_TARGET_FUND_TYPE = "Private Equity Fund"
_IAPD_FIRM_URL = "https://adviserinfo.sec.gov/firm/summary/{crd}"
_PREFIXES = ("ERA", "IA")


def parse_form_adv(bulk_dir: Path) -> list[FundCandidate]:
    """Return one candidate per unique Private-Equity Fund ID across both the
    ERA and IA file families, deduped to each fund's most recent filing."""
    advisers = _load_advisers(bulk_dir)
    adviser_websites = _load_keyed_values(bulk_dir, "Schedule_D_1I", key_field="FilingID")
    fund_websites = _load_keyed_values(
        bulk_dir, "Schedule_D_7B1A28_websites", key_field="ReferenceID", value_field="Website Address"
    )
    auditors = _load_keyed_values(
        bulk_dir, "Schedule_D_7B1A23", key_field="ReferenceID", value_field="Name of Auditing Firm"
    )
    prime_brokers = _load_keyed_values(
        bulk_dir, "Schedule_D_7B1A24", key_field="ReferenceID", value_field="Name of Prime Broker"
    )
    custodian_flags = _load_keyed_values(
        bulk_dir, "Schedule_D_7B1A24", key_field="ReferenceID", value_field="Custodian"
    )

    best: dict[str, tuple[datetime, FundCandidate]] = {}
    for prefix in _PREFIXES:
        path = _find(bulk_dir, f"{prefix}_Schedule_D_7B1_")
        if path is None:
            logger.warning("No %s_Schedule_D_7B1 file found under %s", prefix, bulk_dir)
            continue
        _accumulate(
            path, advisers, adviser_websites, fund_websites, auditors, prime_brokers,
            custodian_flags, best,
        )

    candidates = [candidate for _, candidate in best.values()]
    logger.info("Form ADV bulk data: %d private-equity-fund candidate(s)", len(candidates))
    return candidates


def _accumulate(
    path: Path,
    advisers: dict[str, dict],
    adviser_websites: dict[str, str],
    fund_websites: dict[str, str],
    auditors: dict[str, str],
    prime_brokers: dict[str, str],
    custodian_flags: dict[str, str],
    best: dict[str, tuple[datetime, FundCandidate]],
) -> None:
    skipped_no_adviser = 0
    with path.open(encoding="latin-1", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("Fund Type") != _TARGET_FUND_TYPE:
                continue
            fund_id = row.get("Fund ID")
            if not fund_id:
                continue
            filing_id = row["FilingID"]
            adviser = advisers.get(filing_id)
            if adviser is None:
                skipped_no_adviser += 1
                continue

            existing = best.get(fund_id)
            if existing is not None and existing[0] >= adviser["date"]:
                continue

            reference_id = row.get("ReferenceID", "")
            website = fund_websites.get(reference_id) or adviser_websites.get(filing_id)
            custodian_flag = custodian_flags.get(reference_id)
            candidate = FundCandidate(
                name=row["Fund Name"],
                firm=adviser["name"],
                website_url=_normalize_url(website),
                source_url=_IAPD_FIRM_URL.format(crd=adviser["crd"]),
                state=row.get("State") or None,
                country=row.get("Country") or None,
                significance=_parse_amount(row.get("Gross Asset Value")),
                origin="form_adv",
                fund_type_raw=row.get("Fund Type") or None,
                gross_asset_value_usd=_parse_amount(row.get("Gross Asset Value")) or None,
                investor_count=_parse_int(row.get("Owners")),
                filing_date=adviser["date"].date() if adviser["date"] > datetime.min else None,
                auditor_name=auditors.get(reference_id),
                prime_broker_name=prime_brokers.get(reference_id),
                custodian_name=prime_brokers.get(reference_id) if custodian_flag == "Y" else None,
                regulatory_id=fund_id,
            )
            best[fund_id] = (adviser["date"], candidate)

    if skipped_no_adviser:
        logger.info("%s: skipped %d fund row(s) with no matching adviser filing", path.name, skipped_no_adviser)


def _load_advisers(bulk_dir: Path) -> dict[str, dict]:
    """FilingID -> {name, crd, date}, from every *_ADV_Base*.csv file.

    ``IA_ADV_Base_B`` is a distinct file (state registration checkboxes) that
    happens to match a loose "*ADV_Base*" glob but shares none of the columns
    read here — explicitly excluded rather than crashing on a missing key.
    """
    advisers: dict[str, dict] = {}
    for path in sorted(bulk_dir.glob("*ADV_Base*.csv")):
        if "_Base_B_" in path.name:
            continue
        with path.open(encoding="latin-1", newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            idx = {name: i for i, name in enumerate(header)}
            i_filing, i_name, i_crd, i_date = (
                idx["FilingID"], idx["1A"], idx["1E1"], idx["DateSubmitted"],
            )
            for row in reader:
                advisers[row[i_filing]] = {
                    "name": row[i_name],
                    "crd": row[i_crd],
                    "date": _parse_date(row[i_date]),
                }
        logger.info("Loaded %d adviser filing(s) from %s", len(advisers), path.name)
    return advisers


def _load_keyed_values(
    bulk_dir: Path, filename_fragment: str, *, key_field: str, value_field: str = "Website"
) -> dict[str, str]:
    """Build {key_field value -> first value_field value} across every matching file."""
    out: dict[str, str] = {}
    for path in sorted(bulk_dir.glob(f"*{filename_fragment}*.csv")):
        with path.open(encoding="latin-1", newline="") as f:
            for row in csv.DictReader(f):
                key = row.get(key_field)
                site = row.get(value_field)
                if key and site and key not in out:
                    out[key] = site
    return out


def _find(bulk_dir: Path, filename_fragment: str) -> Path | None:
    matches = list(bulk_dir.glob(f"*{filename_fragment}*.csv"))
    return matches[0] if matches else None


def _parse_date(raw: str) -> datetime:
    # ERA filings use a bare date ("11/13/2012"); IA (registered adviser)
    # filings append a timestamp ("03/30/2015 12:12:27 PM").
    for fmt in ("%m/%d/%Y", "%m/%d/%Y %I:%M:%S %p"):
        try:
            return datetime.strptime(raw, fmt)
        except (ValueError, TypeError):
            continue
    return datetime.min


def _parse_amount(raw: str | None) -> float:
    if not raw:
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _parse_int(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def _normalize_url(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    if not raw.lower().startswith(("http://", "https://")):
        raw = f"https://{raw}"
    return raw
