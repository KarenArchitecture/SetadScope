"""Separate Central Board clearance records by owning collection.

Revision ID: 0012
Revises: 0011
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

EXECUTIVE_SOURCE = "setad_clearance_executive_agencies"
AMVAL_SOURCE = "setad_clearance_amval_tamliki"
EXECUTIVE_URL = "https://fe.setadiran.ir/centralboard/?tagCode=341,343&notOrgId=5315&boardCode=3"
AMVAL_URL = "https://fe.setadiran.ir/centralboard/?tagCode=342&selectedOrganization=5315&boardCode=3"


def upgrade():
    # Revision 0010 replaced the former Amval source identity with the shared
    # source name. Recover ownership from the retained source payload first.
    op.execute(sa.text("""
        UPDATE auctions
        SET collection_group = 'amval_tamliki',
            source = :source,
            source_url = :source_url
        WHERE category = 'clearance'
          AND collection_group = 'shared'
          AND (
              raw_payload ->> 'orgId' = '5315'
              OR raw_payload ->> 'tagCode' = '342'
              OR COALESCE(raw_payload ->> 'orgName', organization, '') ILIKE '%اموال تملیکی%'
          )
    """).bindparams(source=AMVAL_SOURCE, source_url=AMVAL_URL))

    # The previous tagCode=341,343 collector was the executive-agency feed.
    # Any remaining rows are assigned there; no historical payload is deleted.
    op.execute(sa.text("""
        UPDATE auctions
        SET collection_group = 'executive_agencies',
            source = :source,
            source_url = :source_url
        WHERE category = 'clearance'
          AND collection_group = 'shared'
    """).bindparams(source=EXECUTIVE_SOURCE, source_url=EXECUTIVE_URL))

    # IngestionRun has no foreign key to individual cards, so old shared runs
    # cannot be classified reliably. Keep them visible under the legacy default.
    op.execute(sa.text("""
        UPDATE ingestion_runs
        SET collection_group = 'executive_agencies'
        WHERE kind = 'auctions'
          AND category = 'clearance'
          AND collection_group = 'shared'
    """))

    bind = op.get_bind()
    remaining = bind.execute(sa.text("""
        SELECT COUNT(*) FROM auctions
        WHERE category = 'clearance' AND collection_group = 'shared'
    """)).scalar_one()
    if remaining:
        raise RuntimeError(f"Could not separate {remaining} legacy shared clearance rows.")


def downgrade():
    bind = op.get_bind()
    duplicate_ids = bind.execute(sa.text("""
        SELECT source_party_id
        FROM auctions
        WHERE category = 'clearance'
          AND collection_group IN ('executive_agencies', 'amval_tamliki')
          AND source IN (:executive_source, :amval_source)
        GROUP BY source_party_id
        HAVING COUNT(*) > 1
        LIMIT 1
    """).bindparams(executive_source=EXECUTIVE_SOURCE, amval_source=AMVAL_SOURCE)).first()
    if duplicate_ids:
        raise RuntimeError(
            "Cannot downgrade clearance sources into one shared identity because "
            "the same source_party_id exists in both owning collections."
        )

    op.execute(sa.text("""
        UPDATE auctions
        SET collection_group = 'shared',
            source = 'setad_clearance_shared',
            source_url = 'https://fe.setadiran.ir/centralboard/?tagCode=341,343&notOrgId=5315&boardCode=3'
        WHERE category = 'clearance'
          AND (
              (collection_group = 'executive_agencies' AND source = :executive_source)
              OR (collection_group = 'amval_tamliki' AND source = :amval_source)
          )
    """).bindparams(executive_source=EXECUTIVE_SOURCE, amval_source=AMVAL_SOURCE))

    op.execute(sa.text("""
        UPDATE ingestion_runs
        SET collection_group = 'shared'
        WHERE kind = 'auctions'
          AND category = 'clearance'
          AND collection_group IN ('executive_agencies', 'amval_tamliki')
    """))
