"""Add unified auction category metadata without dropping legacy records.

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("auctions", sa.Column("category", sa.String(24), nullable=False, server_default="movable"))
    op.add_column("auctions", sa.Column("has_keyword_match", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("auctions", sa.Column("item_title", sa.Text(), nullable=True))
    op.add_column("auctions", sa.Column("item_reference_no", sa.String(120), nullable=True))
    op.add_column("auctions", sa.Column("asset_type", sa.String(180), nullable=True))
    op.add_column("auctions", sa.Column("price_type", sa.String(40), nullable=True))
    op.add_column("auctions", sa.Column("rent_duration_months", sa.Integer(), nullable=True))
    op.add_column("auctions", sa.Column("rent_duration_days", sa.Integer(), nullable=True))
    # Earlier releases only stored keyword-matched movable auctions.
    # Preserve every existing row and its unique source/source_party_id key.
    op.execute("UPDATE auctions SET has_keyword_match = true WHERE json_array_length(matched_keywords) > 0")
    op.execute("UPDATE auctions SET price_type = 'sale_base' WHERE source = 'setad_main_estate'")
    op.create_index("ix_auctions_category", "auctions", ["category"])
    op.create_index("ix_auctions_category_match", "auctions", ["category", "has_keyword_match"])


def downgrade():
    op.drop_index("ix_auctions_category_match", table_name="auctions")
    op.drop_index("ix_auctions_category", table_name="auctions")
    for name in [
        "rent_duration_days", "rent_duration_months", "price_type", "asset_type",
        "item_reference_no", "item_title", "has_keyword_match", "category",
    ]:
        op.drop_column("auctions", name)
