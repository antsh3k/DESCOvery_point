"""Merge semantics for search-based enrichment (website stays authoritative)."""

from app.schemas.company import CompanyEnrichment, CompanyProfile
from app.services.pipeline import merge_enrichment


def _profile(**kw) -> CompanyProfile:
    return CompanyProfile(name="Acme", industry="SaaS", **kw)


def test_enrichment_fills_only_empty_fields():
    profile = _profile(size_employees=None, revenue_estimate_usd_m=None)
    enrichment = CompanyEnrichment(
        size_employees=450,
        revenue_estimate_usd_m=30.0,
        ownership_status="PE-owned",
        investors=["General Atlantic"],
        competitors=["Lululemon", "Alo Yoga", "Nike"],
        confidence={"size_employees": 0.7},
    )

    merged = merge_enrichment(profile, enrichment)

    assert merged.size_employees == 450
    assert merged.revenue_estimate_usd_m == 30.0
    assert merged.ownership_status == "PE-owned"
    assert merged.investors == ["General Atlantic"]
    assert merged.competitors == ["Lululemon", "Alo Yoga", "Nike"]
    assert merged.confidence["enriched.size_employees"] == 0.7


def test_competitors_capped_at_five():
    profile = _profile()
    enrichment = CompanyEnrichment(
        competitors=["A", "B", "C", "D", "E", "F", "G"],
    )

    merged = merge_enrichment(profile, enrichment)

    assert merged.competitors == ["A", "B", "C", "D", "E"]


def test_website_competitors_win_over_enrichment():
    profile = _profile(competitors=["Existing Rival"])
    enrichment = CompanyEnrichment(competitors=["Other Rival"])

    merged = merge_enrichment(profile, enrichment)

    assert merged.competitors == ["Existing Rival"]


def test_website_values_win_over_enrichment():
    profile = _profile(
        size_employees=1000,
        revenue_estimate_usd_m=200.0,
        ownership_status="founder-owned",
        investors=["Founder"],
    )
    enrichment = CompanyEnrichment(
        size_employees=450,
        revenue_estimate_usd_m=30.0,
        ownership_status="PE-owned",
        investors=["Someone Else"],
    )

    merged = merge_enrichment(profile, enrichment)

    assert merged.size_employees == 1000
    assert merged.revenue_estimate_usd_m == 200.0
    assert merged.ownership_status == "founder-owned"
    assert merged.investors == ["Founder"]


def test_empty_enrichment_is_a_noop():
    profile = _profile(size_employees=500)
    merged = merge_enrichment(profile, CompanyEnrichment())

    assert merged.size_employees == 500
    assert merged.ownership_status is None
    assert merged.investors == []
