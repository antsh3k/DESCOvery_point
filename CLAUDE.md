# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment & dependencies

This project uses **uv** for Python environment and dependency management (`.venv/`, `pyproject.toml`, `uv.lock`, Python per `.python-version`). Always manage packages through uv so they are recorded in `pyproject.toml`/`uv.lock` — never `pip install` into the venv ad hoc:

- Add a dependency: `uv add <package>`
- Add a dev-only dependency: `uv add --dev <package>`
- Remove: `uv remove <package>`
- Sync the env from the lockfile: `uv sync`
- Run a command in the env: `uv run <cmd>` (e.g. `uv run uvicorn ...`, `uv run pytest`)

## Common commands

Backend (Python / uv):
```
uv run pytest                              # DB- and network-free test suite
uv run alembic upgrade head                # apply migrations (needs Postgres up)
uv run seed                                # load the curated fund seed
uv run uvicorn app.main:app --reload       # run the API (docs at /docs)
```

Frontend (`web/`, Next.js):
```
cd web && npm install && npm run dev       # dev server on :3000 (needs API on :8000)
cd web && npm run build                    # production build + typecheck
```

Full stack (Docker):
```
docker compose up --build                  # db + api (auto-migrates & seeds) + web
```

Tests are intentionally DB- and network-free (LLM faked, HTTP mocked with `respx`), so `uv run pytest` works without Postgres or API keys.

## Project status

M0–M5 of `BUILD_PLAN.md` are built and verified: FastAPI + async SQLAlchemy/Postgres backend (tiered scraper with a Claude `web_fetch` Tier-2 fallback, LLM extractor, 4-stage matching engine), a Next.js dashboard (`web/`), and a Docker Compose stack. "Later" items (SEC EDGAR ingestion, embeddings/pgvector, background jobs, auth) are not built. Read `BUILD_PLAN.md` before feature work.

Tier-2 fallback runs entirely through Claude's server-side `web_fetch` tool (uses `ANTHROPIC_API_KEY`; no extra deps or browser). `SCRAPE_TIER2=claude|off` selects the fallback.

## What this project is

An AI-powered tool that takes a company's **website URL** as input, analyzes the site content to extract key attributes (industry, location, size, product offerings), and produces a **shortlist of private equity (PE) funds** that would be good potential buyers for that business. Target companies are SMBs/SMEs.

## Architecture (as built)

The pipeline is **scrape → extract → store → match → rank**, each a separable, testable unit under `app/services/`:

1. **Scrape** (`services/scraper/`) — tiered: Tier-1 HTTP fetch + BeautifulSoup parse by default; a `detector` decides whether to escalate to Tier-2 (Claude's server-side `web_fetch` tool in `tier2_claude.py`, selected by `SCRAPE_TIER2`).
2. **Extract** (`services/extractor.py` + `services/llm/`) — provider-agnostic `LLMClient` (Anthropic default, OpenAI alt) coerces scraped text into the `CompanyProfile` schema. Numerics are optional; **missing is never treated as zero**. An optional **enrich** step (`services/enrichment.py`, `ENRICH_SOURCE=claude|off`) then uses Claude's server-side `web_search` tool to fill gaps the website leaves open — headcount, revenue, ownership, investors, competitors — merging into empty fields only (website stays authoritative) and citing each source with `fetch_method=search`. Enrichment runs as a **background job** (`run_company_enrichment`, scheduled via FastAPI `BackgroundTasks`): `POST /companies` returns right after extraction with `enrichment_status=pending`, the job updates the row on its own session, and the client polls until `enrichment_status` leaves `pending`/`running`.
3. **Match** (`services/matching/`) — 4 stages: hard filters (geo/sector, forgiving on unknowns) → soft numeric range scoring → LLM thesis/strategy judge → LLM re-rank + rationale on the top N. Composite score uses configurable weights (`settings`) and **renormalises over present dimensions** so missing financials don't penalise.

`services/pipeline.py` ties these to the DB and is what the routers call. Models in `app/models/`, schemas in `app/schemas/`, routers in `app/routers/`, fund seed in `app/seed/`.

## Conventions

- `.gitignore` targets Python; default to Python unless the user chooses otherwise.
- LLM provider is unspecified in the brief ("OpenAI's GPT API" is only an example). Confirm the provider before wiring one in; if building against Claude/Anthropic, consult the `claude-api` skill for current model IDs and usage.
- Keep API keys in a `.env` (already covered by `.gitignore`), never in code or commits.
