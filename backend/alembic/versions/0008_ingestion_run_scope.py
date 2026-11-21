"""Scope ingestion history by transaction dataset and auction category.

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ingestion_runs", sa.Column("kind", sa.String(length=20), nullable=True))
    op.add_column("ingestion_runs", sa.Column("category", sa.String(length=24), nullable=True))
    op.create_index(
        "ix_ingestion_runs_scope_finished",
        "ingestion_runs",
        ["kind", "category", "status", "finished_at"],
    )


def downgrade():
    op.drop_index("ix_ingestion_runs_scope_finished", table_name="ingestion_runs")
    op.drop_column("ingestion_runs", "category")
    op.drop_column("ingestion_runs", "kind")
