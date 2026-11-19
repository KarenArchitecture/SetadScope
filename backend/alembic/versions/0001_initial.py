"""Initial database schema.

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "auctions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("source_party_id", sa.String(120), nullable=False),
        sa.Column("auction_id", sa.String(120)),
        sa.Column("auction_no", sa.String(120)),
        sa.Column("auction_reference_no", sa.String(120)),
        sa.Column("title", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("organization", sa.Text()),
        sa.Column("province", sa.String(200)),
        sa.Column("city", sa.String(200)),
        sa.Column("state", sa.String(100)),
        sa.Column("proposal_start", sa.DateTime(timezone=True)),
        sa.Column("proposal_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document_deadline", sa.DateTime(timezone=True)),
        sa.Column("base_total_price", sa.Numeric(24, 2)),
        sa.Column("trust_amount", sa.Numeric(24, 2)),
        sa.Column("total_volume_m3", sa.Numeric(20, 3)),
        sa.Column("money_unit", sa.String(30)),
        sa.Column("source_url", sa.Text()),
        sa.Column("matched_keywords", sa.JSON(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("source", "source_party_id", name="uq_auctions_source_party"),
    )
    op.create_index("ix_auctions_deadline", "auctions", ["proposal_deadline"])
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("fetched", sa.BigInteger()),
        sa.Column("matched", sa.BigInteger()),
        sa.Column("stored", sa.BigInteger()),
        sa.Column("skipped_expired", sa.BigInteger()),
        sa.Column("skipped_unknown_deadline", sa.BigInteger()),
        sa.Column("error", sa.Text()),
    )

def downgrade():
    op.drop_table("ingestion_runs")
    op.drop_index("ix_auctions_deadline", table_name="auctions")
    op.drop_table("auctions")
