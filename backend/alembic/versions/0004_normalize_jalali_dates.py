"""Add normalized Jalali/Gregorian date columns for auction and tender filtering.

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

from app.services.date_normalization import parse_setad_datetime


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


AUCTION_DATE_FIELDS = {
    "proposal_start": "fromProposalDate",
    "proposal_deadline": "toProposalDate",
    "site_show_start_at": "fromSiteShowDate",
    "site_show_end_at": "toSiteShowDate",
    "publish_start_at": "publishStartDate",
    "publish_finish_at": "publishFinishDate",
    "winner_announce_at": "winnerAnnounceDate",
    "opened_at": "openedDate",
    "opening_at": "openingDate",
    "last_modify_at": "lastModifyDate",
    "source_created_at": "createDate",
    "trust_opened_at": "trustOpenedDate",
}


def _auction_source_date(payload, field):
    party = payload.get("auctionParty") or {}
    auction = party.get("auction") or {}
    for container in (auction, party, payload):
        value = container.get(field)
        if value not in (None, ""):
            return parse_setad_datetime(value)
    return None


def upgrade():
    date_columns = [
        ("auctions", "site_show_start_at"),
        ("auctions", "site_show_end_at"),
        ("auctions", "publish_start_at"),
        ("auctions", "publish_finish_at"),
        ("auctions", "winner_announce_at"),
        ("auctions", "opened_at"),
        ("auctions", "opening_at"),
        ("auctions", "last_modify_at"),
        ("auctions", "source_created_at"),
        ("auctions", "trust_opened_at"),
        ("tenders", "public_notification_at"),
        ("tenders", "documents_deadline_at"),
        ("tenders", "proposal_deadline_at"),
        ("tenders", "opening_at"),
    ]
    for table, column in date_columns:
        op.add_column(table, sa.Column(column, sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_auctions_site_show_start", "auctions", ["site_show_start_at"])
    op.create_index("ix_auctions_publish_start", "auctions", ["publish_start_at"])
    op.create_index("ix_tenders_public_notification_at", "tenders", ["public_notification_at"])
    op.create_index("ix_tenders_proposal_deadline_at", "tenders", ["proposal_deadline_at"])
    op.create_index("ix_auctions_location", "auctions", ["province", "city"])
    op.create_index("ix_auctions_base_total_price", "auctions", ["base_total_price"])
    op.create_index("ix_auctions_state", "auctions", ["state"])
    op.create_index("ix_tenders_location", "tenders", ["province", "city"])
    op.create_index("ix_tenders_state_type", "tenders", ["state", "type_name"])

    connection = op.get_bind()

    auction_rows = connection.execute(
        sa.text("SELECT id, raw_payload FROM auctions")
    ).mappings()
    for row in auction_rows:
        payload = row["raw_payload"] or {}
        values = {
            column: _auction_source_date(payload, source_field)
            for column, source_field in AUCTION_DATE_FIELDS.items()
        }
        connection.execute(
            sa.text(
                """
                UPDATE auctions SET
                    proposal_start = COALESCE(proposal_start, :proposal_start),
                    proposal_deadline = COALESCE(proposal_deadline, :proposal_deadline),
                    site_show_start_at = :site_show_start_at,
                    site_show_end_at = :site_show_end_at,
                    publish_start_at = :publish_start_at,
                    publish_finish_at = :publish_finish_at,
                    winner_announce_at = :winner_announce_at,
                    opened_at = :opened_at,
                    opening_at = :opening_at,
                    last_modify_at = :last_modify_at,
                    source_created_at = :source_created_at,
                    trust_opened_at = :trust_opened_at
                WHERE id = :id
                """
            ),
            {"id": row["id"], **values},
        )

    tender_rows = connection.execute(
        sa.text(
            """
            SELECT id, public_notification_date, documents_deadline_date,
                   proposal_deadline_date, opening_date
            FROM tenders
            """
        )
    ).mappings()
    for row in tender_rows:
        connection.execute(
            sa.text(
                """
                UPDATE tenders SET
                    public_notification_at = :public_notification_at,
                    documents_deadline_at = :documents_deadline_at,
                    proposal_deadline_at = :proposal_deadline_at,
                    opening_at = :opening_at
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "public_notification_at": parse_setad_datetime(row["public_notification_date"]),
                "documents_deadline_at": parse_setad_datetime(row["documents_deadline_date"]),
                "proposal_deadline_at": parse_setad_datetime(row["proposal_deadline_date"]),
                "opening_at": parse_setad_datetime(row["opening_date"]),
            },
        )


def downgrade():
    op.drop_index("ix_tenders_proposal_deadline_at", table_name="tenders")
    op.drop_index("ix_tenders_public_notification_at", table_name="tenders")
    op.drop_index("ix_auctions_publish_start", table_name="auctions")
    op.drop_index("ix_auctions_site_show_start", table_name="auctions")
    op.drop_index("ix_tenders_state_type", table_name="tenders")
    op.drop_index("ix_tenders_location", table_name="tenders")
    op.drop_index("ix_auctions_state", table_name="auctions")
    op.drop_index("ix_auctions_base_total_price", table_name="auctions")
    op.drop_index("ix_auctions_location", table_name="auctions")

    for table, column in [
        ("auctions", "site_show_start_at"),
        ("auctions", "site_show_end_at"),
        ("auctions", "publish_start_at"),
        ("auctions", "publish_finish_at"),
        ("auctions", "winner_announce_at"),
        ("auctions", "opened_at"),
        ("auctions", "opening_at"),
        ("auctions", "last_modify_at"),
        ("auctions", "source_created_at"),
        ("auctions", "trust_opened_at"),
        ("tenders", "public_notification_at"),
        ("tenders", "documents_deadline_at"),
        ("tenders", "proposal_deadline_at"),
        ("tenders", "opening_at"),
    ]:
        op.drop_column(table, column)
