from __future__ import annotations
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Auction
from app.db.session import SessionLocal, get_db
from app.jobs import latest_run_files
from app.services.ingestion import RAW_DIR, import_pages
from app.tender_api import router as tenders_router

app = FastAPI(title="SetadScope API", version="0.5.0")
app.include_router(tenders_router)

ORDER_FIELDS = {
    "source_party_id": Auction.source_party_id,
    "auction_no": Auction.auction_no,
    "auction_reference_no": Auction.auction_reference_no,
    "title": Auction.title,
    "description": Auction.description,
    "matched_keywords": cast(Auction.matched_keywords, String),
    "state": Auction.state,
    "organization": Auction.organization,
    "province": Auction.province,
    "city": Auction.city,
    "base_total_price": Auction.base_total_price,
    "trust_amount": Auction.trust_amount,
    "money_unit": Auction.money_unit,
    "proposal_start": Auction.proposal_start,
    "proposal_deadline": Auction.proposal_deadline,
    "document_deadline": Auction.document_deadline,
    "total_volume_m3": Auction.total_volume_m3,
    "first_seen_at": Auction.first_seen_at,
    "updated_at": Auction.updated_at,
}

COLLECTION_START_PAGE = 1
COLLECTION_END_PAGE = 37
collection_lock = threading.Lock()
collection_state = {
    "status": "idle",
    "message": "هنوز جمع‌آوری جدیدی اجرا نشده است.",
    "started_at": None,
    "finished_at": None,
    "totals": None,
    "error": None,
    "output": None,
}


def update_collection_state(**values) -> None:
    with collection_lock:
        collection_state.update(values)


def run_collection_job() -> None:
    started_at = datetime.now(timezone.utc).isoformat()
    update_collection_state(
        status="collecting",
        message=f"در حال دریافت صفحات {COLLECTION_START_PAGE} تا {COLLECTION_END_PAGE} از ستاد...",
        started_at=started_at,
        finished_at=None,
        totals=None,
        error=None,
        output=None,
    )
    try:
        project_root = Path(__file__).resolve().parents[2]
        env = os.environ.copy()
        python_paths = [
            str(project_root / "backend"),
            str(project_root / "src"),
            env.get("PYTHONPATH", ""),
        ]
        env["PYTHONPATH"] = os.pathsep.join(value for value in python_paths if value)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "setad_scope.collectors.fetch_main_estate",
                "--start-page",
                str(COLLECTION_START_PAGE),
                "--end-page",
                str(COLLECTION_END_PAGE),
            ],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )
        output = (result.stdout or "")[-5000:]
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "Collector failed.")[-3000:]
            raise RuntimeError(detail)

        update_collection_state(
            status="importing",
            message="دریافت صفحات تمام شد؛ در حال فیلتر کلیدواژه‌ها و ذخیره در PostgreSQL...",
            output=output,
        )
        files = latest_run_files(RAW_DIR)
        if not files:
            raise RuntimeError("Collector completed but no raw page files were found.")

        with SessionLocal() as session:
            totals = import_pages(session, files)

        update_collection_state(
            status="completed",
            message="جمع‌آوری و ذخیره‌سازی با موفقیت انجام شد.",
            totals=totals,
            finished_at=datetime.now(timezone.utc).isoformat(),
            output=output,
        )
    except Exception as exc:
        update_collection_state(
            status="failed",
            message="اجرای جمع‌آوری با خطا مواجه شد.",
            error=str(exc)[-3000:],
            finished_at=datetime.now(timezone.utc).isoformat(),
        )


def excel_safe(value):
    """Prevent untrusted Setad strings being interpreted as spreadsheet formulas."""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def auction_to_dict(a: Auction) -> dict:
    return {
        "id": a.id,
        "source_party_id": a.source_party_id,
        "auction_id": a.auction_id,
        "auction_no": a.auction_no,
        "auction_reference_no": a.auction_reference_no,
        "title": a.title,
        "description": a.description,
        "organization": a.organization,
        "province": a.province,
        "city": a.city,
        "state": a.state,
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
        query = query.where(
            or_(
                Auction.title.ilike(term),
                Auction.description.ilike(term),
                Auction.organization.ilike(term),
                Auction.city.ilike(term),
            )
        )
    return query


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(select(1)).scalar_one()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ok", "database": "ok"}


@app.get("/api/collection/status")
def get_collection_status():
    with collection_lock:
        return dict(collection_state)


@app.post("/api/collection/run", status_code=202)
def start_collection(background_tasks: BackgroundTasks):
    with collection_lock:
        if collection_state["status"] in {"collecting", "importing"}:
            raise HTTPException(
                status_code=409,
                detail="A collection job is already running.",
            )
        collection_state.update(
            {
                "status": "collecting",
                "message": "در حال آماده‌سازی جمع‌آوری اطلاعات...",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": None,
                "totals": None,
                "error": None,
                "output": None,
            }
        )
    background_tasks.add_task(run_collection_job)
    return get_collection_status()


@app.get("/api/auctions")
def get_auctions(
    search: str | None = None,
    status: Literal["active", "archive", "all"] = "all",
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
    rows = db.scalars(
        query.order_by(ordering, Auction.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [auction_to_dict(a) for a in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": (total + page_size - 1) // page_size,
    }


@app.get("/api/auctions/export.xlsx")
def export_auctions(
    status: Literal["active", "archive", "all"] = "all",
    search: str | None = None,
    db: Session = Depends(get_db),
):
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("SetadScope")
    sheet.append(
        [
            "شناسه",
            "عنوان",
            "شرح کلی",
            "کلمات منطبق",
            "سازمان",
            "استان",
            "شهر",
            "شروع پیشنهاد",
            "مهلت پیشنهاد",
            "مهلت دریافت اسناد",
            "مبلغ پایه (واحد تأییدنشده)",
            "حجم کل (مترمکعب)",
            "شماره آگهی",
            "لینک منبع",
        ]
    )
    query = filtered_query(status, search).order_by(Auction.proposal_deadline, Auction.id)
    for a in db.scalars(query).yield_per(500):
        sheet.append(
            [
                a.source_party_id,
                a.title,
                a.description,
                ", ".join(a.matched_keywords or []),
                excel_safe(a.organization),
                excel_safe(a.province),
                excel_safe(a.city),
                str(a.proposal_start or ""),
                str(a.proposal_deadline or ""),
                str(a.document_deadline or ""),
                float(a.base_total_price) if a.base_total_price is not None else None,
                float(a.total_volume_m3) if a.total_volume_m3 is not None else None,
                excel_safe(a.auction_no),
                excel_safe(a.source_url),
            ]
        )
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
