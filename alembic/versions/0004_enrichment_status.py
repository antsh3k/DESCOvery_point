"""add enrichment_status to companies

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-19
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing rows were enriched inline (before the background job existed),
    # so backfill them as 'done'.
    op.add_column(
        "companies",
        sa.Column(
            "enrichment_status",
            sa.String(32),
            nullable=False,
            server_default="done",
        ),
    )


def downgrade() -> None:
    op.drop_column("companies", "enrichment_status")
