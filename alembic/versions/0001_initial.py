"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-19
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("name", sa.String(512)),
        sa.Column("industry", sa.String(256)),
        sa.Column("sub_industry", sa.String(256)),
        sa.Column("location_country", sa.String(128)),
        sa.Column("location_region", sa.String(128)),
        sa.Column("size_employees", sa.Integer()),
        sa.Column("revenue_estimate_usd_m", sa.Numeric(14, 2)),
        sa.Column("ebitda_estimate_usd_m", sa.Numeric(14, 2)),
        sa.Column("products", postgresql.JSONB()),
        sa.Column("summary", sa.Text()),
        sa.Column("business_model", sa.Text()),
        sa.Column("raw_extracted", postgresql.JSONB()),
        sa.Column("extraction_confidence", postgresql.JSONB()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
    )
    op.create_index("ix_companies_url", "companies", ["url"])

    op.create_table(
        "company_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("page_title", sa.String(512)),
        sa.Column("fetched_at", sa.DateTime(timezone=True)),
        sa.Column("fetch_method", sa.String(32), nullable=False),
        sa.Column("snippet", sa.Text()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_company_sources_company_id", "company_sources", ["company_id"]
    )

    op.create_table(
        "funds",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("firm", sa.String(512)),
        sa.Column("website_url", sa.String(2048)),
        sa.Column("source_url", sa.String(2048)),
        sa.Column("sectors", postgresql.JSONB()),
        sa.Column("geographies", postgresql.JSONB()),
        sa.Column("check_size_min_usd_m", sa.Numeric(14, 2)),
        sa.Column("check_size_max_usd_m", sa.Numeric(14, 2)),
        sa.Column("ebitda_min_usd_m", sa.Numeric(14, 2)),
        sa.Column("ebitda_max_usd_m", sa.Numeric(14, 2)),
        sa.Column("revenue_min_usd_m", sa.Numeric(14, 2)),
        sa.Column("revenue_max_usd_m", sa.Numeric(14, 2)),
        sa.Column("stage", sa.String(128)),
        sa.Column("thesis", sa.Text()),
        sa.Column("provenance", sa.String(32), nullable=False),
        sa.Column("mandate_source", sa.String(32), nullable=False),
        sa.Column("mandate_confidence", sa.Numeric(4, 3)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
    )

    op.create_table(
        "matches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("fund_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("passed_hard_filters", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("numeric_score", sa.Numeric(6, 2)),
        sa.Column("thesis_score", sa.Numeric(6, 2)),
        sa.Column("strategy_score", sa.Numeric(6, 2)),
        sa.Column("composite_score", sa.Numeric(6, 2)),
        sa.Column("matched_on", postgresql.JSONB()),
        sa.Column("rationale", sa.Text()),
        sa.Column("rank", sa.Integer()),
        sa.Column("weights_used", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fund_id"], ["funds.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_matches_company_id", "matches", ["company_id"])
    op.create_index("ix_matches_fund_id", "matches", ["fund_id"])
    op.create_index("ix_matches_run_id", "matches", ["run_id"])

    op.create_table(
        "settings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("weight_thesis", sa.Numeric(4, 3), nullable=False, server_default="0.40"),
        sa.Column("weight_numeric", sa.Numeric(4, 3), nullable=False, server_default="0.35"),
        sa.Column("weight_strategy", sa.Numeric(4, 3), nullable=False, server_default="0.25"),
        sa.Column("llm_provider", sa.String(32), nullable=False, server_default="anthropic"),
        sa.Column("llm_model", sa.String(128)),
        sa.Column("scrape_max_pages", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_index("ix_matches_run_id", table_name="matches")
    op.drop_index("ix_matches_fund_id", table_name="matches")
    op.drop_index("ix_matches_company_id", table_name="matches")
    op.drop_table("matches")
    op.drop_table("funds")
    op.drop_index("ix_company_sources_company_id", table_name="company_sources")
    op.drop_table("company_sources")
    op.drop_index("ix_companies_url", table_name="companies")
    op.drop_table("companies")
