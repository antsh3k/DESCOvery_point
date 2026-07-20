"""EDGAR ingestion: Form D / Form ADV parsers (tiny real-shaped fixtures),
candidate merging, and mandate inference. Network- and DB-free — parsers read
local fixture files, and mandate inference mocks the HTTP scrape (respx) and
the LLM (a fake), matching this suite's existing conventions.
"""

from __future__ import annotations

import csv
import textwrap
from types import SimpleNamespace

import httpx
import respx

import app.services.scraper as scraper
import app.services.scraper.tier1_http as tier1_http
from app.schemas.fund import FundMandate
from app.services.edgar.candidates import FundCandidate, merge_candidates, normalize_name
from app.services.edgar.mandate import infer_mandate
from app.services.edgar.parse_form_adv import parse_form_adv
from app.services.edgar.parse_form_d import parse_form_d
from app.services.llm.base import LLMClient


def _scrape_settings(**kw) -> SimpleNamespace:
    base = dict(scrape_max_pages=1, scrape_tier2="off", anthropic_api_key="", anthropic_model="")
    base.update(kw)
    return SimpleNamespace(**base)


# -- Form D -----------------------------------------------------------------


def _write_form_d(tmp_path):
    (tmp_path / "OFFERING.tsv").write_text(
        "ACCESSIONNUMBER\tINDUSTRYGROUPTYPE\tINVESTMENTFUNDTYPE\tTOTALOFFERINGAMOUNT\n"
        "0001-A\tPooled Investment Fund\tPrivate Equity Fund\t50000000\n"
        "0002-B\tPooled Investment Fund\tHedge Fund\t9000000\n"
        "0003-C\tPooled Investment Fund\tPrivate Equity Fund\tIndefinite\n"
        "0004-D\tManufacturing\t\t1000\n"
    )
    (tmp_path / "ISSUERS.tsv").write_text(
        "ACCESSIONNUMBER\tIS_PRIMARYISSUER_FLAG\tCIK\tENTITYNAME\tSTATEORCOUNTRY\tSTATEORCOUNTRYDESCRIPTION\n"
        "0001-A\tYES\t0001234567\tAcme Buyout Fund III, L.P.\tNY\tNEW YORK\n"
        "0003-C\tYES\t0007654321\tGlobal Growth Partners IV\tN4\tLUXEMBOURG\n"
    )
    return tmp_path


def test_parse_form_d_filters_to_private_equity_and_joins_issuer(tmp_path):
    quarter_dir = _write_form_d(tmp_path)

    candidates = parse_form_d(quarter_dir)

    names = {c.name for c in candidates}
    assert names == {"Acme Buyout Fund III, L.P.", "Global Growth Partners IV"}
    acme = next(c for c in candidates if "Acme" in c.name)
    assert acme.significance == 50_000_000.0
    assert acme.country == "NEW YORK"
    assert acme.origin == "form_d"
    assert "CIK=1234567" in acme.source_url

    # "Indefinite" offering amounts must not blow up float parsing.
    global_fund = next(c for c in candidates if "Global" in c.name)
    assert global_fund.significance == 0.0


def test_parse_form_d_skips_offering_rows_with_no_matching_issuer(tmp_path):
    quarter_dir = _write_form_d(tmp_path)
    # 0003-C's issuer row is a non-primary issuer only — drop it.
    (tmp_path / "ISSUERS.tsv").write_text(
        "ACCESSIONNUMBER\tIS_PRIMARYISSUER_FLAG\tCIK\tENTITYNAME\tSTATEORCOUNTRY\tSTATEORCOUNTRYDESCRIPTION\n"
        "0001-A\tYES\t0001234567\tAcme Buyout Fund III, L.P.\tNY\tNEW YORK\n"
        "0003-C\tNO\t0007654321\tSome Related Entity\tN4\tLUXEMBOURG\n"
    )

    candidates = parse_form_d(quarter_dir)

    assert [c.name for c in candidates] == ["Acme Buyout Fund III, L.P."]


# -- Form ADV -----------------------------------------------------------------


def _write_adv_base(path, rows):
    """rows: list of (filing_id, date_submitted, name, crd)"""
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["FilingID", "1A", "1E1", "DateSubmitted"])
        for filing_id, date, name, crd in rows:
            w.writerow([filing_id, name, crd, date])


