"""rename match/settings scoring to the mandate/strategy/value_creation pillars

Moves the 3-dimension scoring (thesis / numeric / strategy) to the rubric's three
pillars: mandate, strategy, value_creation. Match rows are rebuilt on every run so
their per-dimension columns carry no durable history — renaming/dropping them is
safe. The single settings row's weights changed meaning (thesis→mandate is not
1:1), so they are reset to the new defaults.

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-19
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # matches: ephemeral per-run scores
    op.alter_column("matches", "numeric_score", new_column_name="mandate_score")
    op.drop_column("matches", "thesis_score")
    op.add_column(
        "matches", sa.Column("value_creation_score", sa.Numeric(6, 2), nullable=True)
    )

    # settings: single-row weights — dimensions changed meaning, reset to defaults
    op.alter_column("settings", "weight_numeric", new_column_name="weight_mandate")
    op.add_column(
        "settings",
        sa.Column(
            "weight_value_creation",
            sa.Numeric(4, 3),
            nullable=False,
            server_default="0.25",
        ),
    )
    op.drop_column("settings", "weight_thesis")
    op.execute(
        "UPDATE settings SET weight_mandate = 0.40, weight_strategy = 0.35, "
        "weight_value_creation = 0.25"
    )


def downgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "weight_thesis", sa.Numeric(4, 3), nullable=False, server_default="0.40"
        ),
    )
    op.drop_column("settings", "weight_value_creation")
    op.alter_column("settings", "weight_mandate", new_column_name="weight_numeric")

    op.add_column(
        "matches", sa.Column("thesis_score", sa.Numeric(6, 2), nullable=True)
    )
    op.drop_column("matches", "value_creation_score")
    op.alter_column("matches", "mandate_score", new_column_name="numeric_score")
