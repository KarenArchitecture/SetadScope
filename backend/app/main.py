from __future__ import annotations
import json
import os
import subprocess
import sys
import threading
from collections import deque
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
from app.services.tender_ingestion import RAW_DIR as TENDER_RAW_DIR, import_tender_pages
from app.tender_jobs import latest_tender_run_files
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
PROGRESS_PREFIX = "PROGRESS_JSON:"
COLLECTION_KINDS = ("auctions", "tenders")
collection_lock = threading.Lock()


def initial_collection_state(kind: str) -> dict:
    return {
        "kind": kind,
        "status": "idle",
        "phase": "idle",
        "message": "هنوز جمع‌آوری جدیدی اجرا نشده است.",
        "started_at": None,
        "finished_at": None,
        "current_page": 0,
        "total_pages": COLLECTION_END_PAGE if kind == "auctions" else None,
        "pages_completed": 0,
        "records_fetched": 0,
        "records_total": None,
        "records_stored": 0,
        "records_skipped": 0,
        "progress_percent": 0,
        "totals": None,
        "error": None,
        "output": None,
    }


collection_states = {kind: initial_collection_state(kind) for kind in COLLECTION_KINDS}


def update_collection_state(collection_kind: str, **values) -> dict:
    with collection_lock:
        collection_states[collection_kind].update(values)
        return dict(collection_states[collection_kind])


def run_collection_job(kind: str) -> None:
    started_at = datetime.now(timezone.utc).isoformat()
    initial = initial_collection_state(kind)
    initial.update(
        {
            "status": "collecting",
            "phase": "collecting",
            "message": (
                "در حال دریافت صفحات مزایده‌ها..."
                if kind == "auctions"
                else "در حال اتصال به سامانه مناقصه‌ها و شناسایی تعداد صفحات..."
            ),
            "started_at": started_at,
        }
    )
    update_collection_state(kind, **initial)

    output_lines: deque[str] = deque(maxlen=100)
    try:
        project_root = Path(__file__).resolve().parents[2]
        env = os.environ.copy()
        python_paths = [
            str(project_root / "backend"),
            str(project_root / "src"),
            env.get("PYTHONPATH", ""),
        ]
        env["PYTHONPATH"] = os.pathsep.join(value for value in python_paths if value)

        if kind == "auctions":
            module = "setad_scope.collectors.fetch_main_estate"
            collector_args = [
                "--start-page",
                str(COLLECTION_START_PAGE),
                "--end-page",
                str(COLLECTION_END_PAGE),
                "--delay",
                "1",
            ]
        else:
            module = "setad_scope.collectors.fetch_tenders"
            collector_args = ["--start-page", "1", "--rows", "30", "--delay", "0.5"]

        process = subprocess.Popen(
            [sys.executable, "-u", "-m", module, *collector_args],
            cwd=project_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        if process.stdout is not None:
            for raw_line in process.stdout:
                line = raw_line.rstrip()
                if not line:
                    continue
                output_lines.append(line)
                if line.startswith(PROGRESS_PREFIX):
                    try:
                        progress = json.loads(line[len(PROGRESS_PREFIX):])
                    except json.JSONDecodeError:
                        continue
                    update_collection_state(
                        kind,
                        status="collecting",
                        phase=progress.get("phase", "collecting"),
                        message=progress.get("message", "در حال دریافت اطلاعات..."),
                        current_page=progress.get("current_page", 0),
                        total_pages=progress.get("total_pages"),
                        pages_completed=progress.get("pages_completed", 0),
                        records_fetched=progress.get("records_fetched", 0),
                        records_total=progress.get("records_total"),
                        progress_percent=min(int(progress.get("progress_percent", 0)), 85),
                    )

        return_code = process.wait()
        output = "\n".join(output_lines)[-5000:]
        if return_code != 0:
            raise RuntimeError(output or f"{kind} collector exited with code {return_code}")

        update_collection_state(
            kind,
            status="importing",
            phase="importing",
            message="دریافت صفحات تمام شد؛ در حال پردازش و ذخیره در PostgreSQL...",
            progress_percent=85,
            output=output,
        )

        if kind == "auctions":
            files = latest_run_files(RAW_DIR)
        else:
            files = latest_tender_run_files(TENDER_RAW_DIR)

        if not files:
            raise RuntimeError("Collector completed but no raw response page files were found.")

        def report_import_progress(progress: dict) -> None:
            completed = int(progress.get("pages_completed", 0))
            total = max(int(progress.get("total_pages", 0)), 1)
            percent = 85 + int(15 * completed / total)
            update_collection_state(
                kind,
                status="importing",
                phase="importing",
                message=f"ذخیره صفحه {completed} از {total} در PostgreSQL...",
                current_page=completed,
                total_pages=total,
                pages_completed=completed,
                records_fetched=int(progress.get("fetched", 0)),
                records_stored=int(progress.get("stored", 0)),
                records_skipped=int(
                    progress.get("skipped_missing_id", 0)
                    + progress.get("skipped_invalid_record", 0)
                    + progress.get("skipped_expired", 0)
                ),
                progress_percent=min(percent, 99),
            )

        with SessionLocal() as session:
            if kind == "auctions":
                totals = import_pages(session, files, progress_callback=report_import_progress)
            else:
                totals = import_tender_pages(session, files, progress_callback=report_import_progress)

        records_fetched = int(totals.get("fetched", 0))
        records_stored = int(totals.get("stored", 0))
        records_skipped = max(records_fetched - records_stored, 0)
        update_collection_state(
            kind,
            status="completed",
            phase="completed",
            message="جمع‌آوری و ذخیره‌سازی با موفقیت انجام شد.",
            progress_percent=100,
            records_fetched=records_fetched,
            records_stored=records_stored,
            records_skipped=records_skipped,
            totals=totals,
            finished_at=datetime.now(timezone.utc).isoformat(),
            output=output,
        )
    except Exception as exc:
        update_collection_state(
            kind,
            status="failed",
            phase="failed",
            message="اجرای جمع‌آوری با خطا مواجه شد.",
            error=str(exc)[-3000:],
            finished_at=datetime.now(timezone.utc).isoformat(),
            output="\n".join(output_lines)[-5000:],
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


@app.get("/api/collection/{kind}/status")
def get_collection_status(kind: Literal["auctions", "tenders"]):
    with collection_lock:
        return dict(collection_states[kind])


@app.post("/api/collection/{kind}/run", status_code=202)
def start_collection(
    kind: Literal["auctions", "tenders"],
    background_tasks: BackgroundTasks,
):
    with collection_lock:
        state = collection_states[kind]
        if state["status"] in {"collecting", "importing"}:
            raise HTTPException(
                status_code=409,
                detail=f"A {kind} collection job is already running.",
            )
        collection_states[kind] = initial_collection_state(kind)
        collection_states[kind].update(
            {
                "status": "collecting",
                "phase": "collecting",
                "message": "در حال آماده‌سازی جمع‌آوری اطلاعات...",
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        response_state = dict(collection_states[kind])

    background_tasks.add_task(run_collection_job, kind)
    return response_state


# Backward-compatible aliases: the old untyped endpoints continue to target auctions.
@app.get("/api/collection/status")
def get_auction_collection_status():
    return get_collection_status("auctions")


@app.post("/api/collection/run", status_code=202)
def start_auction_collection(background_tasks: BackgroundTasks):
    return start_collection("auctions", background_tasks)


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
