from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, union_all
from sqlalchemy.orm import Session

from app.listing_types import LISTING_TYPES
from app.db.session import get_db
from app.excel_api import ExportProgress, excel_download, track_excel_export
from app.services.listing_filters import announced_today, date_range
from setad_scope.collectors.auction_sources.registry import resolve_collection_group


router = APIRouter(tags=["global-search"])

AUCTION_CATEGORIES = {
    "movable": "منقول",
    "immovable": "غیرمنقول",
    "rental": "اجاره",
    "minor": "جزئی",
    "clearance": "حراج مشترک",
}
SOURCE_LABELS = {
    "setad_main_estate": "سامانه مزایده ستاد · منقول",
    "setad_immovable": "سامانه مزایده ستاد · غیرمنقول",
    "setad_rental": "سامانه مزایده ستاد · اجاره",
    "setad_minor": "سامانه مزایده ستاد · جزئی",
    "setad_clearance_5315": "سامانه حراج اموال تملیکی (قدیمی)",
    "setad_clearance_shared": "سامانه حراج مشترک ستاد",
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
    "collection_group": "collection_group",
    "state": "state",
    "documents_deadline_at": "documents_deadline_at",
    "category": "category",
}


@dataclass
class AdvancedSearchFilters:
    state: str | None = None
    type_name: str | None = None
    announcement_from: str | None = None
    announcement_to: str | None = None
    deadline_from: str | None = None
    deadline_to: str | None = None
    documents_deadline_from: str | None = None
    documents_deadline_to: str | None = None
    price_min: Annotated[Decimal | None, Query(ge=0)] = None
    price_max: Annotated[Decimal | None, Query(ge=0)] = None
    today_only: bool = False

    def conditions(self, rows):
        columns = rows.c
        conditions = [
            *date_range(columns.announcement_at, "announcement", self.announcement_from, self.announcement_to),
            *date_range(columns.deadline_at, "deadline", self.deadline_from, self.deadline_to),
            *date_range(
                columns.documents_deadline_at, "documents_deadline",
                self.documents_deadline_from, self.documents_deadline_to,
            ),
        ]
        if self.state:
            conditions.append(columns.state == self.state)
        if self.type_name:
            conditions.append(columns.type_name == self.type_name)
        if self.today_only:
            conditions.extend(announced_today(columns.announcement_at))
        if self.price_min is not None and self.price_max is not None and self.price_min > self.price_max:
            raise HTTPException(status_code=422, detail="price_min cannot exceed price_max")
        if self.price_min is not None:
            conditions.append(columns.base_total_price >= self.price_min)
        if self.price_max is not None:
            conditions.append(columns.base_total_price <= self.price_max)
        return conditions


def _searchable_rows(
    search: str | None,
    source: str | None,
    province: str | None,
    city: str | None,
    category: str | None,
    status: str,
    matched_only: bool,
    collection_group: str,
):
    projections = []
    for listing in LISTING_TYPES.values():
        query = listing.project()
        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.where(or_(*(field.ilike(term) for field in listing.search_fields)))
        projections.append(query)
    rows = union_all(*projections).subquery()
    columns = rows.c
    query = select(rows)
    for field, value in (("source", source), ("province", province), ("city", city), ("category", category)):
        if value:
            query = query.where(columns[field] == value)
    if collection_group != "all":
        query = query.where(columns.collection_group == collection_group)
    if matched_only:
        query = query.where(columns.has_keyword_match.is_(True))
    if status != "all":
        now = datetime.now(timezone.utc)
        deadline = columns.deadline_at
        query = query.where(deadline > now if status == "active" else deadline <= now)
    return query.subquery("global_listings")


