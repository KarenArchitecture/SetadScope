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

    # Earlier auction imports updated every imported row's updated_at inside
    # the run's started_at/finished_at window. Backfill only when that window
    # identifies exactly one category; overlapping/ambiguous runs stay unscoped.
    op.execute("""
        UPDATE ingestion_runs AS runs
        SET kind = 'auctions', category = matched.category
        FROM (
            SELECT runs.id, MIN(auctions.category) AS category
            FROM ingestion_runs AS runs
            JOIN auctions
              ON auctions.updated_at >= runs.started_at
             AND auctions.updated_at <= runs.finished_at
            WHERE runs.kind IS NULL
              AND runs.status = 'success'
              AND runs.finished_at IS NOT NULL
            GROUP BY runs.id
            HAVING COUNT(DISTINCT auctions.category) = 1
        ) AS matched
        WHERE runs.id = matched.id
    """)

    # Keep this conservative too: only infer tender history when no auction
    # rows were touched during the same successful run window.
    op.execute("""
        UPDATE ingestion_runs AS runs
        SET kind = 'tenders', category = NULL
        WHERE runs.kind IS NULL
          AND runs.status = 'success'
          AND runs.finished_at IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM tenders
              WHERE tenders.updated_at >= runs.started_at
                AND tenders.updated_at <= runs.finished_at
          )
          AND NOT EXISTS (
              SELECT 1 FROM auctions
              WHERE auctions.updated_at >= runs.started_at
                AND auctions.updated_at <= runs.finished_at
          )
    """)

    op.create_index(
        "ix_ingestion_runs_scope_finished",
        "ingestion_runs",
        ["kind", "category", "status", "finished_at"],
    )


def downgrade():
    op.drop_index("ix_ingestion_runs_scope_finished", table_name="ingestion_runs")
    op.drop_column("ingestion_runs", "category")
    op.drop_column("ingestion_runs", "kind")
