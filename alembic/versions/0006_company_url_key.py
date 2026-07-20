"""add unique url_key to companies for caching/dedup

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-19
"""

from __future__ import annotations

from urllib.parse import urlparse

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _canonical_key(url: str) -> str:
    normalized = url if urlparse(url).scheme else f"https://{url}"
    parsed = urlparse(normalized)
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return f"{netloc}{parsed.path.rstrip('/')}"


def upgrade() -> None:
    op.add_column("companies", sa.Column("url_key", sa.String(2048), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, url FROM companies")).fetchall()
    seen: set[str] = set()
    for row in rows:
        key = _canonical_key(row.url)
        # Rows already sharing a URL predate this constraint; disambiguate by
        # id rather than deleting historical data.
        if key in seen:
            key = f"{key}#{row.id}"
        seen.add(key)
        conn.execute(
            sa.text("UPDATE companies SET url_key = :key WHERE id = :id"),
            {"key": key, "id": row.id},
        )

    op.alter_column("companies", "url_key", nullable=False)
    op.create_index("ix_companies_url_key", "companies", ["url_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_companies_url_key", table_name="companies")
    op.drop_column("companies", "url_key")
