"""Support relevant-only tender filtering and backfill archived tenders.

Revision ID: 0007
Revises: 0006
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.services.keyword_matching import KEYWORDS, matched_keywords

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "tenders",
        sa.Column("has_keyword_match", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "tenders",
        sa.Column("matched_keywords", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )

    connection = op.get_bind()
    configured = connection.execute(
        sa.text("SELECT value FROM app_settings WHERE key = 'auction_keywords'")
    ).scalar_one_or_none()
    words = (
        tuple(configured["keywords"])
        if isinstance(configured, dict) and isinstance(configured.get("keywords"), list)
        and configured["keywords"]
        else KEYWORDS
    )

    # Keyset pagination avoids loading the complete tender archive into memory.
    last_id = -1
    while True:
        batch = connection.execute(
            sa.text("""
                SELECT id, title, description, type_name
                FROM tenders
                WHERE id > :last_id
                ORDER BY id
                LIMIT 500
            """),
            {"last_id": last_id},
        ).mappings().all()
        if not batch:
            break
        updates = []
        for row in batch:
            found = matched_keywords(row["title"], row["description"], row["type_name"], keywords=words)
            updates.append({
                "id": row["id"],
                "has_match": bool(found),
                "words": json.dumps(found, ensure_ascii=False),
            })
        connection.execute(
            sa.text("""
                UPDATE tenders
                SET has_keyword_match = :has_match, matched_keywords = CAST(:words AS jsonb)
                WHERE id = :id
            """),
            updates,
        )
        last_id = batch[-1]["id"]

    op.create_index("ix_tenders_keyword_match", "tenders", ["has_keyword_match"])


def downgrade():
    op.drop_index("ix_tenders_keyword_match", table_name="tenders")
    op.drop_column("tenders", "matched_keywords")
    op.drop_column("tenders", "has_keyword_match")
