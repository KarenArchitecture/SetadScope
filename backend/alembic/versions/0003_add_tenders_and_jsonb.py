"""Add tender records and use PostgreSQL JSONB for raw auction payloads.

Revision ID: 0003
Revises: 0002
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "auctions",
        "raw_payload",
        existing_type=sa.JSON(),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=False,
        postgresql_using="raw_payload::jsonb",
    )

    op.create_table(
        "tenders",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("source_tender_id", sa.String(length=120), nullable=False),
        sa.Column("tender_number", sa.String(length=120), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("tender_type", sa.String(length=120), nullable=True),
        sa.Column("type_name", sa.String(length=240), nullable=True),
        sa.Column("organization", sa.Text(), nullable=True),
        sa.Column("province", sa.String(length=200), nullable=True),
        sa.Column("city", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=120), nullable=True),
        sa.Column("public_notification_date", sa.String(length=40), nullable=True),
        sa.Column("documents_deadline_date", sa.String(length=40), nullable=True),
        sa.Column("proposal_deadline_date", sa.String(length=40), nullable=True),
        sa.Column("opening_date", sa.String(length=40), nullable=True),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("source", "source_tender_id", name="uq_tenders_source_tender"),
    )
    op.create_index("ix_tenders_number", "tenders", ["tender_number"])
    op.create_index("ix_tenders_notification_date", "tenders", ["public_notification_date"])
    op.create_index("ix_tenders_proposal_deadline", "tenders", ["proposal_deadline_date"])


def downgrade():
    op.drop_index("ix_tenders_proposal_deadline", table_name="tenders")
    op.drop_index("ix_tenders_notification_date", table_name="tenders")
    op.drop_index("ix_tenders_number", table_name="tenders")
    op.drop_table("tenders")

    op.alter_column(
        "auctions",
        "raw_payload",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.JSON(),
        existing_nullable=False,
        postgresql_using="raw_payload::json",
    )
