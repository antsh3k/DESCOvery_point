"""add growth_trajectory and deal_stage to companies

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-20
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("growth_trajectory", sa.Text(), nullable=True))
    op.add_column("companies", sa.Column("deal_stage", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "deal_stage")
    op.drop_column("companies", "growth_trajectory")
