"""Shared candidate record produced by the Form D / Form ADV parsers, before
mandate inference and before it becomes a ``Fund`` row.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FundCandidate:
    """A real private-equity fund entity discovered in EDGAR bulk data.

    ``website_url`` is the best known site for the fund itself or its adviser
    (may be ``None`` — resolved via search before mandate inference).
    ``source_url`` is always set to an authoritative SEC/IAPD page.
    ``significance`` is a sort proxy (gross asset value / offering amount, in
    USD) used to prioritise real, active funds over one-off SPVs when the
    candidate pool is far larger than the ingest limit.
    """

    name: str
    firm: str | None
    website_url: str | None
    source_url: str
    state: str | None
    country: str | None
    significance: float
    origin: str  # "form_d" | "form_adv"

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
    """Merge candidate lists, keeping the most significant record per fund and
    sorting the result most-significant-first."""
    best: dict[str, FundCandidate] = {}
    for group in groups:
        for candidate in group:
            key = candidate.dedupe_key
            existing = best.get(key)
            if existing is None or candidate.significance > existing.significance:
                best[key] = candidate
    return sorted(best.values(), key=lambda c: c.significance, reverse=True)
