"""Normalize and upsert public Setad tender response pages into PostgreSQL.

Original Jalali date strings remain unchanged for display and audit; parallel
timezone-aware Gregorian columns support reliable filtering and sorting. The
complete source object is retained in JSONB.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import IngestionRun, Tender
from app.services.date_normalization import parse_setad_datetime
from app.services.keyword_matching import matched_keywords
from app.services.keyword_settings import configured_keywords


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "tenders"
SOURCE = "setad_tender"


def _as_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return str(value)


def _organization_name(value: object) -> str | None:
    if isinstance(value, dict):
        return _as_text(value.get("name"))
    return _as_text(value)


def project_tender_record(record: dict[str, Any], keywords: tuple[str, ...] | None = None) -> tuple[dict[str, Any] | None, str]:
    """Project one gridModel row; do not infer or convert source date semantics."""
    if not isinstance(record, dict):
        return None, "invalid_record"

    source_id = record.get("id")
    if source_id is None or str(source_id).strip() == "":
        return None, "missing_id"

    found = matched_keywords(
        record.get("title"), record.get("domainsDescription") or record.get("description"),
        record.get("typeName"), keywords=keywords,
    )

    return {
        "source": SOURCE,
        "has_keyword_match": bool(found),
        "matched_keywords": found,
        "source_tender_id": str(source_id),
        "tender_number": _as_text(record.get("number")),
        "title": _as_text(record.get("title")),
        "tender_type": _as_text(record.get("type")),
        "type_name": _as_text(record.get("typeName")),
        "organization": _organization_name(record.get("organization")),
        "province": _as_text(record.get("operationProvinceName")),
        "city": _as_text(record.get("operationCityName")),
        "description": _as_text(record.get("domainsDescription") or record.get("description")),
        "state": _as_text(record.get("stateName") or record.get("state")),
        "public_notification_date": _as_text(record.get("publicNotificationDate")),
        "documents_deadline_date": _as_text(record.get("documentsDeadlineDate")),
        "proposal_deadline_date": _as_text(record.get("proposalDeadlineDate")),
        "opening_date": _as_text(record.get("openingDate")),
        "public_notification_at": parse_setad_datetime(record.get("publicNotificationDate")),
        "documents_deadline_at": parse_setad_datetime(record.get("documentsDeadlineDate")),
        "proposal_deadline_at": parse_setad_datetime(record.get("proposalDeadlineDate")),
        "opening_at": parse_setad_datetime(record.get("openingDate")),
        "raw_payload": record,
    }, "ready"


def import_tender_pages(db: Session, paths: list[Path], progress_callback=None) -> dict[str, int]:
    """Import tender pages and persist a scoped history record for the run."""
    totals = {
        "fetched": 0,
        "matched": 0,
        "stored": 0,
        "changed": 0,
        "unchanged": 0,
        "skipped_missing_id": 0,
        "skipped_invalid_record": 0,
    }

    run = IngestionRun(status="running", kind="tenders", category=None)
    db.add(run)
    db.commit()
    run_id = run.id

    try:
        active_keywords = configured_keywords(db)
        ordered_paths = sorted(paths)
        total_pages = len(ordered_paths)
        for page_index, path in enumerate(ordered_paths, start=1):
            payload = json.loads(path.read_text(encoding="utf-8"))
            records = payload.get("gridModel") if isinstance(payload, dict) else None
            if not isinstance(records, list):
                raise ValueError(f"Missing gridModel array in tender response: {path}")

            for record in records:
                totals["fetched"] += 1
                item, status = project_tender_record(record, keywords=active_keywords)
                if item is None:
                    if status == "missing_id":
                        totals["skipped_missing_id"] += 1
                    else:
                        totals["skipped_invalid_record"] += 1
                    continue

                if item["has_keyword_match"]:
                    totals["matched"] += 1

                statement = insert(Tender).values(**item)
                identity_fields = {"source", "source_tender_id"}
                update_values = {
                    key: getattr(statement.excluded, key)
                    for key in item
                    if key not in identity_fields
                }
                changed_conditions = [
                    getattr(Tender, key).is_distinct_from(getattr(statement.excluded, key))
                    for key in item
                    if key not in identity_fields
                ]
                statement = statement.on_conflict_do_update(
                    constraint="uq_tenders_source_tender",
                    set_={**update_values, "updated_at": datetime.now(timezone.utc)},
                    where=or_(*changed_conditions),
                ).returning(Tender.id)
                changed_id = db.execute(statement).scalar_one_or_none()
                totals["stored"] += 1
                if changed_id is None:
                    totals["unchanged"] += 1
                else:
                    totals["changed"] += 1

            db.commit()
            if progress_callback:
                progress_callback({
                    "pages_completed": page_index,
                    "total_pages": total_pages,
                    **totals,
                })

        run = db.get(IngestionRun, run_id)
        run.status = "success"
        run.finished_at = datetime.now(timezone.utc)
        run.fetched = totals["fetched"]
        run.matched = totals["matched"]
        run.stored = totals["stored"]
        db.commit()
        return totals
    except Exception as exc:
        db.rollback()
        failed = db.get(IngestionRun, run_id)
        if failed is not None:
            failed.status = "failed"
            failed.error = str(exc)[:5000]
            failed.finished_at = datetime.now(timezone.utc)
            db.commit()
        raise
