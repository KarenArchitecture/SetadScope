"""Lossless auction projection and idempotent import across collection groups."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import cast, or_
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import Session

from app.db.models import Auction, IngestionRun
from app.services.date_normalization import parse_setad_datetime
from app.services.ingestion import to_decimal
from app.services.keyword_matching import matched_keywords
from app.services.keyword_settings import configured_keywords
from setad_scope.collectors.auction_sources.registry import (
    ALL_CATEGORIES,
    CATEGORIES_BY_GROUP,
    COLLECTION_GROUPS,
    SOURCE_REGISTRY,
    resolve_collection_group,
    source_for,
)

AUCTION_CATEGORIES = ALL_CATEGORIES
AUCTION_CATEGORIES_BY_GROUP = CATEGORIES_BY_GROUP
SOURCES_BY_GROUP = {
    group: {category: source.source for category, source in sources.items()}
    for group, sources in SOURCE_REGISTRY.items()
}
# Backward-compatible category-to-source mapping for existing imports and tests.
SOURCES = {
    category: source_for(category).source
    for category in AUCTION_CATEGORIES
}


def _dict(value):
    return value if isinstance(value, dict) else {}


def _name(value):
    if isinstance(value, dict):
        return value.get("name")
    return value if isinstance(value, str) else None


def _date(obj: dict, key: str):
    return parse_setad_datetime(obj.get(key))


def _id(value):
    return str(value) if value is not None and value != "" else None


def project_auction(
    record: dict,
    category: str,
    keywords: tuple[str, ...] | None = None,
    collection_group: str | None = None,
) -> tuple[dict | None, str]:
    """Return normalized row and status. Store all rows, including nonmatches and expired."""
    group = resolve_collection_group(category, collection_group)
    source_config = source_for(category, group)
    if not isinstance(record, dict):
        return None, "invalid"
    party = _dict(record.get("auctionParty"))
    details = party if category == "movable" else record
    auction = (
        _dict(party.get("auction"))
        if category == "movable"
        else (_dict(record.get("auction")) or _dict(record.get("immovableAuction")))
    )
    if category in {"minor", "clearance"}:
        auction = record

    if category == "clearance":
        # cartId identifies each central-board card, even if cards share a number.
        record_id = _id(record.get("cartId") or record.get("ticketId"))
    else:
        record_id = _id(details.get("id"))
    if not record_id:
        return None, "missing_id"

    auctioneer = _dict(auction.get("auctioneer"))
    city = (
        _dict(party.get("visitCity")) if category == "movable"
        else _dict(record.get("city") or record.get("propertyCity"))
    )
    if category == "minor" and not city:
        city = _dict(_dict(auctioneer.get("city")))

    if category == "clearance":
        organization = record.get("orgName")
        province = record.get("provinceName")
        city_name = record.get("cityName")
        title = record.get("title") or ""
        description = None
    else:
        organization = auctioneer.get("name")
        province = _name(city.get("province")) or _name(_dict(auctioneer.get("city")).get("province"))
        city_name = _name(city)
        title = auction.get("title") or details.get("title") or ""
        description = auction.get("description") or details.get("description")

    item_title = (
        details.get("title") if category in {"rental", "immovable"} else
        party.get("title") if category == "movable" else
        record.get("title") if category == "clearance" else
        None
    )
    item_reference_no = (
        _id(record.get("rentalItemNo")) if category == "rental" else
        _id(record.get("no")) if category == "immovable" else
        _id(party.get("partyNo")) if category == "movable" else
        _id(record.get("partyNumber")) if category == "clearance" else
        None
    )

    if category == "movable":
        price = party.get("baseTotalPrice")
        price_type = "sale_base"
        trust_amount = party.get("trustAmount")
        asset_type = party.get("itemGroupName")
    elif category == "immovable":
        price = record.get("organizationBasePrice")
        price_type = "property_sale_base"
        trust_amount = record.get("trustAmount")
        asset_type = _name(record.get("type"))
    elif category == "rental":
        price = record.get("rentBasePrice")
        price_type = "rental_base"
        trust_amount = record.get("trustAmount")
        asset_type = _name(record.get("type")) or record.get("typeName")
    elif category == "minor":
        price = record.get("totalBasePrice")
        price_type = "minor_sale_base"
        trust_amount = record.get("amountTrust")
        asset_type = _name(record.get("type"))
    else:
        price = record.get("basePrice")
        price_type = "clearance_base"
        trust_amount = None
        asset_type = record.get("categoryName")

    description = description or details.get("propertyDescription") or details.get("specification")
    keywords = matched_keywords(
        title, description, item_title, asset_type,
        details.get("address"), details.get("visitAddress"),
        record.get("categoryName"),
        keywords=keywords,
    )

    if category == "clearance":
        date_start = parse_setad_datetime(str(record.get("jalaliFromProposalDate") or "").replace(" - ", " "))
        date_deadline = parse_setad_datetime(str(record.get("jalaliSendDeadlineDate") or "").replace(" - ", " "))
        doc_deadline = parse_setad_datetime(str(record.get("jalaliDocumentDeadlineDate") or "").replace(" - ", " "))
        announce = _date(record, "insertDate")
        last_modify = parse_setad_datetime(str(record.get("jalaliLastEditDate") or "").replace(" - ", " "))
        auction_no = _id(record.get("number"))
        auction_id = _id(record.get("tableId"))
        state = _id(record.get("aucState"))
        source_url = (
            "https://fe.setadiran.ir/centralboard/?tagCode=342&selectedOrganization=5315&boardCode=3"
            if group == "amval_tamliki"
            else "https://fe.setadiran.ir/centralboard/?tagCode=341,343&boardCode=3"
        )
    else:
        date_start = _date(auction, "fromProposalDate")
        date_deadline = _date(auction, "toProposalDate")
        doc_deadline = _date(auction, "receiptDocumentDate")
        announce = _date(auction, "fromSiteShowDate")
        last_modify = _date(auction, "lastModifyDate")
        auction_no = _id(auction.get("auctionNo"))
        auction_id = _id(auction.get("id"))
        state = auction.get("state") or details.get("state")
        source_url = "https://eauc.setadiran.ir/eauc/welcome.action?gateway=setad"

    normalized = {
        "collection_group": group,
        "source": source_config.source,
        "source_party_id": record_id,
        "category": category,
        "has_keyword_match": bool(keywords),
        "item_title": item_title,
        "item_reference_no": item_reference_no,
        "asset_type": asset_type,
        "price_type": price_type,
        "rent_duration_months": record.get("rentMonthDuration") if category == "rental" else None,
        "rent_duration_days": record.get("rentDayDuration") if category == "rental" else None,
        "auction_id": auction_id,
        "auction_no": auction_no,
        "auction_reference_no": _id(auction.get("auctionReferenceNo")),
        "title": title or item_title,
        "description": description,
        "organization": organization,
        "province": province,
        "city": city_name,
        "state": state,
        "proposal_start": date_start,
        "proposal_deadline": date_deadline,
        "document_deadline": doc_deadline,
        "site_show_start_at": announce,
        "site_show_end_at": _date(auction, "toSiteShowDate") if category != "clearance" else date_deadline,
        "publish_start_at": _date(auction, "publishStartDate") if category != "clearance" else announce,
        "publish_finish_at": _date(auction, "publishFinishDate") if category != "clearance" else None,
        "winner_announce_at": _date(auction, "winnerAnnounceDate") if category != "clearance" else None,
        "opened_at": _date(auction, "openedDate") if category != "clearance" else None,
        "opening_at": _date(auction, "openingDate") if category != "clearance" else None,
        "last_modify_at": last_modify,
        "source_created_at": _date(auction, "createDate") if category != "clearance" else announce,
        "trust_opened_at": _date(auction, "trustOpenedDate") if category != "clearance" else None,
        "base_total_price": to_decimal(price),
        "trust_amount": to_decimal(trust_amount),
        "total_volume_m3": None,
        "money_unit": "IRR" if category == "clearance" else None,
        "source_url": source_url,
        "matched_keywords": keywords,
        "raw_payload": record,
    }
    return normalized, "matched" if keywords else "unmatched"


def import_auction_pages(
    db: Session,
    paths: list[Path],
    category: str,
    progress_callback=None,
    collection_group: str | None = None,
    *,
    incomplete_reason: str | None = None,
) -> dict[str, int]:
    group = resolve_collection_group(category, collection_group)
    if category not in AUCTION_CATEGORIES:
        raise ValueError(f"Unknown auction category: {category}")
    totals = {
        "fetched": 0,
        "matched": 0,
        "stored": 0,
        "changed": 0,
        "unchanged": 0,
        "skipped_missing_id": 0,
        "skipped_invalid_record": 0,
    }
    # Keep the legacy constructor shape for downstream source-contract checks;
    # assign the new scope explicitly before the run is persisted.
    run = IngestionRun(status="running", kind="auctions", category=category)
    run.collection_group = group
    db.add(run)
    db.commit()
    run_id = run.id
    try:
        active_keywords = configured_keywords(db)
        for i, path in enumerate(paths, start=1):
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = payload.get("content") if category == "clearance" else payload.get("gridModel")
            if not isinstance(rows, list):
                raise ValueError(f"Expected array missing in {path}")
            for record in rows:
                totals["fetched"] += 1
                item, status = project_auction(
                    record, category, keywords=active_keywords, collection_group=group,
                )
                if item is None:
                    totals["skipped_missing_id" if status == "missing_id" else "skipped_invalid_record"] += 1
                    continue
                if item["has_keyword_match"]:
                    totals["matched"] += 1
                stmt = insert(Auction).values(**item)
                identity_fields = {"collection_group", "source", "source_party_id"}
                update_values = {
                    key: getattr(stmt.excluded, key)
                    for key in item
                    if key not in identity_fields
                }
                changed_conditions = [
                    (
                        cast(Auction.matched_keywords, JSONB).is_distinct_from(
                            cast(stmt.excluded.matched_keywords, JSONB)
                        )
                        if key == "matched_keywords"
                        else getattr(Auction, key).is_distinct_from(getattr(stmt.excluded, key))
                    )
                    for key in item
                    if key not in identity_fields
                ]
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_auctions_group_source_party",
                    set_={**update_values, "updated_at": datetime.now(timezone.utc)},
                    where=or_(*changed_conditions),
                ).returning(Auction.id)
                changed_id = db.execute(stmt).scalar_one_or_none()
                totals["stored"] += 1
                if changed_id is None:
                    totals["unchanged"] += 1
                else:
                    totals["changed"] += 1
            db.commit()
            if progress_callback:
                progress_callback({"pages_completed": i, "total_pages": len(paths), **totals})
        run = db.get(IngestionRun, run_id)
        run.status = "failed" if incomplete_reason else "success"
        run.error = incomplete_reason
        run.finished_at = datetime.now(timezone.utc)
        run.fetched = totals["fetched"]
        run.matched = totals["matched"]
        run.stored = totals["stored"]
        db.commit()
        return totals
    except Exception as exc:
        db.rollback()
        failed = db.get(IngestionRun, run_id)
        failed.status = "failed"
        failed.error = str(exc)[:5000]
        failed.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise
