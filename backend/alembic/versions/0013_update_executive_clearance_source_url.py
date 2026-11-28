"""Align historical executive clearance source URLs with the owner exclusion filter.

Revision ID: 0013
Revises: 0012
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

EXECUTIVE_URL = (
    "https://fe.setadiran.ir/centralboard/"
    "?tagCode=341,343&notOrgId=5315&boardCode=3"
)
LEGACY_EXECUTIVE_URL = (
    "https://fe.setadiran.ir/centralboard/"
    "?tagCode=341,343&boardCode=3"
)


def upgrade():
    op.execute(sa.text("""
        UPDATE auctions
        SET source_url = :source_url
        WHERE category = 'clearance'
          AND collection_group = 'executive_agencies'
          AND source = 'setad_clearance_executive_agencies'
    """).bindparams(source_url=EXECUTIVE_URL))


def downgrade():
    op.execute(sa.text("""
        UPDATE auctions
        SET source_url = :source_url
        WHERE category = 'clearance'
          AND collection_group = 'executive_agencies'
          AND source = 'setad_clearance_executive_agencies'
    """).bindparams(source_url=LEGACY_EXECUTIVE_URL))
