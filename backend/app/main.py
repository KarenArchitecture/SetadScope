from __future__ import annotations
import logging
import json
import os
import subprocess
import sys
import threading
from collections import deque
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.raw_cleanup import prune_previous_runs
from app.db.models import Auction, AppSetting, IngestionRun
from app.services.date_normalization import persian_timestamp
from app.db.session import SessionLocal, get_db
from app.jobs import latest_run_files
from app.services.ingestion import RAW_DIR, import_pages
from app.services.auction_ingestion import (
    AUCTION_CATEGORIES,
    AUCTION_CATEGORIES_BY_GROUP,
    COLLECTION_GROUPS,
    import_auction_pages,
    resolve_collection_group,
)
from app.auction_category_jobs import latest_category_files, partial_category_files
from app.excel_api import ExportProgress, excel_download, router as excel_router, track_excel_export
from app.services.keyword_settings import SETTING_KEY, configured_keywords, validate_keywords
from app.services.listing_filters import announced_today, date_range
from app.services.tender_ingestion import RAW_DIR as TENDER_RAW_DIR, import_tender_pages
from app.tender_jobs import latest_tender_run_files
from app.tender_api import router as tenders_router
from app.search_api import router as global_search_router

app = FastAPI(title="SetadScope API", version="0.5.0")
app.include_router(global_search_router)
app.include_router(tenders_router)
app.include_router(excel_router)

ORDER_FIELDS = {
    "source_party_id": Auction.source_party_id,
    "collection_group": Auction.collection_group,
    "category": Auction.category,
    "item_title": Auction.item_title,
    "item_reference_no": Auction.item_reference_no,
    "asset_type": Auction.asset_type,
    "price_type": Auction.price_type,
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
    "announcement_at": func.coalesce(Auction.site_show_start_at, Auction.publish_start_at),
    "proposal_start": Auction.proposal_start,
    "proposal_deadline": Auction.proposal_deadline,
    "document_deadline": Auction.document_deadline,
    "winner_announce_at": Auction.winner_announce_at,
    "opening_at": Auction.opening_at,
    "source_created_at": Auction.source_created_at,
    "total_volume_m3": Auction.total_volume_m3,
    "first_seen_at": Auction.first_seen_at,
    "updated_at": Auction.updated_at,
}

AuctionCategory = Literal["movable", "immovable", "rental", "minor", "clearance"]

PROGRESS_PREFIX = "PROGRESS_JSON:"
collection_lock = threading.Lock()

COLLECTION_GROUP_LABELS = {
    "executive_agencies": "دستگاه‌های اجرایی",
    "amval_tamliki": "سازمان اموال تملیکی",
    "shared": "تابلوی مشترک ستاد",
}
AUCTION_CATEGORY_LABELS = {
    "movable": "منقول",
    "immovable": "غیرمنقول",
    "rental": "اجاره",
    "minor": "جزئی",
    "clearance": "حراج مشترک",
}
GLOBAL_COLLECTION_SOURCES = tuple(
    {
        "kind": "auctions",
        "collection_group": group,
        "category": category,
        "label": (
            "حراج مشترک ستاد"
            if group == "shared"
            else f"{AUCTION_CATEGORY_LABELS.get(category, category)} — "
                 f"{COLLECTION_GROUP_LABELS.get(group, group)}"
        ),
    }
    for group, categories in AUCTION_CATEGORIES_BY_GROUP.items()
    for category in categories
) + (
    {
        "kind": "tenders",
        "collection_group": None,
        "category": None,
        "label": "مناقصه‌ها",
    },
)


AuctionBatchGroup = Literal["all", "executive_agencies", "amval_tamliki"]


def auction_batch_key(
    group: AuctionBatchGroup, categories: list[AuctionCategory] | None = None,
) -> str:
    selected = tuple(category for category in AUCTION_CATEGORY_LABELS if category in (categories or ()))
    suffix = ",".join(selected) if 0 < len(selected) < len(AUCTION_CATEGORY_LABELS) else "all"
    return f"auction-batch:{group}:{suffix}"


def auction_batch_sources(
    group: AuctionBatchGroup, categories: list[AuctionCategory] | None = None,
) -> tuple[dict, ...]:
    # Preserve category order, including when both owning collections are selected.
    return tuple(
        source
        for category in AUCTION_CATEGORY_LABELS
        if not categories or category in categories
        for source in GLOBAL_COLLECTION_SOURCES
        if source["category"] == category
        and (group == "all" or source["collection_group"] in (group, "shared"))
    )


def collection_state_key(collection_group: str, category: str) -> str:
    return f"auctions:{collection_group}:{category}"


