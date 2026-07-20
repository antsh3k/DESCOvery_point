"""add fund regulatory metadata (auditor, prime broker, custodian, gross
assets, amount raised, investor count, filing date, regulatory id) — all
straight from Form ADV / Form D filings, not LLM-inferred.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-19
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("funds", sa.Column("fund_type_raw", sa.String(128), nullable=True))
    op.add_column("funds", sa.Column("gross_asset_value_usd", sa.Numeric(20, 2), nullable=True))
    op.add_column("funds", sa.Column("amount_raised_usd", sa.Numeric(20, 2), nullable=True))
    op.add_column("funds", sa.Column("investor_count", sa.Integer(), nullable=True))
    op.add_column("funds", sa.Column("filing_date", sa.Date(), nullable=True))
    op.add_column("funds", sa.Column("auditor_name", sa.String(512), nullable=True))
    op.add_column("funds", sa.Column("prime_broker_name", sa.String(512), nullable=True))
    op.add_column("funds", sa.Column("custodian_name", sa.String(512), nullable=True))
    op.add_column("funds", sa.Column("regulatory_id", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("funds", "regulatory_id")
    op.drop_column("funds", "custodian_name")
    op.drop_column("funds", "prime_broker_name")
    op.drop_column("funds", "auditor_name")
    op.drop_column("funds", "filing_date")
    op.drop_column("funds", "investor_count")
    op.drop_column("funds", "amount_raised_usd")
    op.drop_column("funds", "gross_asset_value_usd")
    op.drop_column("funds", "fund_type_raw")
