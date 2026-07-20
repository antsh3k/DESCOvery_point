"""widen funds.stage — real fund sites sometimes describe stage/strategy in a
full sentence rather than a short label, and the old 128-char cap crashed the
insert (StringDataRightTruncation) instead of just storing it.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-19
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("funds", "stage", type_=sa.String(512))


def downgrade() -> None:
    op.alter_column("funds", "stage", type_=sa.String(128))
