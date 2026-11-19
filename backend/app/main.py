from __future__ import annotations
from datetime import datetime, timezone
from io import BytesIO
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from app.db.models import Auction
from app.db.session import get_db

app = FastAPI(title="SetadScope API", version="0.2.0")
ORDER_FIELDS = {
    "title": Auction.title, "organization": Auction.organization,
    "province": Auction.province, "city": Auction.city,
    "base_total_price": Auction.base_total_price,
    "proposal_start": Auction.proposal_start,
    "proposal_deadline": Auction.proposal_deadline,
    "document_deadline": Auction.document_deadline,
    "total_volume_m3": Auction.total_volume_m3,
    "first_seen_at": Auction.first_seen_at,
}

def auction_to_dict(a: Auction) -> dict:
    return {
        "id": a.id, "source_party_id": a.source_party_id,
        "auction_id": a.auction_id, "auction_no": a.auction_no,
        "auction_reference_no": a.auction_reference_no,
        "title": a.title, "description": a.description,
        "organization": a.organization, "province": a.province,
        "city": a.city, "state": a.state,
        "proposal_start": a.proposal_start,
        "proposal_deadline": a.proposal_deadline,
        "document_deadline": a.document_deadline,
        "base_total_price": a.base_total_price,
        "trust_amount": a.trust_amount,
        "total_volume_m3": a.total_volume_m3,
        "money_unit": a.money_unit,
        "matched_keywords": a.matched_keywords,
        "source_url": a.source_url,
        "first_seen_at": a.first_seen_at,
        "updated_at": a.updated_at,
    }

def filtered_query(status: str, search: str | None):
    query = select(Auction)
    now = datetime.now(timezone.utc)
    if status == "active":
        query = query.where(Auction.proposal_deadline > now)
    elif status == "archive":
        query = query.where(Auction.proposal_deadline <= now)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(or_(
            Auction.title.ilike(term), Auction.description.ilike(term),
            Auction.organization.ilike(term), Auction.city.ilike(term),
        ))
    return query

@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(select(1)).scalar_one()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ok", "database": "ok"}

@app.get("/api/auctions")
def get_auctions(
    search: str | None = None,
    status: Literal["active", "archive", "all"] = "active",
    sort_by: str = Query("proposal_deadline"),
    sort_dir: Literal["asc", "desc"] = "asc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if sort_by not in ORDER_FIELDS:
        raise HTTPException(status_code=422, detail="Unsupported sort_by column")
    query = filtered_query(status, search)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    column = ORDER_FIELDS[sort_by]
    ordering = column.asc().nulls_last() if sort_dir == "asc" else column.desc().nulls_last()
    rows = db.scalars(query.order_by(ordering, Auction.id.asc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "items": [auction_to_dict(a) for a in rows],
        "page": page, "page_size": page_size,
        "total": total, "pages": (total + page_size - 1) // page_size,
    }

@app.get("/api/auctions/export.xlsx")
def export_auctions(
    status: Literal["active", "archive", "all"] = "active",
    search: str | None = None,
    db: Session = Depends(get_db),
):
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("SetadScope")
    sheet.append([
        "شناسه", "عنوان", "شرح کلی", "کلمات منطبق", "سازمان", "استان", "شهر",
        "شروع پیشنهاد", "مهلت پیشنهاد", "مهلت دریافت اسناد",
        "مبلغ پایه (واحد تأییدنشده)", "حجم کل (مترمکعب)", "شماره آگهی", "لینک منبع",
    ])
    query = filtered_query(status, search).order_by(Auction.proposal_deadline, Auction.id)
    for a in db.scalars(query).yield_per(500):
        sheet.append([
            a.source_party_id, a.title, a.description, ", ".join(a.matched_keywords or []),
            a.organization, a.province, a.city, str(a.proposal_start or ""),
            str(a.proposal_deadline), str(a.document_deadline or ""),
            float(a.base_total_price) if a.base_total_price is not None else None,
            float(a.total_volume_m3) if a.total_volume_m3 is not None else None,
            a.auction_no, a.source_url,
        ])
    data = BytesIO()
    workbook.save(data)
    data.seek(0)
    return StreamingResponse(
        data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=setadscope_auctions.xlsx"},
    )

@app.get("/api/auctions/{auction_id}")
def get_auction(auction_id: int, db: Session = Depends(get_db)):
    row = db.get(Auction, auction_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Auction listing not found")
    return auction_to_dict(row)