def test_parse_form_adv_dedupes_by_fund_id_keeping_latest_filing(tmp_path):
    # Same Fund ID reported across two amendments (an earlier and a later
    # filing) — only the later one should survive.
    _write_adv_base(
        tmp_path / "ERA_ADV_Base_test.csv",
        [
            ("100", "01/01/2015", "OLDCO ADVISERS LLC", "1111"),
            ("200", "01/01/2020", "NEWCO ADVISERS LLC", "1111"),
        ],
    )
    (tmp_path / "ERA_Schedule_D_1I_test.csv").write_text(
        "FilingID,Website\n200,newco-advisers.com\n"
    )
    (tmp_path / "ERA_Schedule_D_7B1A28_websites_test.csv").write_text(
        'FilingID,ReferenceID,SubreferenceID,"Website Address"\n'
    )
    (tmp_path / "ERA_Schedule_D_7B1_test.csv").write_text(
        textwrap.dedent(
            """\
            FilingID,"Fund Name","Fund ID",ReferenceID,State,Country,"Fund Type","Gross Asset Value"
            100,"OLD FUND NAME",805-1,10,DE,United States,Private Equity Fund,1000000
            200,"NEW FUND NAME",805-1,20,DE,United States,Private Equity Fund,2000000
            """
        )
    )
    # No IA files present for this test — the parser should just skip them.

    candidates = parse_form_adv(tmp_path)

    assert len(candidates) == 1
    fund = candidates[0]
    assert fund.name == "NEW FUND NAME"
    assert fund.firm == "NEWCO ADVISERS LLC"
    assert fund.significance == 2_000_000.0
    assert fund.website_url == "https://newco-advisers.com"
    assert fund.source_url == "https://adviserinfo.sec.gov/firm/summary/1111"


def test_parse_form_adv_prefers_fund_website_over_adviser_website(tmp_path):
    _write_adv_base(tmp_path / "ERA_ADV_Base_test.csv", [("100", "01/01/2020", "ADVISER LLC", "5555")])
    (tmp_path / "ERA_Schedule_D_1I_test.csv").write_text(
        "FilingID,Website\n100,http://adviser-site.com\n"
    )
    (tmp_path / "ERA_Schedule_D_7B1A28_websites_test.csv").write_text(
        'FilingID,ReferenceID,SubreferenceID,"Website Address"\n100,10,1,https://fund-specific-site.com\n'
    )
    (tmp_path / "ERA_Schedule_D_7B1_test.csv").write_text(
        textwrap.dedent(
            """\
            FilingID,"Fund Name","Fund ID",ReferenceID,State,Country,"Fund Type","Gross Asset Value"
            100,"SOME FUND",805-1,10,DE,United States,Private Equity Fund,1000000
            """
        )
    )

    candidates = parse_form_adv(tmp_path)

    assert candidates[0].website_url == "https://fund-specific-site.com"


def test_parse_form_adv_ignores_non_private_equity_fund_types(tmp_path):
    _write_adv_base(tmp_path / "ERA_ADV_Base_test.csv", [("100", "01/01/2020", "ADVISER LLC", "5555")])
    (tmp_path / "ERA_Schedule_D_1I_test.csv").write_text("FilingID,Website\n")
    (tmp_path / "ERA_Schedule_D_7B1A28_websites_test.csv").write_text(
        'FilingID,ReferenceID,SubreferenceID,"Website Address"\n'
    )
    (tmp_path / "ERA_Schedule_D_7B1_test.csv").write_text(
        textwrap.dedent(
            """\
            FilingID,"Fund Name","Fund ID",ReferenceID,State,Country,"Fund Type","Gross Asset Value"
            100,"A HEDGE FUND",805-1,10,DE,United States,Hedge Fund,1000000
            """
        )
    )

    assert parse_form_adv(tmp_path) == []


