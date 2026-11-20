"""Import collected Setad JSON pages into PostgreSQL; retain keyword matches regardless of date."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import Auction, IngestionRun
from app.services.keyword_matching import matched_keywords

TEHRAN = ZoneInfo("Asia/Tehran")
PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "raw"


def to_datetime(value: object) -> datetime | None:
    """Parse known Gregorian/epoch formats; keep unsupported (e.g. Jalali) values raw."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) or (
        isinstance(value, str) and re.fullmatch(r"\d{13}", value.strip())
    ):
        n = int(value)
        return datetime.fromtimestamp(n / 1000, tz=timezone.utc) if n > 100000000000 else None
    if isinstance(value, str):
        raw = value.strip()
        if raw.startswith("/Date("):
            match = re.match(r"/Date\((\d+)(?:[+-]\d{4})?\)/", raw)
            if match:
                return datetime.fromtimestamp(int(match.group(1)) / 1000, tz=timezone.utc)
        try:
            result = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if not 2000 <= result.year <= 2100:
                return None
            return result.replace(tzinfo=TEHRAN) if result.tzinfo is None else result
        except ValueError:
            return None
    return None


def to_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        n = Decimal(str(value).replace(",", ""))
        return n if n.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def project_record(record: dict, now: datetime | None = None) -> tuple[dict | None, str]:
    """Project a raw Setad row when it matches a requested keyword; do not filter by dates yet."""
    party = record.get("auctionParty") or {}
    auction = party.get("auction") or {}
    party_id = party.get("id")
    if party_id is None:
        return None, "no_id"

    title = auction.get("title") or party.get("title") or record.get("title") or ""
    description = auction.get("description") or party.get("description") or ""
    keywords = matched_keywords(title, description)
    if not keywords:
        return None, "not_matched"

    auctioneer = auction.get("auctioneer") or {}
    city = party.get("visitCity") or {}
    return {
        "source": "setad_main_estate",
        "source_party_id": str(party_id),
        "auction_id": str(auction.get("id")) if auction.get("id") is not None else None,
        "auction_no": str(auction.get("auctionNo")) if auction.get("auctionNo") is not None else None,
        "auction_reference_no": str(auction.get("auctionReferenceNo")) if auction.get("auctionReferenceNo") is not None else None,
        "title": title,
        "description": description or None,
        "organization": auctioneer.get("name"),
        "province": (city.get("province") or {}).get("name"),
        "city": city.get("name"),
        "state": auction.get("state") or party.get("state"),
        "proposal_start": to_datetime(auction.get("fromProposalDate")),
        "proposal_deadline": to_datetime(auction.get("toProposalDate")),
        "document_deadline": None,
        "base_total_price": to_decimal(party.get("baseTotalPrice")),
        "trust_amount": to_decimal(party.get("trustAmount")),
        "total_volume_m3": None,
        "money_unit": None,
        "source_url": None,
        "matched_keywords": keywords,
        "raw_payload": record,
    }, "matched"


def import_pages(db: Session, paths: list[Path], now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    totals = {
        "fetched": 0,
        "matched": 0,
        "stored": 0,
        "skipped_expired": 0,
        "skipped_unknown_deadline": 0,
    }
    run = IngestionRun(status="running")
    db.add(run)
    db.commit()
    run_id = run.id
    try:
        for path in paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            records = payload.get("gridModel")
            if not isinstance(records, list):
                raise ValueError(f"Missing gridModel array: {path}")
            for record in records:
                totals["fetched"] += 1
                item, status = project_record(record, now)
                if item is None:
                    continue
                totals["matched"] += 1
                statement = insert(Auction).values(**item)
                statement = statement.on_conflict_do_update(
                    constraint="uq_auctions_source_party",
                    set_={**item, "updated_at": datetime.now(timezone.utc)},
                )
                db.execute(statement)
                totals["stored"] += 1
            db.commit()
        for key, value in totals.items():
            setattr(run, key, value)
        run.status = "success"
        run.finished_at = datetime.now(timezone.utc)
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
