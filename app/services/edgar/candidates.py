"""Shared candidate record produced by the Form D / Form ADV parsers, before
mandate inference and before it becomes a ``Fund`` row.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from datetime import date


@dataclass(slots=True)
class FundCandidate:
    """A real private-equity fund entity discovered in EDGAR bulk data.

    ``website_url`` is the best known site for the fund itself or its adviser
    (may be ``None`` — resolved via search before mandate inference).
    ``source_url`` is always set to an authoritative SEC/IAPD page.
    ``significance`` is a sort proxy (gross asset value / offering amount, in
    USD) used to prioritise real, active funds over one-off SPVs when the
    candidate pool is far larger than the ingest limit.

    The remaining fields are regulatory metadata straight from the filing —
    not LLM-inferred, no scraping involved, populated whenever the source
    schedule reports them:

    - ``fund_type_raw``: the filing's own label (always "Private Equity Fund"
      given the parsers' filter, kept for provenance/audit).
    - ``gross_asset_value_usd`` (Form ADV): the fund's current reported AUM.
    - ``amount_raised_usd`` (Form D): capital raised in the offering — a
      related but distinct figure from AUM (one is a flow, one is a stock).
    - ``investor_count`` (Form ADV "Owners"): number of beneficial owners.
    - ``filing_date``: date of the filing this record was read from.
    - ``auditor_name`` / ``prime_broker_name`` / ``custodian_name`` (Form ADV
      Schedule D 7.B.1(23)/(24)): reported service providers, when disclosed.
    - ``regulatory_id``: the filing's own stable identifier (Form ADV's
      "805-" Fund ID, or the Form D issuer's CIK) for future re-matching.
    """

    name: str
    firm: str | None
    website_url: str | None
    source_url: str
    state: str | None
    country: str | None
    significance: float
    origin: str  # "form_d" | "form_adv"

    fund_type_raw: str | None = None
    gross_asset_value_usd: float | None = None
    amount_raised_usd: float | None = None
    investor_count: int | None = None
    filing_date: date | None = None
    auditor_name: str | None = None
    prime_broker_name: str | None = None
    custodian_name: str | None = None
    regulatory_id: str | None = None

    @property
    def dedupe_key(self) -> str:
        return normalize_name(self.name)


def normalize_name(name: str) -> str:
    """Loose key for deduping the same entity across sources/filings —
    case/punctuation-insensitive, not a legal-name parser."""
    cleaned = name.upper()
    for ch in (",", ".", "-", "'"):
        cleaned = cleaned.replace(ch, " ")
    return " ".join(cleaned.split())


def merge_candidates(*groups: list[FundCandidate]) -> list[FundCandidate]:
    """Merge candidate lists into one record per fund, sorted most-significant
    first. The same fund often surfaces from *both* Form D (fundraising
    details) and Form ADV (manager identity, AUM, service providers) — rather
    than keeping only the higher-significance source and discarding the
    other's fields, this combines them so nothing either source disclosed is
    lost.
    """
    best: dict[str, FundCandidate] = {}
    for group in groups:
        for candidate in group:
            key = candidate.dedupe_key
            existing = best.get(key)
            best[key] = candidate if existing is None else _combine(existing, candidate)
    return sorted(best.values(), key=lambda c: c.significance, reverse=True)


def _combine(a: FundCandidate, b: FundCandidate) -> FundCandidate:
    """Keep the higher-significance record as the base; fill any field it
    left empty (None / "" / 0) from the other source."""
    primary, secondary = (a, b) if a.significance >= b.significance else (b, a)
    merged = replace(primary)
    for f in fields(FundCandidate):
        if not getattr(merged, f.name) and getattr(secondary, f.name):
            setattr(merged, f.name, getattr(secondary, f.name))
    return merged
