"""Quarantine EAUC records previously collected under the wrong Amval context.

Revision ID: 0011
Revises: 0010

Rows in the Amval Tamliki collection are only trusted when their embedded
auctioneer.id is 2, matching the current gateway-context validation. Preserve
mismatched legacy rows for audit, then remove them from the live auction feed.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auction_quarantine",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("original_auction_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("row_data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "quarantined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.execute(sa.text("""
        INSERT INTO auction_quarantine (original_auction_id, reason, row_data)
        SELECT
            id,
            'Legacy Amval record does not belong to auctioneer.id=2',
            to_jsonb(auctions)
        FROM auctions
        WHERE collection_group = 'amval_tamliki'
          AND category IN ('movable', 'immovable', 'rental', 'minor')
          AND (
            CASE
                WHEN category = 'movable'
                    THEN raw_payload #>> '{auctionParty,auction,auctioneer,id}'
                WHEN category IN ('immovable', 'rental')
                    THEN COALESCE(
                        raw_payload #>> '{auction,auctioneer,id}',
                        raw_payload #>> '{immovableAuction,auctioneer,id}'
                    )
                WHEN category = 'minor'
                    THEN raw_payload #>> '{auctioneer,id}'
                ELSE NULL
            END
          ) IS DISTINCT FROM '2'
    """))

    op.execute(sa.text("""
        DELETE FROM auctions
        WHERE collection_group = 'amval_tamliki'
          AND category IN ('movable', 'immovable', 'rental', 'minor')
          AND (
            CASE
                WHEN category = 'movable'
                    THEN raw_payload #>> '{auctionParty,auction,auctioneer,id}'
                WHEN category IN ('immovable', 'rental')
                    THEN COALESCE(
                        raw_payload #>> '{auction,auctioneer,id}',
                        raw_payload #>> '{immovableAuction,auctioneer,id}'
                    )
                WHEN category = 'minor'
                    THEN raw_payload #>> '{auctioneer,id}'
                ELSE NULL
            END
          ) IS DISTINCT FROM '2'
    """))


def downgrade():
    # Quarantined rows are intentionally not restored automatically: they are
    # known to have been attributed to the wrong collection context.
    op.drop_table("auction_quarantine")
