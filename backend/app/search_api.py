from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Numeric, String, Text, cast, func, literal, or_, select, union_all
from sqlalchemy.orm import Session

from app.db.models import Auction, Tender
from app.db.session import get_db


router = APIRouter(tags=["global-search"])

AUCTION_CATEGORIES = {
    "movable": "منقول",
    "immovable": "غیرمنقول",
    "rental": "اجاره",
    "minor": "جزئی",
    "clearance": "حراج اموال تملیکی",
}
SOURCE_LABELS = {
    "setad_main_estate": "سامانه مزایده ستاد · منقول",
    "setad_immovable": "سامانه مزایده ستاد · غیرمنقول",
    "setad_rental": "سامانه مزایده ستاد · اجاره",
    "setad_minor": "سامانه مزایده ستاد · جزئی",
    "setad_clearance_5315": "سامانه اموال تملیکی",
    "setad_tender": "سامانه مناقصات ستاد",
}
SORT_COLUMNS = {
    "title": "title",
    "organization": "organization",
    "province": "province",
    "city": "city",
    "announcement_at": "announcement_at",
    "deadline_at": "deadline_at",
    "base_total_price": "base_total_price",
    "record_type": "record_type",
    "source": "source",
}


def _searchable_rows(
    search: str | None,
    source: str | None,
    province: str | None,
    city: str | None,
    category: str | None,
    status: str,
    matched_only: bool,
):
    auction_query = select(
        literal("auction").label("record_type"),
        Auction.id.label("record_id"),
        Auction.source.label("source"),
        Auction.category.label("category"),
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
        Auction.base_total_price.label("base_total_price"),
        Auction.money_unit.label("money_unit"),
        Auction.has_keyword_match.label("has_keyword_match"),
    )
    tender_query = select(
        literal("tender").label("record_type"),
        Tender.id.label("record_id"),
        Tender.source.label("source"),
        literal(None, type_=String(24)).label("category"),
        Tender.title.label("title"),
        func.coalesce(Tender.tender_number, Tender.source_tender_id).label("record_number"),
        Tender.organization.label("organization"),
        Tender.province.label("province"),
        Tender.city.label("city"),
        cast(Tender.state, Text).label("state"),
        Tender.public_notification_at.label("announcement_at"),
        Tender.proposal_deadline_at.label("deadline_at"),
        literal(None, type_=Numeric(24, 2)).label("base_total_price"),
        literal(None, type_=String(30)).label("money_unit"),
        Tender.has_keyword_match.label("has_keyword_match"),
    )

    if source:
        auction_query = auction_query.where(Auction.source == source)
        tender_query = tender_query.where(Tender.source == source)
    if province:
        auction_query = auction_query.where(Auction.province == province)
        tender_query = tender_query.where(Tender.province == province)
    if city:
        auction_query = auction_query.where(Auction.city == city)
        tender_query = tender_query.where(Tender.city == city)
    if category:
        auction_query = auction_query.where(Auction.category == category)
        tender_query = tender_query.where(False)
    if matched_only:
        auction_query = auction_query.where(Auction.has_keyword_match.is_(True))
        tender_query = tender_query.where(Tender.has_keyword_match.is_(True))

    if status != "all":
        now = datetime.now(timezone.utc)
        if status == "active":
            auction_query = auction_query.where(Auction.proposal_deadline > now)
            tender_query = tender_query.where(Tender.proposal_deadline_at > now)
        else:
            auction_query = auction_query.where(Auction.proposal_deadline <= now)
            tender_query = tender_query.where(Tender.proposal_deadline_at <= now)

    if search and search.strip():
        term = f"%{search.strip()}%"
        auction_query = auction_query.where(
            or_(
                Auction.title.ilike(term),
                Auction.description.ilike(term),
                Auction.organization.ilike(term),
                Auction.province.ilike(term),
                Auction.city.ilike(term),
                Auction.auction_no.ilike(term),
                Auction.auction_reference_no.ilike(term),
                Auction.source_party_id.ilike(term),
                Auction.item_title.ilike(term),
                Auction.item_reference_no.ilike(term),
                Auction.asset_type.ilike(term),
            )
        )
        tender_query = tender_query.where(
            or_(
                Tender.title.ilike(term),
                Tender.description.ilike(term),
                Tender.tender_number.ilike(term),
                Tender.source_tender_id.ilike(term),
                Tender.type_name.ilike(term),
                Tender.organization.ilike(term),
                Tender.province.ilike(term),
                Tender.city.ilike(term),
            )
        )

    return union_all(auction_query, tender_query).subquery("global_listings")


@router.get("/api/search")
def global_search(
    search: str | None = None,
    kind: Literal["all", "auction", "tender"] = "all",
    source: str | None = None,
    category: Literal["movable", "immovable", "rental", "minor", "clearance"] | None = None,
    province: str | None = None,
    city: str | None = None,
    status: Literal["all", "active", "archive"] = "all",
    matched_only: bool = False,
    sort_by: str = Query("announcement_at"),
    sort_dir: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if sort_by not in SORT_COLUMNS:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Unsupported sort_by column")

    rows = _searchable_rows(search, source, province, city, category, status, matched_only)
    base = select(rows)
    auction_count = db.scalar(
        select(func.count()).select_from(rows).where(rows.c.record_type == "auction")
    ) or 0
    tender_count = db.scalar(
        select(func.count()).select_from(rows).where(rows.c.record_type == "tender")
    ) or 0

    if kind != "all":
        base = base.where(rows.c.record_type == kind)

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    column = rows.c[SORT_COLUMNS[sort_by]]
    ordering = column.asc().nulls_last() if sort_dir == "asc" else column.desc().nulls_last()
    records = db.execute(
        base.order_by(ordering, rows.c.record_type.asc(), rows.c.record_id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).mappings().all()

    sources_query = union_all(
        select(Auction.source.label("source")),
        select(Tender.source.label("source")),
    ).subquery()
    source_values = db.scalars(
        select(sources_query.c.source).distinct().order_by(sources_query.c.source)
    ).all()
    provinces_query = union_all(
        select(Auction.province.label("province")).where(Auction.province.is_not(None)),
        select(Tender.province.label("province")).where(Tender.province.is_not(None)),
    ).subquery()
    province_values = db.scalars(
        select(provinces_query.c.province).distinct().order_by(provinces_query.c.province)
    ).all()

    items = []
    for row in records:
        item = dict(row)
        item["id"] = item["record_id"]
        item["row_key"] = f'{item["record_type"]}:{item["record_id"]}'
        item["record_type_label"] = "مزایده" if item["record_type"] == "auction" else "مناقصه"
        item["source_label"] = SOURCE_LABELS.get(item["source"], item["source"])
        item["category_label"] = AUCTION_CATEGORIES.get(item["category"], "—")
        items.append(item)

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": (total + page_size - 1) // page_size,
        "summary": {
            "all": auction_count + tender_count,
            "auctions": auction_count,
            "tenders": tender_count,
        },
        "filter_options": {
            "sources": [
                {"value": value, "label": SOURCE_LABELS.get(value, value)}
                for value in source_values
            ],
            "provinces": list(province_values),
            "categories": [
                {"value": key, "label": value}
                for key, value in AUCTION_CATEGORIES.items()
            ],
        },
    }
