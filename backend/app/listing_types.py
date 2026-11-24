"""Types available in the unified notice index and their SQL projections."""
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import DateTime, Numeric, String, Text, cast, func, literal, select
from sqlalchemy.sql import Select

from app.db.models import Auction, Tender


def auction_rows() -> Select:
    return select(
        literal("auction").label("record_type"),
        Auction.id.label("record_id"),
        Auction.source.label("source"),
        Auction.collection_group.label("collection_group"),
        Auction.category.label("category"),
        cast(literal(None), String).label("type_name"),
        func.coalesce(Auction.title, Auction.item_title).label("title"),
        func.coalesce(
            Auction.auction_no,
            Auction.auction_reference_no,
            Auction.source_party_id,
        ).label("record_number"),
        Auction.organization.label("organization"),
        Auction.province.label("province"),
        Auction.city.label("city"),
        cast(Auction.state, Text).label("state"),
        func.coalesce(Auction.site_show_start_at, Auction.publish_start_at).label("announcement_at"),
        Auction.proposal_deadline.label("deadline_at"),
        cast(literal(None), DateTime(timezone=True)).label("documents_deadline_at"),
        Auction.base_total_price.label("base_total_price"),
        Auction.money_unit.label("money_unit"),
        Auction.has_keyword_match.label("has_keyword_match"),
    )


def tender_rows() -> Select:
    return select(
        literal("tender").label("record_type"),
        Tender.id.label("record_id"),
        Tender.source.label("source"),
        literal(None, type_=String(32)).label("collection_group"),
        literal(None, type_=String(24)).label("category"),
        Tender.type_name.label("type_name"),
        Tender.title.label("title"),
        func.coalesce(Tender.tender_number, Tender.source_tender_id).label("record_number"),
        Tender.organization.label("organization"),
        Tender.province.label("province"),
        Tender.city.label("city"),
        cast(Tender.state, Text).label("state"),
        Tender.public_notification_at.label("announcement_at"),
        Tender.proposal_deadline_at.label("deadline_at"),
        Tender.documents_deadline_at.label("documents_deadline_at"),
        literal(None, type_=Numeric(24, 2)).label("base_total_price"),
        literal(None, type_=String(30)).label("money_unit"),
        Tender.has_keyword_match.label("has_keyword_match"),
    )


@dataclass(frozen=True)
class ListingType:
    count_key: str
    label: str
    project: Callable[[], Select]
    search_fields: tuple[Any, ...]


# Projections must return the same named columns in the same order.
LISTING_TYPES = {
    "auction": ListingType("auctions", "مزایده", auction_rows, (
        Auction.title,
        Auction.description,
        Auction.organization,
        Auction.province,
        Auction.city,
        Auction.auction_no,
        Auction.auction_reference_no,
        Auction.source_party_id,
        Auction.item_title,
        Auction.item_reference_no,
        Auction.asset_type,
    )),
    "tender": ListingType("tenders", "مناقصه", tender_rows, (
        Tender.title,
        Tender.description,
        Tender.tender_number,
        Tender.source_tender_id,
        Tender.type_name,
        Tender.organization,
        Tender.province,
        Tender.city,
    )),
}
