"""Add independent collection-group identity to auctions and ingestion runs.

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("auctions", sa.Column("collection_group", sa.String(length=32), nullable=True))
    op.add_column("ingestion_runs", sa.Column("collection_group", sa.String(length=32), nullable=True))

    # Classify only source identities that are known from the pre-refactor
    # collector. Abort rather than silently assigning an unknown source to a group.
    op.execute("""
        UPDATE auctions
        SET collection_group = CASE
            WHEN source = 'setad_clearance_5315' THEN 'amval_tamliki'
            WHEN source IN (
                'setad_main_estate', 'setad_immovable', 'setad_rental', 'setad_minor'
            ) THEN 'executive_agencies'
            ELSE NULL
        END
    """)
    bind = op.get_bind()
    unknown_auctions = bind.execute(sa.text(
        "SELECT COUNT(*) FROM auctions WHERE collection_group IS NULL"
    )).scalar_one()
    if unknown_auctions:
        raise RuntimeError(
            f"Cannot safely backfill collection_group for {unknown_auctions} auction rows; "
            "inspect their source values before retrying this migration."
        )

    op.execute("""
        UPDATE ingestion_runs
        SET collection_group = CASE
            WHEN category = 'clearance' THEN 'amval_tamliki'
            WHEN category IN ('movable', 'immovable', 'rental', 'minor') THEN 'executive_agencies'
            ELSE NULL
        END
        WHERE kind = 'auctions'
    """)
    unknown_runs = bind.execute(sa.text(
        "SELECT COUNT(*) FROM ingestion_runs "
        "WHERE kind = 'auctions' AND collection_group IS NULL"
    )).scalar_one()
    if unknown_runs:
        raise RuntimeError(
            f"Cannot safely backfill collection_group for {unknown_runs} auction ingestion runs."
        )

    op.alter_column(
        "auctions", "collection_group",
        existing_type=sa.String(length=32),
        nullable=False,
        server_default="executive_agencies",
    )
    op.drop_constraint("uq_auctions_source_party", "auctions", type_="unique")
    op.create_unique_constraint(
        "uq_auctions_group_source_party",
        "auctions",
        ["collection_group", "source", "source_party_id"],
    )
    op.create_index(
        "ix_auctions_group_category",
        "auctions",
        ["collection_group", "category"],
    )
    op.create_index(
        "ix_ingestion_runs_group_scope_finished",
        "ingestion_runs",
        ["kind", "collection_group", "category", "status", "finished_at"],
    )


def downgrade():
    op.drop_index("ix_ingestion_runs_group_scope_finished", table_name="ingestion_runs")
    op.drop_index("ix_auctions_group_category", table_name="auctions")
    op.drop_constraint("uq_auctions_group_source_party", "auctions", type_="unique")
    op.create_unique_constraint(
        "uq_auctions_source_party",
        "auctions",
        ["source", "source_party_id"],
    )
    op.drop_column("ingestion_runs", "collection_group")
    op.drop_column("auctions", "collection_group")
