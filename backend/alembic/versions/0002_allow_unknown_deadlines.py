"""Allow keyword-matched auctions with unparsed proposal deadlines.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "auctions",
        "proposal_deadline",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        "auctions",
        "proposal_deadline",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
