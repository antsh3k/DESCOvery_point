"""add pgvector extension + funds.thesis_embedding for a semantic pre-filter
(thesis + sectors + stage text) ahead of the LLM judge stage.

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-19
"""

from __future__ import annotations

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

EMBEDDING_DIMENSIONS = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "funds",
        sa.Column("thesis_embedding", Vector(EMBEDDING_DIMENSIONS), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("funds", "thesis_embedding")
    op.execute("DROP EXTENSION IF EXISTS vector")