def excel_safe(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


@router.get("/api/search")
def global_search(
    search: str | None = None,
    kind: str = "all",
    source: str | None = None,
    category: Literal["movable", "immovable", "rental", "minor", "clearance"] | None = None,
    province: str | None = None,
    city: str | None = None,
    status: Literal["all", "active", "archive"] = "all",
    matched_only: bool = False,
    collection_group: Literal["all", "executive_agencies", "amval_tamliki", "shared"] = "all",
    sort_by: str = Query("announcement_at"),
    sort_dir: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    advanced: AdvancedSearchFilters = Depends(),
    db: Session = Depends(get_db),
):
    if kind != "all" and kind not in LISTING_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported listing type")
    if sort_by not in SORT_COLUMNS:
        raise HTTPException(status_code=422, detail="Unsupported sort_by column")
    if collection_group != "all" and category is not None:
        try:
            resolve_collection_group(category, collection_group)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    rows = _searchable_rows(search, source, province, city, category, status, matched_only, collection_group)
    filters = advanced.conditions(rows)
    base = select(rows).where(*filters)

    # Tab counts stay meaningful when an auction-only category filter is active.
    summary_rows = rows
    summary_filters = filters
    if category is not None:
        summary_rows = _searchable_rows(search, source, province, city, None, status, matched_only, collection_group)
        summary_filters = advanced.conditions(summary_rows)
    summary_query = (
        select(summary_rows.c.record_type, func.count())
        .where(*summary_filters)
        .group_by(summary_rows.c.record_type)
    )
    counts = dict(db.execute(summary_query).all())
    summary = {config.count_key: counts.get(key, 0) for key, config in LISTING_TYPES.items()}

    if kind != "all":
        base = base.where(rows.c.record_type == kind)
    if category is not None:
        total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    else:
        total = sum(summary.values()) if kind == "all" else counts.get(kind, 0)

    column = rows.c[SORT_COLUMNS[sort_by]]
    if sort_by == "category":
        column = func.coalesce(column, rows.c.type_name)
    ordering = column.asc().nulls_last() if sort_dir == "asc" else column.desc().nulls_last()
    records = db.execute(
        base.order_by(ordering, rows.c.record_type.asc(), rows.c.record_id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).mappings().all()

    options_rows = _searchable_rows(None, None, None, None, None, "all", False, "all").c
    source_values = db.scalars(select(options_rows.source).distinct().order_by(options_rows.source)).all()
    scope = [options_rows.record_type == kind] if kind != "all" else []
    province_values = db.scalars(
        select(options_rows.province).where(*scope, options_rows.province.is_not(None))
        .distinct().order_by(options_rows.province)
    ).all()
    city_rows = db.execute(
        select(options_rows.province, options_rows.city)
        .where(*scope, options_rows.province.is_not(None), options_rows.city.is_not(None))
        .distinct().order_by(options_rows.province, options_rows.city)
    ).all()
    states = db.scalars(
        select(options_rows.state).where(*scope, options_rows.state.is_not(None))
        .distinct().order_by(options_rows.state)
    ).all()
    types = db.scalars(
        select(options_rows.type_name).where(*scope, options_rows.type_name.is_not(None))
        .distinct().order_by(options_rows.type_name)
    ).all()

    items = []
    for row in records:
        item = dict(row)
        item["id"] = item["record_id"]
        item["row_key"] = f'{item["record_type"]}:{item["record_id"]}'
        item["record_type_label"] = LISTING_TYPES[item["record_type"]].label
        item["collection_group_label"] = {
            "executive_agencies": "دستگاه‌های اجرایی",
            "amval_tamliki": "سازمان جمع‌آوری و فروش اموال تملیکی",
            "shared": "حراج مشترک ستاد",
        }.get(item.get("collection_group"), "—")
        if item.get("collection_group") == "amval_tamliki":
            item["source_label"] = (
                "سامانه حراج اموال تملیکی"
                if item["source"] == "setad_clearance_5315"
                else "سامانه مزایده اموال تملیکی"
            )
        else:
            item["source_label"] = SOURCE_LABELS.get(item["source"], item["source"])
        item["category_label"] = AUCTION_CATEGORIES.get(item["category"]) or item["type_name"] or "—"
        items.append(item)

    archive_counts = dict(db.execute(
        select(options_rows.record_type, func.count()).group_by(options_rows.record_type)
    ).all())
    archive_summary = {
        config.count_key: archive_counts.get(key, 0)
        for key, config in LISTING_TYPES.items()
    }

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": (total + page_size - 1) // page_size,
        "summary": {"all": sum(summary.values()), **summary},
        "archive_summary": {"all": sum(archive_summary.values()), **archive_summary},
        "filter_options": {
            "sources": [
                {"value": value, "label": SOURCE_LABELS.get(value, value)}
                for value in source_values
            ],
            "provinces": list(province_values),
            "cities": [{"province": province, "city": city} for province, city in city_rows],
            "states": list(states),
            "types": list(types),
            "categories": [
                {"value": key, "label": value}
                for key, value in AUCTION_CATEGORIES.items()
            ],
            "collection_groups": [
                {"value": "executive_agencies", "label": "دستگاه‌های اجرایی"},
                {"value": "amval_tamliki", "label": "سازمان جمع‌آوری و فروش اموال تملیکی"},
                {"value": "shared", "label": "حراج مشترک ستاد"},
            ],
        },
    }


@router.get("/api/search/export.xlsx")
def export_global_search(
    search: str | None = None,
    kind: str = "all",
    source: str | None = None,
    category: Literal["movable", "immovable", "rental", "minor", "clearance"] | None = None,
    province: str | None = None,
    city: str | None = None,
    status: Literal["all", "active", "archive"] = "all",
    matched_only: bool = False,
    collection_group: Literal["all", "executive_agencies", "amval_tamliki", "shared"] = "all",
    sort_by: str = Query("announcement_at"),
    sort_dir: Literal["asc", "desc"] = "desc",
    advanced: AdvancedSearchFilters = Depends(),
    progress: ExportProgress | None = Depends(track_excel_export),
    db: Session = Depends(get_db),
):
    if kind != "all" and kind not in LISTING_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported listing type")
    if sort_by not in SORT_COLUMNS:
        raise HTTPException(status_code=422, detail="Unsupported sort_by column")
    if collection_group != "all" and category is not None:
        try:
            resolve_collection_group(category, collection_group)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    rows = _searchable_rows(
        search, source, province, city, category, status, matched_only, collection_group,
    )
    query = select(rows).where(*advanced.conditions(rows))
    if kind != "all":
        query = query.where(rows.c.record_type == kind)

    column = rows.c[SORT_COLUMNS[sort_by]]
    if sort_by == "category":
        column = func.coalesce(column, rows.c.type_name)
    ordering = column.asc().nulls_last() if sort_dir == "asc" else column.desc().nulls_last()
    query = query.order_by(ordering, rows.c.record_type.asc(), rows.c.record_id.asc())

    group_labels = {
        "executive_agencies": "دستگاه‌های اجرایی",
        "amval_tamliki": "سازمان جمع‌آوری و فروش اموال تملیکی",
        "shared": "حراج مشترک ستاد",
    }

    headers = [
        "شناسه رکورد", "نوع معامله", "مجموعه", "دسته مزایده", "منبع",
        "شماره آگهی", "عنوان", "سازمان برگزارکننده", "استان", "شهر",
        "تاریخ اعلام", "مهلت پیشنهاد", "مبلغ پایه", "واحد پول",
        "وضعیت", "مرتبط با کلیدواژه‌ها", "نوع فراخوان", "مهلت دریافت اسناد",
    ]

    def export_rows():
        for row in db.execute(query).mappings().yield_per(500):
            record_type = row["record_type"]
            source_label = SOURCE_LABELS.get(row["source"], row["source"])
            if row.get("collection_group") == "amval_tamliki" and row["source"] == "setad_clearance_5315":
                source_label = "سامانه حراج اموال تملیکی"

            announcement_at = row["announcement_at"]
            deadline_at = row["deadline_at"]
            yield [
                row["record_id"],
                LISTING_TYPES[record_type].label,
                group_labels.get(row.get("collection_group"), "—"),
                AUCTION_CATEGORIES.get(row.get("category"), "—"),
                excel_safe(source_label),
                excel_safe(row["record_number"]),
                excel_safe(row["title"]),
                excel_safe(row["organization"]),
                excel_safe(row["province"]),
                excel_safe(row["city"]),
                announcement_at.isoformat() if announcement_at else "",
                deadline_at.isoformat() if deadline_at else "",
                row["base_total_price"],
                row["money_unit"] or "",
                excel_safe(row["state"]),
                "بله" if row["has_keyword_match"] else "خیر",
                excel_safe(row["type_name"]),
                row["documents_deadline_at"].isoformat() if row["documents_deadline_at"] else "",
            ]

    return excel_download(
        db, query, progress, "setadscope_global.xlsx",
        "تمام معاملات", "SetadScopeGlobal", headers, export_rows,
        widths=[18, 15, 34, 18, 36, 24, 54, 38, 20, 20, 25, 25, 24, 16, 20, 20, 26, 25],
        numeric_columns=(13,),
    )
