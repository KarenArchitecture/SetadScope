from __future__ import annotations

from io import BytesIO
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Tender
from app.db.session import get_db


router = APIRouter(tags=["tenders"])

ORDER_FIELDS = {
    "source_tender_id": Tender.source_tender_id,
    "tender_number": Tender.tender_number,
    "title": Tender.title,
    "tender_type": Tender.tender_type,
    "type_name": Tender.type_name,
    "organization": Tender.organization,
    "province": Tender.province,
    "city": Tender.city,
    "public_notification_date": Tender.public_notification_date,
    "documents_deadline_date": Tender.documents_deadline_date,
    "proposal_deadline_date": Tender.proposal_deadline_date,
    "opening_date": Tender.opening_date,
    "state": Tender.state,
    "first_seen_at": Tender.first_seen_at,
    "updated_at": Tender.updated_at,
}


def tender_to_dict(tender: Tender, include_raw: bool = False) -> dict:
    result = {
        "id": tender.id,
        "source_tender_id": tender.source_tender_id,
        "tender_number": tender.tender_number,
        "title": tender.title,
        "type": tender.tender_type,
        "type_name": tender.type_name,
        "organization": tender.organization,
        "province": tender.province,
        "city": tender.city,
        "description": tender.description,
        "state": tender.state,
        "public_notification_date": tender.public_notification_date,
        "documents_deadline_date": tender.documents_deadline_date,
        "proposal_deadline_date": tender.proposal_deadline_date,
        "opening_date": tender.opening_date,
        "first_seen_at": tender.first_seen_at,
        "updated_at": tender.updated_at,
    }
    if include_raw:
        result["raw_payload"] = tender.raw_payload
    return result


def filtered_tender_query(search: str | None):
    query = select(Tender)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Tender.title.ilike(term),
                Tender.tender_number.ilike(term),
                Tender.type_name.ilike(term),
                Tender.organization.ilike(term),
                Tender.description.ilike(term),
                Tender.province.ilike(term),
                Tender.city.ilike(term),
            )
        )
    return query


def excel_safe(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


@router.get("/api/tenders")
def get_tenders(
    search: str | None = None,
    sort_by: str = Query("public_notification_date"),
    sort_dir: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if sort_by not in ORDER_FIELDS:
        raise HTTPException(status_code=422, detail="Unsupported sort_by column")

    query = filtered_tender_query(search)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    column = ORDER_FIELDS[sort_by]
    ordering = column.asc().nulls_last() if sort_dir == "asc" else column.desc().nulls_last()
    rows = db.scalars(
        query.order_by(ordering, Tender.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return {
        "items": [tender_to_dict(row) for row in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": (total + page_size - 1) // page_size,
    }


@router.get("/api/tenders/export.xlsx")
def export_tenders(
    search: str | None = None,
    db: Session = Depends(get_db),
):
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("SetadScope Tenders")
    sheet.append(
        [
            "شناسه منبع",
            "شماره مناقصه",
            "عنوان",
            "نوع فراخوان",
            "سازمان",
            "استان",
            "شهر",
            "شرح",
            "تاریخ انتشار",
            "مهلت دریافت اسناد",
            "مهلت پیشنهاد",
            "تاریخ بازگشایی",
            "وضعیت",
        ]
    )

    query = filtered_tender_query(search).order_by(
        Tender.public_notification_date.desc().nulls_last(),
        Tender.id.asc(),
    )
    for row in db.scalars(query).yield_per(500):
        sheet.append(
            [
                excel_safe(row.source_tender_id),
                excel_safe(row.tender_number),
                excel_safe(row.title),
                excel_safe(row.type_name),
                excel_safe(row.organization),
                excel_safe(row.province),
                excel_safe(row.city),
                excel_safe(row.description),
                excel_safe(row.public_notification_date),
                excel_safe(row.documents_deadline_date),
                excel_safe(row.proposal_deadline_date),
                excel_safe(row.opening_date),
                excel_safe(row.state),
            ]
        )

    data = BytesIO()
    workbook.save(data)
    data.seek(0)
    return StreamingResponse(
        data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=setadscope_tenders.xlsx"},
    )


@router.get("/api/tenders/{tender_id}")
def get_tender(tender_id: int, db: Session = Depends(get_db)):
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender listing not found")
    return tender_to_dict(tender, include_raw=True)
