"""Normalize and upsert public Setad tender response pages into PostgreSQL.

Jalali date strings are intentionally kept as text until a verified calendar
conversion is introduced. The complete source object is retained in JSONB.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import Tender


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


def project_tender_record(record: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """Project one gridModel row; do not infer or convert source date semantics."""
    if not isinstance(record, dict):
        return None, "invalid_record"

    source_id = record.get("id")
    if source_id is None or str(source_id).strip() == "":
        return None, "missing_id"

    return {
        "source": SOURCE,
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
        "raw_payload": record,
    }, "ready"


def import_tender_pages(db: Session, paths: list[Path]) -> dict[str, int]:
    """Import every row in the supplied response pages, updating known tender IDs."""
    totals = {
        "fetched": 0,
        "stored": 0,
        "skipped_missing_id": 0,
        "skipped_invalid_record": 0,
    }

    for path in sorted(paths):
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload.get("gridModel") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            raise ValueError(f"Missing gridModel array in tender response: {path}")

        for record in records:
            totals["fetched"] += 1
            item, status = project_tender_record(record)
            if item is None:
                if status == "missing_id":
                    totals["skipped_missing_id"] += 1
                else:
                    totals["skipped_invalid_record"] += 1
                continue

            statement = insert(Tender).values(**item)
            update_values = {
                key: getattr(statement.excluded, key)
                for key in item
                if key not in {"source", "source_tender_id", "raw_payload"}
            }
            update_values["raw_payload"] = statement.excluded.raw_payload
            update_values["updated_at"] = datetime.now(timezone.utc)
            statement = statement.on_conflict_do_update(
                constraint="uq_tenders_source_tender",
                set_=update_values,
            )
            db.execute(statement)
            totals["stored"] += 1

        db.commit()

    return totals
