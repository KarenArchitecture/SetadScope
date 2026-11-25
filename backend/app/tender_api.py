from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Tender
from app.services.date_normalization import persian_timestamp
from app.db.session import get_db
from app.services.listing_filters import announced_today, date_range
from app.excel_api import ExportProgress, excel_download, track_excel_export


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
    "announcement_at": Tender.public_notification_at,
    "public_notification_at": Tender.public_notification_at,
    "documents_deadline_at": Tender.documents_deadline_at,
    "proposal_deadline_at": Tender.proposal_deadline_at,
    "opening_at": Tender.opening_at,
    "state": Tender.state,
    "first_seen_at": Tender.first_seen_at,
    "updated_at": Tender.updated_at,
}


def tender_to_dict(tender: Tender, include_raw: bool = False) -> dict:
    result = {
        "id": tender.id,
        "source_tender_id": tender.source_tender_id,
        "has_keyword_match": tender.has_keyword_match,
        "matched_keywords": tender.matched_keywords,
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
        "announcement_at": tender.public_notification_at,
        "documents_deadline_date": tender.documents_deadline_date,
        "proposal_deadline_date": tender.proposal_deadline_date,
        "opening_date": tender.opening_date,
        "public_notification_at": tender.public_notification_at,
        "documents_deadline_at": tender.documents_deadline_at,
        "proposal_deadline_at": tender.proposal_deadline_at,
        "opening_at": tender.opening_at,
        "first_seen_at": tender.first_seen_at,
        "updated_at": tender.updated_at,
    }
    if include_raw:
        result["raw_payload"] = tender.raw_payload
    return result


def filtered_tender_query(
    search: str | None,
    province: str | None = None,
    city: str | None = None,
    state: str | None = None,
    type_name: str | None = None,
    announcement_from: str | None = None,
    announcement_to: str | None = None,
    deadline_from: str | None = None,
    deadline_to: str | None = None,
    documents_deadline_from: str | None = None,
    documents_deadline_to: str | None = None,
    matched_only: bool = False,
    today_only: bool = False,
    status: Literal["all", "active", "archive"] = "all",
):
    query = select(Tender)
    if status != "all":
        now = datetime.now(timezone.utc)
        if status == "active":
            query = query.where(Tender.proposal_deadline_at > now)
        else:
            query = query.where(Tender.proposal_deadline_at <= now)
    if matched_only:
        query = query.where(Tender.has_keyword_match.is_(True))
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
    if province:
        query = query.where(Tender.province == province)
    if city:
        query = query.where(Tender.city == city)
    if state:
        query = query.where(Tender.state.in_(("PUBLISHED", "منتشر شده", "منتشرشده", "منتشر‌شده"))
                            if state == "PUBLISHED" else Tender.state == state)
    if type_name:
        query = query.where(Tender.type_name == type_name)

    query = query.where(
        *date_range(Tender.public_notification_at, "announcement", announcement_from, announcement_to),
        *date_range(Tender.proposal_deadline_at, "deadline", deadline_from, deadline_to),
        *date_range(Tender.documents_deadline_at, "documents_deadline", documents_deadline_from, documents_deadline_to),
    )
    if today_only:
        query = query.where(*announced_today(Tender.public_notification_at))
    return query


def tender_archive_stats(db: Session) -> dict[str, int]:
    return {
        "total": db.scalar(select(func.count(Tender.id))) or 0,
        "matched_total": db.scalar(select(func.count(Tender.id)).where(Tender.has_keyword_match.is_(True))) or 0,
        "province_count": db.scalar(
            select(func.count(func.distinct(Tender.province))).where(Tender.province.is_not(None))
        ) or 0,
        "city_count": db.scalar(
            select(func.count(func.distinct(Tender.city))).where(Tender.city.is_not(None))
        ) or 0,
        "organization_count": db.scalar(
            select(func.count(func.distinct(Tender.organization))).where(Tender.organization.is_not(None))
        ) or 0,
        "type_count": db.scalar(
            select(func.count(func.distinct(Tender.type_name))).where(Tender.type_name.is_not(None))
        ) or 0,
    }


def tender_filter_options(db: Session) -> dict[str, list]:
    provinces = db.scalars(
        select(Tender.province)
        .where(Tender.province.is_not(None))
        .distinct()
        .order_by(Tender.province)
    ).all()
    city_rows = db.execute(
        select(Tender.city, Tender.province)
        .where(Tender.city.is_not(None), Tender.province.is_not(None))
        .distinct()
        .order_by(Tender.province, Tender.city)
    ).all()
    states = db.scalars(
        select(Tender.state)
        .where(Tender.state.is_not(None))
        .distinct()
        .order_by(Tender.state)
    ).all()
    types = db.scalars(
        select(Tender.type_name)
        .where(Tender.type_name.is_not(None))
        .distinct()
        .order_by(Tender.type_name)
    ).all()
    return {
        "provinces": list(provinces),
        "cities": [{"city": city, "province": province} for city, province in city_rows],
        "states": list(states),
        "types": list(types),
    }

