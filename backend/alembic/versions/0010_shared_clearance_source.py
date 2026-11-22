"""Move Central Board clearance records into one shared source scope.

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

SHARED_SOURCE = "setad_clearance_shared"
LEGACY_SOURCE = "setad_clearance_5315"
SHARED_URL = "https://fe.setadiran.ir/centralboard/?tagCode=341,343&boardCode=3"
LEGACY_URL = "https://fe.setadiran.ir/centralboard/?tagCode=342&boardCode=3&selectedOrganization=5315"


def upgrade():
    # Keep every historical row and its raw JSONB. Only its source identity and
    # scope change so the new unscoped feed upserts into the same archive.
    op.execute(sa.text("""
        UPDATE auctions
        SET collection_group = 'shared',
            source = :shared_source,
            source_url = :shared_url
        WHERE category = 'clearance'
          AND source = :legacy_source
    """).bindparams(
        shared_source=SHARED_SOURCE,
        shared_url=SHARED_URL,
        legacy_source=LEGACY_SOURCE,
    ))
    op.execute(sa.text("""
        UPDATE ingestion_runs
        SET collection_group = 'shared'
        WHERE kind = 'auctions'
          AND category = 'clearance'
    """))

    bind = op.get_bind()
    remaining_legacy = bind.execute(sa.text("""
        SELECT COUNT(*) FROM auctions
        WHERE category = 'clearance'
          AND source = :legacy_source
    """).bindparams(legacy_source=LEGACY_SOURCE)).scalar_one()
    if remaining_legacy:
        raise RuntimeError(
            f"Could not migrate {remaining_legacy} legacy clearance auction rows."
        )


def downgrade():
    op.execute(sa.text("""
        UPDATE auctions
        SET collection_group = 'amval_tamliki',
            source = :legacy_source,
            source_url = :legacy_url
        WHERE category = 'clearance'
          AND source = :shared_source
    """).bindparams(
        legacy_source=LEGACY_SOURCE,
        legacy_url=LEGACY_URL,
        shared_source=SHARED_SOURCE,
    ))
    op.execute(sa.text("""
        UPDATE ingestion_runs
        SET collection_group = 'amval_tamliki'
        WHERE kind = 'auctions'
          AND category = 'clearance'
    """))