def test_parse_form_adv_skips_unrelated_base_b_file_without_crashing(tmp_path):
    """IA_ADV_Base_B carries a completely different column set (state
    registration checkboxes) and must not be treated as an adviser-identity
    file just because it matches a loose "*ADV_Base*" glob."""
    _write_adv_base(tmp_path / "IA_ADV_Base_A_test.csv", [("100", "01/01/2020", "ADVISER LLC", "5555")])
    (tmp_path / "IA_ADV_Base_B_test.csv").write_text("FilingID,2A1,2A2\n100,Y,\n")
    (tmp_path / "IA_Schedule_D_1I_test.csv").write_text("FilingID,Website\n")
    (tmp_path / "IA_Schedule_D_7B1A28_websites_test.csv").write_text(
        'FilingID,ReferenceID,SubreferenceID,"Website Address"\n'
    )
    (tmp_path / "IA_Schedule_D_7B1_test.csv").write_text(
        textwrap.dedent(
            """\
            FilingID,"Fund Name","Fund ID",ReferenceID,State,Country,"Fund Type","Gross Asset Value"
            100,"SOME FUND",805-1,10,DE,United States,Private Equity Fund,1000000
            """
        )
    )

    candidates = parse_form_adv(tmp_path)

    assert len(candidates) == 1
    assert candidates[0].firm == "ADVISER LLC"


# -- candidate merging ---------------------------------------------------------


def test_normalize_name_ignores_punctuation_and_case():
    assert normalize_name("Acme Fund, L.P.") == normalize_name("ACME FUND L P")


def test_merge_candidates_keeps_most_significant_and_sorts_descending():
    # Same fund reported identically (modulo case) by both sources — the
    # higher-significance (form_adv) record should win.
    low = FundCandidate(
        name="Acme Fund, L.P.", firm=None, website_url=None, source_url="s1",
        state=None, country=None, significance=10.0, origin="form_d",
    )
    high = FundCandidate(
        name="ACME FUND, L.P.", firm="Acme", website_url="https://acme.com", source_url="s2",
        state=None, country=None, significance=500.0, origin="form_adv",
    )
    other = FundCandidate(
        name="Other Fund", firm=None, website_url=None, source_url="s3",
        state=None, country=None, significance=200.0, origin="form_d",
    )

    merged = merge_candidates([low, other], [high])

    assert [c.name for c in merged] == ["ACME FUND, L.P.", "Other Fund"]
    assert merged[0].firm == "Acme"


# -- mandate inference ---------------------------------------------------------


class _FakeExtractLLM(LLMClient):
    def _raw_complete(self, *, system, user):  # pragma: no cover - unused
        raise NotImplementedError

    def extract_fund(self, *, text, source_url):
        return FundMandate(
            name="Whatever The Site Says",
            firm=None,
            sectors=["Software"],
            thesis="Buys B2B software companies.",
        )


@respx.mock
async def test_infer_mandate_overrides_identity_with_candidate_and_keeps_llm_mandate(monkeypatch):
    monkeypatch.setattr(scraper, "assert_public_http_url", lambda url: None)
    monkeypatch.setattr(tier1_http, "assert_public_http_url", lambda url: None)
    monkeypatch.setattr(scraper, "get_settings", _scrape_settings)
    respx.get("https://acme-fund.com/").mock(
        return_value=httpx.Response(200, html="<html><body>We buy software companies.</body></html>")
    )

    candidate = FundCandidate(
        name="ACME FUND III, L.P.", firm="Acme Capital", website_url="https://acme-fund.com/",
        source_url="https://adviserinfo.sec.gov/firm/summary/1", state=None, country=None,
        significance=1.0, origin="form_adv",
    )

    mandate = await infer_mandate(
        candidate, "https://acme-fund.com/", llm=_FakeExtractLLM(), max_pages=1
    )

    assert mandate is not None
    # Identity comes from the authoritative filing, not the site's own copy.
    assert mandate.name == "ACME FUND III, L.P."
    assert mandate.firm == "Acme Capital"
    # Mandate detail comes from the LLM's read of the site.
    assert mandate.sectors == ["Software"]
    assert mandate.source_url == "https://acme-fund.com/"


@respx.mock
async def test_infer_mandate_returns_none_when_nothing_scrapes(monkeypatch):
    monkeypatch.setattr(scraper, "assert_public_http_url", lambda url: None)
    monkeypatch.setattr(tier1_http, "assert_public_http_url", lambda url: None)
    monkeypatch.setattr(scraper, "get_settings", _scrape_settings)
    respx.get("https://dead-site.example/").mock(return_value=httpx.Response(500))

    candidate = FundCandidate(
        name="Dead Fund", firm=None, website_url="https://dead-site.example/",
        source_url="s", state=None, country=None, significance=0.0, origin="form_d",
    )

    mandate = await infer_mandate(
        candidate, "https://dead-site.example/", llm=_FakeExtractLLM(), max_pages=1
    )

    assert mandate is None
