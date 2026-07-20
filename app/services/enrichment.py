"""Supplemental firmographics via Claude's server-side ``web_search`` tool.

The company website is authoritative but usually silent on headcount, funding,
and ownership. This step searches the web (surfacing LinkedIn / PitchBook /
Crunchbase / news snippets) and synthesises those facts with cited source URLs —
without breaching the login-walled pages themselves.

Two passes, because forcing a strict JSON reply in the *same* call as web search
fights the model's cited-prose answer style: (1) search and report findings in
prose, capturing the URLs consulted; (2) coerce that report into the
``CompanyEnrichment`` schema with a plain, tool-free call.

Anthropic-specific (like the Tier-2 fetcher). Requires a model that supports the
``web_search_20260209`` tool (Claude Opus 4.6+, Sonnet 4.6, or Sonnet 5+).
"""

from __future__ import annotations

import json
import logging

from starlette.concurrency import run_in_threadpool

from app.schemas.company import CompanyEnrichment, CompanyProfile, ExtractedSource
from app.services.llm.base import _extract_json_object

logger = logging.getLogger(__name__)

_SEARCH_MAX_TOKENS = 4096
_COERCE_MAX_TOKENS = 2048
_MAX_RESUMES = 5  # guard the server-tool pause/resume loop
_MAX_REPORT_CHARS = 15_000
_MAX_SOURCES = 8
_WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 5}

_SEARCH_SYSTEM = (
    "You are a research analyst. Use the web_search tool to find facts about a "
    "company that its own website rarely states, drawing on sources such as "
    "LinkedIn, PitchBook, Crunchbase, and news:\n"
    "- current employee headcount\n"
    "- annual revenue (state the figure and currency)\n"
    "- ownership status (founder-owned, PE-owned, VC-backed, public, subsidiary)\n"
    "- investors, backers, parent company, or acquirers\n"
    "- the top competitors (name the closest 5, most direct first; sources like "
    "Datanyze, Owler, Craft, or industry write-ups list these)\n"
    "- growth trend: any stated revenue/earnings growth rate, or news of rapid "
    "growth, a slowdown, or decline\n"
    "- signals of a PE deal situation: recent funding/expansion news, a sale "
    "process, distress/restructuring, or a founder retiring/succession\n\n"
    "Report what you find in a few short lines, citing the source URL for each "
    "fact. If the searches don't establish a fact, say so — never guess."
)
_COERCE_SYSTEM = (
    "You convert research notes into a single JSON object. Use only facts stated "
    "in the notes — never invent values. Revenue must be in USD millions (convert "
    "if the notes give another currency). ownership_status is one short label: "
    "'founder-owned', 'PE-owned', 'VC-backed', 'public', 'subsidiary', or "
    "'unknown'. `competitors` is at most 5 competitor company names, most direct "
    "first. `growth_trajectory` is the stated growth figure if given, otherwise a "
    "short qualitative trend ('flat', 'declining'); null if the notes say nothing "
    "about growth. `deal_stage` is a short label for the company's likely PE deal "
    "situation (e.g. 'growth-stage', 'mature/cash-generative buyout candidate', "
    "'distressed/turnaround', 'founder-led succession', 'roll-up/buy-and-build "
    "platform') based only on what the notes support; null if there's no signal. "
    "Leave any unsupported field null / empty. In `sources`, list only URLs that "
    "appear in the notes. Add a 0-1 `confidence` per populated field."
)


async def enrich_company(
    profile: CompanyProfile, url: str, *, api_key: str, model: str
) -> CompanyEnrichment | None:
    """Search for supplemental firmographics. Returns None on failure/empty."""
    if not api_key:
        logger.info("Enrichment skipped: ANTHROPIC_API_KEY not set")
        return None

    identity = _identity(profile, url)

    def _run() -> CompanyEnrichment | None:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        report, searched = _search(client, model, identity)
        if not report.strip():
            return None
        enrichment = _coerce(client, model, report)
        if enrichment is None:
            return None
        if not enrichment.sources:
            enrichment.sources = searched[:_MAX_SOURCES]
        return enrichment

    try:
        return await run_in_threadpool(_run)
    except Exception as exc:  # noqa: BLE001 - network/model errors shouldn't crash ingest
        logger.warning("Enrichment failed for %s: %s", url, exc)
        return None


def _search(client, model: str, identity: str) -> tuple[str, list[ExtractedSource]]:
    """Pass 1 — search the web and report findings in prose."""
    messages = [{"role": "user", "content": f"Research this company:\n{identity}"}]
    report = ""
    searched: list[ExtractedSource] = []
    for _ in range(_MAX_RESUMES):
        resp = client.messages.create(
            model=model,
            max_tokens=_SEARCH_MAX_TOKENS,
            system=_SEARCH_SYSTEM,
            tools=[_WEB_SEARCH_TOOL],
            messages=messages,
        )
        report += _text_of(resp)
        searched.extend(_searched_sources(resp))
        if resp.stop_reason != "pause_turn":
            break
        messages.append({"role": "assistant", "content": resp.content})
    return report[:_MAX_REPORT_CHARS], _dedupe(searched)


def _coerce(client, model: str, report: str) -> CompanyEnrichment | None:
    """Pass 2 — turn the prose report into the CompanyEnrichment schema."""
    instruction = (
        "Respond with a single JSON object and nothing else — no prose, no "
        "markdown fences. It must conform to this JSON schema:\n"
        f"{json.dumps(CompanyEnrichment.model_json_schema())}"
    )
    resp = client.messages.create(
        model=model,
        max_tokens=_COERCE_MAX_TOKENS,
        system=_COERCE_SYSTEM,
        messages=[{"role": "user", "content": f"Research notes:\n{report}\n\n{instruction}"}],
    )
    return _parse(_text_of(resp))


def _identity(profile: CompanyProfile, url: str) -> str:
    parts = [f"Website: {url}"]
    if profile.name:
        parts.append(f"Name: {profile.name}")
    if profile.industry:
        parts.append(f"Industry: {profile.industry}")
    location = ", ".join(filter(None, [profile.location_region, profile.location_country]))
    if location:
        parts.append(f"Location: {location}")
    return "\n".join(parts)


def _text_of(resp) -> str:
    return "".join(
        block.text for block in resp.content if getattr(block, "type", None) == "text"
    )


def _searched_sources(resp) -> list[ExtractedSource]:
    """Pull the URLs Claude consulted out of web_search_tool_result blocks."""
    sources: list[ExtractedSource] = []
    for block in resp.content:
        if getattr(block, "type", None) != "web_search_tool_result":
            continue
        results = getattr(block, "content", None)
        if not isinstance(results, list):  # an error result is a bare object
            continue
        for r in results:
            url = getattr(r, "url", None)
            if url:
                sources.append(ExtractedSource(url=url, title=getattr(r, "title", None)))
    return sources


def _dedupe(sources: list[ExtractedSource]) -> list[ExtractedSource]:
    seen: set[str] = set()
    unique: list[ExtractedSource] = []
    for s in sources:
        if s.url in seen:
            continue
        seen.add(s.url)
        unique.append(s)
    return unique


def _parse(text: str) -> CompanyEnrichment | None:
    if not text.strip():
        return None
    try:
        payload = _extract_json_object(text)
        return CompanyEnrichment.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 - a malformed enrichment shouldn't fail ingest
        logger.warning("Could not parse enrichment JSON: %s", exc)
        return None