def initial_collection_state(
    kind: str,
    collection_group: str | None = None,
    category: str | None = None,
) -> dict:
    return {
        "kind": kind,
        "collection_group": collection_group,
        "category": category,
        "status": "idle",
        "phase": "idle",
        "message": "هنوز جمع‌آوری جدیدی اجرا نشده است.",
        "started_at": None,
        "finished_at": None,
        "last_updated_at": None,
        "current_page": 0,
        "total_pages": None,
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


def initial_global_collection_state(
    *, kind: str = "global", total_sources: int = len(GLOBAL_COLLECTION_SOURCES),
) -> dict:
    return {
        "kind": kind,
        "status": "idle",
        "phase": "idle",
        "message": "هنوز جمع‌آوری جدیدی اجرا نشده است.",
        "started_at": None,
        "finished_at": None,
        "current_source_index": 0,
        "total_sources": total_sources,
        "completed_sources": 0,
        "successful_sources": 0,
        "failed_sources": [],
        "current_source_key": None,
        "current_source_label": None,
        "current_source_status": "idle",
        "current_progress_percent": 0,
        "progress_percent": 0,
        "overall_progress_percent": 0,
        "current_phase": "idle",
        "current_message": "",
        "current_pages_completed": 0,
        "current_total_pages": None,
        "current_records_fetched": 0,
        "error": None,
    }


def global_source_state_key(source: dict) -> str:
    if source["kind"] == "tenders":
        return "tenders"
    return collection_state_key(source["collection_group"], source["category"])


collection_states = {
    "tenders": initial_collection_state("tenders"),
    "global": initial_global_collection_state(),
}
for _group, _categories in AUCTION_CATEGORIES_BY_GROUP.items():
    for _category in _categories:
        _key = collection_state_key(_group, _category)
        collection_states[_key] = initial_collection_state("auctions", _group, _category)


def initial_auction_batch_state(group: AuctionBatchGroup, total_sources: int) -> dict:
    return {
        **initial_global_collection_state(kind="auction_batch", total_sources=total_sources),
        "collection_group": group,
    }


def active_batch_key() -> str | None:
    # Call under collection_lock when reading or reserving a batch.
    return next((key for key, state in collection_states.items() if state["status"] == "running"), None)


def update_collection_state(state_key: str, **values) -> dict:
    with collection_lock:
        collection_state = collection_states[state_key]
        collection_state.update(values)

        batch_key = active_batch_key()
        batch_state = collection_states[batch_key] if batch_key else None
        if (
            batch_state is not None
            and batch_state["current_source_key"] == state_key
        ):
            percent = max(0, min(100, int(collection_state.get("progress_percent", 0) or 0)))
            total_sources = max(int(batch_state.get("total_sources", 1)), 1)
            completed_sources = int(batch_state.get("completed_sources", 0))
            batch_state.update({
                "current_source_status": collection_state.get("status", "collecting"),
                "current_progress_percent": percent,
                "progress_percent": percent,
                "overall_progress_percent": round(
                    (completed_sources + percent / 100) / total_sources * 100
                ),
                "current_phase": collection_state.get("phase", "collecting"),
                "current_message": collection_state.get("message", "در حال دریافت اطلاعات..."),
                "current_pages_completed": collection_state.get("pages_completed", 0),
                "current_total_pages": collection_state.get("total_pages"),
                "current_records_fetched": collection_state.get("records_fetched", 0),
            })
        return dict(collection_state)


quick_processes = {}


def check_stop(state_key):
    with collection_lock:
        batch = collection_states.get(active_batch_key(), {})
        if batch.get("stop_requested") and batch.get("current_source_key") == state_key:
            raise RuntimeError("جمع‌آوری به درخواست کاربر متوقف شد.")


def run_collection_job(
    kind: str,
    collection_group: str | None = None,
    category: str | None = None,
) -> None:
    if kind == "tenders":
        state_key = "tenders"
        group = None
        category = None
    else:
        category = category or "movable"
        group = resolve_collection_group(category, collection_group)
        state_key = collection_state_key(group, category)

    started_at = datetime.now(timezone.utc).isoformat()
    initial = initial_collection_state(kind, group, category)
    initial.update({
        "status": "collecting",
        "phase": "collecting",
        "message": (
            "در حال دریافت صفحات مزایده‌ها..."
            if kind != "tenders"
            else "در حال اتصال به سامانه مناقصه‌ها و شناسایی تعداد صفحات..."
        ),
        "started_at": started_at,
    })
    update_collection_state(state_key, **initial)

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

        if kind == "tenders":
            module = "setad_scope.collectors.fetch_tenders"
            collector_args = ["--start-page", "1", "--rows", "30", "--delay", "0.7"]
        else:
            module = "setad_scope.collectors.fetch_auction_categories"
            collector_args = [
                "--group", group, "--category", category,
                "--start-page", "0", "--delay", "0.7",
            ]

        process = subprocess.Popen(
            [sys.executable, "-u", "-m", module, *collector_args],
            cwd=project_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        partial_manifest = None
        failure_message = None
        with collection_lock:
            quick_processes[state_key] = process
            batch = collection_states.get(active_batch_key(), {})
            if batch.get("stop_requested") and batch.get("current_source_key") == state_key:
                process.terminate()
        if process.stdout is not None:
            for raw_line in process.stdout:
                line = raw_line.rstrip()
                if not line:
                    continue
                output_lines.append(line)
                if line.startswith("PARTIAL_MANIFEST:"):
                    partial_manifest = line.removeprefix("PARTIAL_MANIFEST:")
                elif line.startswith("FETCH FAILED:"):
                    failure_message = line.removeprefix("FETCH FAILED:").strip()
                elif line.startswith(PROGRESS_PREFIX):
                    try:
                        progress = json.loads(line[len(PROGRESS_PREFIX):])
                    except json.JSONDecodeError:
                        continue
                    update_collection_state(
                        state_key,
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
        check_stop(state_key)
        output = "\n".join(output_lines)[-5000:]
        incomplete = return_code != 0
        reason = failure_message or f"{state_key} collector exited with code {return_code}"
        if incomplete and not (kind == "auctions" and group == "shared" and category == "clearance" and partial_manifest):
            raise RuntimeError(failure_message or output or reason)

        with collection_lock:
            fetch_state = dict(collection_states[state_key])
        update_collection_state(
            state_key,
            status="importing",
            phase="importing",
            message=(
                "دریافت صفحه متوقف شد. در حال ذخیره صفحات دریافت‌شده..."
                if incomplete else "دریافت صفحات تمام شد. در حال ذخیره در PostgreSQL..."
            ),
            progress_percent=85,
            output=output,
        )

        if kind == "tenders":
            files = latest_tender_run_files(TENDER_RAW_DIR)
        elif incomplete:
            files = partial_category_files(category, group, partial_manifest)
        else:
            files = latest_category_files(category, collection_group=group)
        if not files:
            raise RuntimeError("Collector completed but no raw response page files were found.")

        def report_import_progress(progress: dict) -> None:
            check_stop(state_key)
            completed = int(progress.get("pages_completed", 0))
            total = max(int(progress.get("total_pages", 0)), 1)
            percent = 85 + int(15 * completed / total)
            update_collection_state(
                state_key,
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
            if kind == "tenders":
                totals = import_tender_pages(session, files, progress_callback=report_import_progress)
            else:
                totals = import_auction_pages(
                    session, files, category,
                    progress_callback=report_import_progress,
                    collection_group=group,
                    incomplete_reason=reason if incomplete else None,
                )

        try:
            totals["raw_files_removed"] = prune_previous_runs(files, partial=incomplete)
        except OSError:
            logging.getLogger(__name__).exception("Raw cleanup failed for %s", state_key)

        records_fetched = int(totals.get("fetched", 0))
        records_stored = int(totals.get("stored", 0))
        records_skipped = max(records_fetched - records_stored, 0)
        update_collection_state(
            state_key,
            status="failed" if incomplete else "completed",
            phase="failed" if incomplete else "completed",
            message=(
                f"{records_stored} رکورد ذخیره شد. دریافت صفحات بعدی با HTTP 428 متوقف شد."
                if incomplete else "جمع‌آوری و ذخیره‌سازی با موفقیت انجام شد."
            ),
            error=f"{reason}. {records_stored} رکورد پیش از توقف ذخیره شد." if incomplete else None,
            progress_percent=fetch_state["progress_percent"] if incomplete else 100,
            **({
                key: fetch_state[key]
                for key in ("current_page", "total_pages", "pages_completed")
            } if incomplete else {}),
            records_fetched=records_fetched,
            records_stored=records_stored,
            records_skipped=records_skipped,
            totals=totals,
            finished_at=datetime.now(timezone.utc).isoformat(),
            output=output,
        )
    except Exception as exc:
        update_collection_state(
            state_key,
            status="failed",
            phase="failed",
            message="اجرای جمع‌آوری با خطا مواجه شد.",
            error=str(exc)[-3000:],
            finished_at=datetime.now(timezone.utc).isoformat(),
            output="\n".join(output_lines)[-5000:],
        )

    finally:
        with collection_lock:
            if quick_processes.get(state_key) is locals().get("process"):
                quick_processes.pop(state_key, None)

def run_global_collection_job() -> None:
    run_collection_batch("global", GLOBAL_COLLECTION_SOURCES)


def run_collection_batch(batch_key: str, sources: tuple[dict, ...]) -> None:
    """Run the reserved batch sequentially, recording failed sources and continuing."""
    total_sources = len(sources)
    for index, source in enumerate(sources, start=1):
        state_key = global_source_state_key(source)
        label = source["label"]
        with collection_lock:
            batch_state = collection_states[batch_key]
            if batch_state.get("stop_requested"):
                break
            batch_state.update({
                "phase": "collecting",
                "current_source_index": index,
                "total_sources": total_sources,
                "current_source_key": state_key,
                "current_source_label": label,
                "current_source_status": "collecting",
                "current_progress_percent": 0,
                "progress_percent": 0,
                "overall_progress_percent": round(
                    batch_state["completed_sources"] / max(total_sources, 1) * 100
                ),
                "current_phase": "starting",
                "current_message": f"در حال شروع منبع {index} از {total_sources}: {label}",
                "current_pages_completed": 0,
                "current_total_pages": None,
                "current_records_fetched": 0,
                "message": f"منبع {index} از {total_sources}: {label}",
            })

        try:
            if source["kind"] == "tenders":
                run_collection_job("tenders")
            else:
                run_collection_job(
                    "auctions",
                    source["collection_group"],
                    source["category"],
                )
        except Exception as exc:
            update_collection_state(
                state_key,
                status="failed",
                phase="failed",
                message="اجرای این منبع با خطا مواجه شد.",
                error=str(exc)[-3000:],
                finished_at=datetime.now(timezone.utc).isoformat(),
            )

        with collection_lock:
            batch_state = collection_states[batch_key]
            source_state = collection_states[state_key]
            succeeded = source_state.get("status") == "completed"
            completed_sources = index
            successful_sources = int(batch_state.get("successful_sources", 0))
            failed_sources = list(batch_state.get("failed_sources", []))

            if succeeded:
                successful_sources += 1
                current_message = f"{label} با موفقیت بروزرسانی شد."
            else:
                failed_sources.append({
                    "key": state_key,
                    "label": label,
                    "error": (
                        source_state.get("error")
                        or source_state.get("message")
                        or "اجرای منبع ناموفق بود."
                    ),
                })
                current_message = (
                    f"{label} ناموفق بود؛ اجرای منابع بعدی ادامه پیدا می‌کند."
                )

            current_percent = (
                100
                if succeeded
                else max(0, min(100, int(source_state.get("progress_percent", 0) or 0)))
            )
            batch_state.update({
                "completed_sources": completed_sources,
                "successful_sources": successful_sources,
                "failed_sources": failed_sources,
                "current_source_status": source_state.get("status", "failed"),
                "current_progress_percent": current_percent,
                "progress_percent": current_percent,
                "overall_progress_percent": round(completed_sources / max(total_sources, 1) * 100),
                "current_phase": source_state.get("phase", "failed" if not succeeded else "completed"),
                "current_message": current_message,
                "current_pages_completed": source_state.get("pages_completed", 0),
                "current_total_pages": source_state.get("total_pages"),
                "current_records_fetched": source_state.get("records_fetched", 0),
                "message": (
                    f"منبع {index} از {total_sources} تمام شد؛ "
                    f"{successful_sources} منبع با موفقیت بروزرسانی شده‌اند."
                ),
            })

    with collection_lock:
        batch_state = collection_states[batch_key]
        if batch_state.get("stop_requested"):
            batch_state.update(status="cancelled", phase="cancelled", message="عملیات متوقف شد.",
                               current_source_key=None, finished_at=datetime.now(timezone.utc).isoformat())
            return
        failed_count = len(batch_state["failed_sources"])
        successful_count = int(batch_state["successful_sources"])
        final_status = "completed_with_errors" if failed_count else "completed"
        final_message = (
            f"جمع‌آوری پایان یافت. {successful_count} از {total_sources} منبع به‌روزرسانی شد."
            if failed_count
            else f"تمام {total_sources} منبع با موفقیت به‌روزرسانی شد."
        )
        batch_state.update({
            "status": final_status,
            "phase": "completed",
            "current_source_index": total_sources,
            "current_source_key": None,
            "current_source_label": "تمام منابع",
            "current_source_status": final_status,
            "current_progress_percent": 100,
            "progress_percent": 100,
            "overall_progress_percent": 100,
            "current_phase": "completed",
            "current_message": final_message,
            "message": final_message,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        })


def excel_safe(value):
    """Prevent untrusted Setad strings being interpreted as spreadsheet formulas."""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def auction_to_dict(a: Auction) -> dict:
    return {
        "id": a.id,
        "source_party_id": a.source_party_id,
        "collection_group": a.collection_group,
        "category": a.category,
        "has_keyword_match": a.has_keyword_match,
        "item_title": a.item_title,
        "item_reference_no": a.item_reference_no,
        "asset_type": a.asset_type,
        "price_type": a.price_type,
        "rent_duration_months": a.rent_duration_months,
        "rent_duration_days": a.rent_duration_days,
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
        "announcement_at": a.site_show_start_at or a.publish_start_at,
        "site_show_start_at": a.site_show_start_at,
        "site_show_end_at": a.site_show_end_at,
        "publish_start_at": a.publish_start_at,
        "publish_finish_at": a.publish_finish_at,
        "winner_announce_at": a.winner_announce_at,
        "opened_at": a.opened_at,
        "opening_at": a.opening_at,
        "last_modify_at": a.last_modify_at,
        "source_created_at": a.source_created_at,
        "trust_opened_at": a.trust_opened_at,
        "base_total_price": a.base_total_price,
        "trust_amount": a.trust_amount,
        "total_volume_m3": a.total_volume_m3,
        "money_unit": a.money_unit,
        "matched_keywords": a.matched_keywords,
        "source_url": a.source_url,
        "first_seen_at": a.first_seen_at,
        "updated_at": a.updated_at,
    }


def filtered_query(
    status: str,
    search: str | None,
    province: str | None = None,
    city: str | None = None,
    state: str | None = None,
    announcement_from: str | None = None,
    announcement_to: str | None = None,
    deadline_from: str | None = None,
    deadline_to: str | None = None,
    price_min: Decimal | None = None,
    price_max: Decimal | None = None,
    category: str = "movable",
    matched_only: bool = True,
    collection_group: str = "all",
    categories: list[AuctionCategory] | None = None,
    today_only: bool = False,
):
    query = select(Auction).where(*_auction_group_scope(category, collection_group, categories))
    if matched_only:
        query = query.where(Auction.has_keyword_match.is_(True))
    now = datetime.now(timezone.utc)
    announcement_date = func.coalesce(Auction.site_show_start_at, Auction.publish_start_at)

    if status == "active":
        query = query.where(Auction.proposal_deadline > now)
    elif status == "archive":
        query = query.where(Auction.proposal_deadline <= now)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Auction.title.ilike(term),
                Auction.description.ilike(term),
                Auction.organization.ilike(term),
                Auction.city.ilike(term),
                Auction.province.ilike(term),
                Auction.auction_no.ilike(term),
                Auction.item_title.ilike(term),
                Auction.item_reference_no.ilike(term),
                Auction.asset_type.ilike(term),
            )
        )
    if province:
        query = query.where(Auction.province == province)
    if city:
        query = query.where(Auction.city == city)
    if state:
        query = query.where(Auction.state == state)

    query = query.where(
        *date_range(announcement_date, "announcement", announcement_from, announcement_to),
        *date_range(Auction.proposal_deadline, "deadline", deadline_from, deadline_to),
    )
    if today_only:
        query = query.where(*announced_today(announcement_date))
    if price_min is not None and price_max is not None and price_min > price_max:
        raise HTTPException(status_code=422, detail="price_min cannot exceed price_max")
    if price_min is not None:
        query = query.where(Auction.base_total_price >= price_min)
    if price_max is not None:
        query = query.where(Auction.base_total_price <= price_max)
    return query


def _auction_group_scope(
    category: str, collection_group: str, categories: list[AuctionCategory] | None = None,
):
    if category == "all" or categories:
        conditions = [Auction.category.in_(categories)] if categories else []
        if collection_group in ("executive_agencies", "amval_tamliki"):
            conditions.append(
                or_(
                    Auction.collection_group == collection_group,
                    (Auction.collection_group == "shared") & (Auction.category == "clearance"),
                )
            )
        elif collection_group != "all":
            conditions.append(Auction.collection_group == collection_group)
        return conditions

    if collection_group == "all":
        return [Auction.category == category]
    try:
        resolve_collection_group(category, collection_group)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return [Auction.category == category, Auction.collection_group == collection_group]


def auction_archive_stats(
    db: Session,
    category: str,
    collection_group: str = "all",
    categories: list[AuctionCategory] | None = None,
) -> dict[str, int]:
    scope = _auction_group_scope(category, collection_group, categories)
    total = db.scalar(select(func.count(Auction.id)).where(*scope)) or 0
    matched_total = db.scalar(
        select(func.count(Auction.id)).where(*scope, Auction.has_keyword_match.is_(True))
    ) or 0
    provinces = db.scalar(
        select(func.count(func.distinct(Auction.province))).where(*scope, Auction.province.is_not(None))
    ) or 0
    cities = db.scalar(
        select(func.count(func.distinct(Auction.city))).where(*scope, Auction.city.is_not(None))
    ) or 0
    organizations = db.scalar(
        select(func.count(func.distinct(Auction.organization))).where(*scope, Auction.organization.is_not(None))
    ) or 0
    published = db.scalar(
        select(func.count(Auction.id)).where(*scope, Auction.state == "PUBLISHED")
    ) or 0
    return {
        "total": total,
        "matched_total": matched_total,
        "province_count": provinces,
        "city_count": cities,
        "organization_count": organizations,
        "published_count": published,
    }


def auction_filter_options(
    db: Session,
    category: str,
    collection_group: str = "all",
    categories: list[AuctionCategory] | None = None,
) -> dict[str, list]:
    scope = _auction_group_scope(category, collection_group, categories)
    provinces = db.scalars(
        select(Auction.province)
        .where(*scope, Auction.province.is_not(None))
        .distinct()
        .order_by(Auction.province)
    ).all()
    city_rows = db.execute(
        select(Auction.city, Auction.province)
        .where(*scope, Auction.city.is_not(None), Auction.province.is_not(None))
        .distinct()
        .order_by(Auction.province, Auction.city)
    ).all()
    states = db.scalars(
        select(Auction.state)
        .where(*scope, Auction.state.is_not(None))
        .distinct()
        .order_by(Auction.state)
    ).all()
    return {
        "provinces": list(provinces),
        "cities": [{"city": city, "province": province} for city, province in city_rows],
        "states": list(states),
        "collection_groups": [
            {"value": "executive_agencies", "label": "دستگاه‌های اجرایی"},
            {"value": "amval_tamliki", "label": "سازمان جمع‌آوری و فروش اموال تملیکی"},
            {"value": "shared", "label": "حراج مشترک ستاد"},
        ],
    }


class KeywordSettingsPayload(BaseModel):
    keywords: list[str]


@app.get("/api/settings/keywords")
def get_keyword_settings(db: Session = Depends(get_db)):
    return {"keywords": list(configured_keywords(db))}


@app.put("/api/settings/keywords")
def put_keyword_settings(payload: KeywordSettingsPayload, db: Session = Depends(get_db)):
    try:
        words = validate_keywords(payload.keywords)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    setting = db.get(AppSetting, SETTING_KEY)
    if setting is None:
        setting = AppSetting(key=SETTING_KEY, value={"keywords": words})
        db.add(setting)
    else:
        setting.value = {"keywords": words}
    db.commit()
    return {"keywords": words}


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(select(1)).scalar_one()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ok", "database": "ok"}


def latest_successful_collection_at(
    db: Session,
    run_kind: str,
    category: str | None,
    collection_group: str | None = None,
) -> datetime | None:
    query = select(IngestionRun.finished_at).where(
        IngestionRun.kind == run_kind,
        IngestionRun.status == "success",
        IngestionRun.finished_at.is_not(None),
    )
    if category is None:
        query = query.where(IngestionRun.category.is_(None))
    else:
        query = query.where(IngestionRun.category == category)
    if collection_group is None:
        query = query.where(IngestionRun.collection_group.is_(None))
    else:
        query = query.where(IngestionRun.collection_group == collection_group)
    return db.scalar(query.order_by(IngestionRun.finished_at.desc()).limit(1))


def collection_status_response(
    state_key: str,
    run_kind: str,
    category: str | None,
    db: Session,
    collection_group: str | None = None,
) -> dict:
    with collection_lock:
        state = dict(collection_states[state_key])
    last_updated = latest_successful_collection_at(db, run_kind, category, collection_group)
    state["last_updated_at"] = last_updated.isoformat() if last_updated else None
    return state


@app.get("/api/collection/global/status")
def get_global_collection_status():
    with collection_lock:
        return dict(collection_states["global"])


@app.post("/api/collection/global/run", status_code=202)
def start_global_collection(background_tasks: BackgroundTasks):
    response = reserve_collection_batch("global", initial_global_collection_state(), include_tenders=True)
    background_tasks.add_task(run_global_collection_job)
    return response


def reserve_collection_batch(batch_key: str, initial: dict, *, include_tenders: bool = False) -> dict:
    with collection_lock:
        if active_batch_key():
            raise HTTPException(status_code=409, detail="یک جمع‌آوری گروهی در حال اجراست.")
        if any(
            state["status"] in {"collecting", "importing"}
            for key, state in collection_states.items()
            if key.startswith("auctions:") or (include_tenders and key == "tenders")
        ):
            raise HTTPException(status_code=409, detail="یکی از منابع این عملیات در حال جمع‌آوری است.")
        initial.update({
            "status": "running",
            "phase": "starting",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "message": "در حال آماده‌سازی جمع‌آوری...",
        })
        collection_states[batch_key] = initial
        return dict(initial)


QuickKind = Literal["auctions", "tenders"]


@app.post("/api/quick/{kind}/run", status_code=202)
def start_quick(kind: QuickKind, background_tasks: BackgroundTasks):
    sources = auction_batch_sources("all") if kind == "auctions" else tuple(
        source for source in GLOBAL_COLLECTION_SOURCES if source["kind"] == "tenders"
    )
    key = f"quick:{kind}"
    state = reserve_collection_batch(key, initial_global_collection_state(total_sources=len(sources)),
                                     include_tenders=kind == "tenders")
    background_tasks.add_task(run_collection_batch, key, sources)
    return state


@app.get("/api/quick/{kind}/status")
def quick_status(kind: QuickKind):
    with collection_lock:
        return dict(collection_states.get(f"quick:{kind}", {"status": "idle"}))


@app.post("/api/quick/{kind}/stop")
def stop_quick(kind: QuickKind, started_at: str):
    with collection_lock:
        batch = collection_states.get(f"quick:{kind}", {})
        if batch.get("started_at") != started_at:
            raise HTTPException(409, "این اجرا دیگر فعال نیست.")
        if batch["status"] == "running":
            batch["stop_requested"] = True
            process = quick_processes.get(batch.get("current_source_key"))
            if process and process.poll() is None:
                process.terminate()
        return dict(batch)


@app.get("/api/collection/{kind}/status")
def get_collection_status(
    kind: Literal["auctions", "tenders"],
    db: Session = Depends(get_db),
):
    if kind == "tenders":
        return collection_status_response("tenders", "tenders", None, db)
    group = "executive_agencies"
    category = "movable"
    return collection_status_response(
        collection_state_key(group, category), "auctions", category, db, group,
    )


@app.post("/api/collection/{kind}/run", status_code=202)
def start_collection(
    kind: Literal["auctions", "tenders"],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if kind == "auctions":
        return start_auction_category_collection(
            "movable", background_tasks, db, collection_group="executive_agencies",
        )

    state_key = "tenders"
    with collection_lock:
        if active_batch_key() in ("global", "quick:tenders"):
            raise HTTPException(status_code=409, detail="A global collection is already running.")
        state = collection_states[state_key]
        if state["status"] in {"collecting", "importing"}:
            raise HTTPException(status_code=409, detail="A tenders collection job is already running.")
        collection_states[state_key] = initial_collection_state("tenders")
        collection_states[state_key].update({
            "status": "collecting",
            "phase": "collecting",
            "message": "در حال آماده‌سازی جمع‌آوری اطلاعات...",
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
        response_state = dict(collection_states[state_key])
    last_updated = latest_successful_collection_at(db, "tenders", None, None)
    response_state["last_updated_at"] = last_updated.isoformat() if last_updated else None
    background_tasks.add_task(run_collection_job, "tenders")
    return response_state


@app.get("/api/collection/auctions/all/status")
def get_auction_batch_status(
    collection_group: AuctionBatchGroup = "all",
    db: Session = Depends(get_db),
    categories: Annotated[list[AuctionCategory] | None, Query()] = None,
):
    sources = auction_batch_sources(collection_group, categories)
    batch_key = auction_batch_key(collection_group, categories)
    with collection_lock:
        stored_state = collection_states.get(batch_key)
        state = dict(stored_state) if stored_state else initial_auction_batch_state(collection_group, len(sources))
    last_updated = db.scalar(
        select(func.max(IngestionRun.finished_at)).where(
            IngestionRun.kind == "auctions",
            IngestionRun.status == "success",
            or_(*(
                (IngestionRun.collection_group == source["collection_group"])
                & (IngestionRun.category == source["category"])
                for source in sources
            )),
        )
    )
    state["last_updated_at"] = last_updated.isoformat() if last_updated else None
    return state


@app.post("/api/collection/auctions/all/run", status_code=202)
def start_auction_batch(
    background_tasks: BackgroundTasks,
    collection_group: AuctionBatchGroup = "all",
    categories: Annotated[list[AuctionCategory] | None, Query()] = None,
):
    sources = auction_batch_sources(collection_group, categories)
    batch_key = auction_batch_key(collection_group, categories)
    response = reserve_collection_batch(batch_key, initial_auction_batch_state(collection_group, len(sources)))
    background_tasks.add_task(run_collection_batch, batch_key, sources)
    return response


# Existing route shapes remain available. Pass collection_group to select a
# source group; clearance defaults to the shared Central Board feed.
@app.get("/api/collection/auctions/{category}/status")
def get_auction_category_status(
    category: Literal["movable", "immovable", "rental", "minor", "clearance"],
    collection_group: Literal["executive_agencies", "amval_tamliki", "shared"] | None = None,
    db: Session = Depends(get_db),
):
    try:
        group = resolve_collection_group(category, collection_group)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    state_key = collection_state_key(group, category)
    return collection_status_response(state_key, "auctions", category, db, group)


@app.post("/api/collection/auctions/{category}/run", status_code=202)
def start_auction_category_collection(
    category: Literal["movable", "immovable", "rental", "minor", "clearance"],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    collection_group: Literal["executive_agencies", "amval_tamliki", "shared"] | None = None,
):
    try:
        group = resolve_collection_group(category, collection_group)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    state_key = collection_state_key(group, category)
    with collection_lock:
        if active_batch_key():
            raise HTTPException(status_code=409, detail="یک جمع‌آوری گروهی در حال اجراست.")
        state = collection_states[state_key]
        if state["status"] in {"collecting", "importing"}:
            raise HTTPException(
                status_code=409,
                detail=f"A {group}/{category} collection job is already running.",
            )
        collection_states[state_key] = initial_collection_state("auctions", group, category)
        collection_states[state_key].update({
            "status": "collecting",
            "phase": "collecting",
            "message": "در حال آماده‌سازی جمع‌آوری اطلاعات...",
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
        response_state = dict(collection_states[state_key])

    last_updated = latest_successful_collection_at(db, "auctions", category, group)
    response_state["last_updated_at"] = last_updated.isoformat() if last_updated else None
    background_tasks.add_task(run_collection_job, "auctions", group, category)
    return response_state


@app.get("/api/collection/auctions/history")
def get_auction_collection_history(
    collection_group: Literal["all", "executive_agencies", "amval_tamliki", "shared"] = "all",
    category: Literal["movable", "immovable", "rental", "minor", "clearance"] | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    if collection_group != "all" and category is not None:
        try:
            resolve_collection_group(category, collection_group)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    query = select(IngestionRun).where(IngestionRun.kind == "auctions")
    if collection_group != "all":
        query = query.where(IngestionRun.collection_group == collection_group)
    if category is not None:
        query = query.where(IngestionRun.category == category)
    runs = db.scalars(
        query.order_by(IngestionRun.started_at.desc(), IngestionRun.id.desc()).limit(limit)
    ).all()
    return {
        "items": [
            {
                "id": run.id,
                "collection_group": run.collection_group,
                "category": run.category,
                "status": run.status,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "fetched": run.fetched,
                "matched": run.matched,
                "stored": run.stored,
                "error": run.error,
            }
            for run in runs
        ],
        "limit": limit,
        "total": len(runs),
    }


@app.get("/api/collection/status")
def get_auction_collection_status(db: Session = Depends(get_db)):
    group = "executive_agencies"
    category = "movable"
    return collection_status_response(
        collection_state_key(group, category), "auctions", category, db, group,
    )


@app.post("/api/collection/run", status_code=202)
def start_auction_collection(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return start_auction_category_collection(
        "movable", background_tasks, db, collection_group="executive_agencies",
    )


@app.get("/api/auctions")
def get_auctions(
    search: str | None = None,
    category: AuctionCategory | Literal["all"] = "movable",
    categories: list[AuctionCategory] | None = Query(None),
    collection_group: Literal["all", "executive_agencies", "amval_tamliki", "shared"] = "all",
    matched_only: bool = True,
    today_only: bool = False,
    status: Literal["active", "archive", "all"] = "all",
    province: str | None = None,
    city: str | None = None,
    state: str | None = None,
    announcement_from: str | None = None,
    announcement_to: str | None = None,
    deadline_from: str | None = None,
    deadline_to: str | None = None,
    price_min: Decimal | None = Query(None, ge=0),
    price_max: Decimal | None = Query(None, ge=0),
    sort_by: str = Query("proposal_deadline"),
    sort_dir: Literal["asc", "desc"] = "asc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if sort_by not in ORDER_FIELDS:
        raise HTTPException(status_code=422, detail="Unsupported sort_by column")

    query = filtered_query(
        status, search, province, city, state,
        announcement_from, announcement_to, deadline_from, deadline_to,
        price_min, price_max, category, matched_only, collection_group, categories, today_only,
    )
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
        "archive_stats": auction_archive_stats(db, category, collection_group, categories),
        "filter_options": auction_filter_options(db, category, collection_group, categories),
    }


@app.get("/api/auctions/export.xlsx")
def export_auctions(
    status: Literal["active", "archive", "all"] = "all",
    search: str | None = None,
    category: AuctionCategory | Literal["all"] = "movable",
    categories: list[AuctionCategory] | None = Query(None),
    collection_group: Literal["all", "executive_agencies", "amval_tamliki", "shared"] = "all",
    matched_only: bool = True,
    today_only: bool = False,
    province: str | None = None,
    city: str | None = None,
    state: str | None = None,
    announcement_from: str | None = None,
    announcement_to: str | None = None,
    deadline_from: str | None = None,
    deadline_to: str | None = None,
    price_min: Decimal | None = Query(None, ge=0),
    price_max: Decimal | None = Query(None, ge=0),
    sort_by: str = Query("proposal_deadline"),
    sort_dir: Literal["asc", "desc"] = "asc",
    progress: ExportProgress | None = Depends(track_excel_export),
    db: Session = Depends(get_db),
):
    if sort_by not in ORDER_FIELDS:
        raise HTTPException(status_code=422, detail="Unsupported sort_by column")
    query = filtered_query(
        status, search, province, city, state,
        announcement_from, announcement_to, deadline_from, deadline_to,
        price_min, price_max, category, matched_only, collection_group, categories, today_only,
    )
    column = ORDER_FIELDS[sort_by]
    ordering = column.asc().nulls_last() if sort_dir == "asc" else column.desc().nulls_last()
    query = query.order_by(ordering, Auction.id.asc())
    headers = [
        "شناسه", "مجموعه", "دسته", "عنوان", "عنوان مورد", "نوع قیمت", "شرح کلی", "کلمات منطبق", "سازمان", "استان", "شهر",
        "تاریخ اعلام در سایت", "شروع پیشنهاد", "مهلت پیشنهاد", "مهلت دریافت اسناد",
        "مبلغ پایه (واحد تأییدنشده)", "مبلغ سپرده (واحد تأییدنشده)",
        "تاریخ اعلام برنده", "تاریخ بازگشایی", "شماره آگهی", "لینک منبع",
    ]

    def export_rows():
        for a in db.scalars(query).yield_per(500):
            yield [
                excel_safe(a.source_party_id), COLLECTION_GROUP_LABELS.get(a.collection_group, a.collection_group), AUCTION_CATEGORY_LABELS.get(a.category, a.category),
                excel_safe(a.title), excel_safe(a.item_title), excel_safe(a.price_type),
                excel_safe(a.description), excel_safe(", ".join(a.matched_keywords or [])),
                excel_safe(a.organization), excel_safe(a.province), excel_safe(a.city),
                persian_timestamp(a.site_show_start_at or a.publish_start_at),
                persian_timestamp(a.proposal_start), persian_timestamp(a.proposal_deadline),
                persian_timestamp(a.document_deadline),
                a.base_total_price, a.trust_amount,
                persian_timestamp(a.winner_announce_at), persian_timestamp(a.opening_at),
                excel_safe(a.auction_no), excel_safe(a.source_url),
            ]

    return excel_download(
        db, query, progress, "setadscope_auctions.xlsx",
        "مزایده‌ها", "SetadScopeAuctions", headers, export_rows,
        widths=[23, 22, 17, 52, 44, 22, 65, 32, 38, 20, 20, 25, 25, 25, 25, 27, 27, 25, 25, 22, 52],
        numeric_columns=(16, 17),
    )


@app.get("/api/auctions/{auction_id}")
def get_auction(auction_id: int, db: Session = Depends(get_db)):
    row = db.get(Auction, auction_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Auction listing not found")
    return {**auction_to_dict(row), "raw_payload": row.raw_payload}