def excel_safe(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


@router.get("/api/tenders")
def get_tenders(
    search: str | None = None,
    matched_only: bool = False,
    today_only: bool = False,
    status: Literal["all", "active", "archive"] = "all",
    province: str | None = None,
    city: str | None = None,
    state: str | None = None,
    type_name: str | None = None,
    announcement_from: str | None = None,
    announcement_to: str | None = None,
    deadline_from: str | None = None,
    deadline_to: str | None = None,
    documents_deadline_from: str | None = None,
    documents_deadline_to: str | None = None,
    sort_by: str = Query("public_notification_at"),
    sort_dir: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if sort_by not in ORDER_FIELDS:
        raise HTTPException(status_code=422, detail="Unsupported sort_by column")

    query = filtered_tender_query(
        search, province, city, state, type_name,
        announcement_from, announcement_to, deadline_from, deadline_to,
        documents_deadline_from, documents_deadline_to,
        matched_only=matched_only, status=status, today_only=today_only,
    )
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
        "archive_stats": tender_archive_stats(db),
        "filter_options": tender_filter_options(db),
    }


@router.get("/api/tenders/export.xlsx")
@router.post("/api/tenders/export.xlsx")
def export_tenders(
    search: str | None = None,
    matched_only: bool = False,
    today_only: bool = False,
    status: Literal["all", "active", "archive"] = "all",
    province: str | None = None,
    city: str | None = None,
    state: str | None = None,
    type_name: str | None = None,
    announcement_from: str | None = None,
    announcement_to: str | None = None,
    deadline_from: str | None = None,
    deadline_to: str | None = None,
    documents_deadline_from: str | None = None,
    documents_deadline_to: str | None = None,
    sort_by: str = Query("public_notification_at"),
    sort_dir: Literal["asc", "desc"] = "desc",
    selected_ids: list[int] | None = Body(default=None, embed=True),
    progress: ExportProgress | None = Depends(track_excel_export),
    db: Session = Depends(get_db),
):
    if sort_by not in ORDER_FIELDS:
        raise HTTPException(status_code=422, detail="Unsupported sort_by column")
    query = (
        select(Tender).where(Tender.id.in_(set(selected_ids)))
        if selected_ids
        else filtered_tender_query(
            search, province, city, state, type_name,
            announcement_from, announcement_to, deadline_from, deadline_to,
            documents_deadline_from, documents_deadline_to,
            matched_only=matched_only, status=status, today_only=today_only,
        )
    )
    column = ORDER_FIELDS[sort_by]
    ordering = column.asc().nulls_last() if sort_dir == "asc" else column.desc().nulls_last()
    query = query.order_by(ordering, Tender.id.asc())
    headers = [
        "شناسه منبع", "شماره مناقصه", "عنوان", "نوع فراخوان", "سازمان",
        "استان", "شهر", "شرح", "تاریخ انتشار", "مهلت دریافت اسناد",
        "مهلت پیشنهاد", "تاریخ بازگشایی", "وضعیت",
    ]

    def export_rows():
        for row in db.scalars(query).yield_per(500):
            yield [
                excel_safe(row.source_tender_id),
                excel_safe(row.tender_number),
                excel_safe(row.title),
                excel_safe(row.type_name),
                excel_safe(row.organization),
                excel_safe(row.province),
                excel_safe(row.city),
                excel_safe(row.description),
                persian_timestamp(row.public_notification_at or row.public_notification_date),
                persian_timestamp(row.documents_deadline_at or row.documents_deadline_date),
                persian_timestamp(row.proposal_deadline_at or row.proposal_deadline_date),
                persian_timestamp(row.opening_at or row.opening_date),
                excel_safe("منتشر شده" if row.state == "PUBLISHED" else row.state),
            ]

    return excel_download(
        db, query, progress, "setadscope_tenders.xlsx",
        "مناقصه‌ها", "SetadScopeTenders", headers, export_rows,
        widths=[25, 24, 53, 28, 40, 21, 21, 66, 25, 25, 25, 25, 20],
    )


@router.get("/api/tenders/{tender_id}")
def get_tender(tender_id: int, db: Session = Depends(get_db)):
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender listing not found")
    return tender_to_dict(tender, include_raw=True)
