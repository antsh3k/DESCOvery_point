# DESCOvery Point — TL;DR

DESCOvery Point is an AI tool that takes a company's **website URL** and returns a ranked shortlist of private-equity funds that would be good potential buyers, working in three separable stages: it first **profiles the company** (scraping the site, escalating to Claude's `web_fetch` only when a page is thin or bot-walled, then using an LLM to extract industry, location, size, financials, and ownership — and optionally enriching gaps from LinkedIn, PitchBook, and news), then assembles a **fund universe** from three sources (a curated seed, funds added by URL, and real SEC EDGAR filings), and finally **matches and ranks** them through a 4-stage engine (deterministic geography/size gates → a quick, no-LLM score of how well the company's size fits each fund's target range → an LLM judge on the top candidates scoring mandate/strategy/value-creation fit → an LLM re-rank with a plain-language "why this fits"). Throughout, the system degrades gracefully — missing data is treated as null (never zero or a guess), numbers are never fabricated, every fact carries a cited source, and scores guide rather than gatekeep so the user always makes the final call.

```mermaid
graph LR
    U[Company URL] --> C[1 Company]
    C --> F[2 Fund universe]
    F --> M[3 Matching]
    M --> R[Ranked shortlist]
```
