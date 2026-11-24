"""Progress and download responses for the three Excel endpoints."""
from dataclasses import dataclass
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import func, select

from app.services.excel_export import build_excel

router = APIRouter(tags=["excel"])
NO_CACHE = {"Cache-Control": "no-store"}


@dataclass(frozen=True)
class ProgressSnapshot:
    phase: str
    processed: int = 0
    total: int | None = None


@dataclass
class ExportProgress:
    snapshot: ProgressSnapshot = ProgressSnapshot("counting")


active_exports: dict[UUID, ExportProgress] = {}


async def track_excel_export(export_id: UUID | None = None):
    if export_id is None:
        yield None
        return

    if export_id in active_exports:
        raise HTTPException(status_code=409, detail="This Excel export is already running")
    progress = ExportProgress()
    active_exports[export_id] = progress
    try:
        yield progress
    finally:
        del active_exports[export_id]


@router.get("/api/excel/progress/{export_id}")
async def excel_progress(export_id: UUID, response: Response):
    response.headers.update(NO_CACHE)
    progress = active_exports.get(export_id)
    return progress.snapshot if progress else None


def excel_download(
    db, query, progress: ExportProgress | None, filename: str,
    sheet_name, table_name, headers, rows, *, widths, numeric_columns=(),
):
    def tracked_rows():
        # Count and export the same rows even if a collection updates the archive.
        db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
        progress.snapshot = ProgressSnapshot("writing", total=total)
        processed = 0
        for row in rows():
            yield row
            processed += 1
            progress.snapshot = ProgressSnapshot("writing", processed, total)
        progress.snapshot = ProgressSnapshot("finalizing", processed, processed)

    data = build_excel(
        sheet_name, table_name, headers, tracked_rows() if progress else rows(),
        widths, numeric_columns,
    )
    return Response(
        data.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={**NO_CACHE, "Content-Disposition": f"attachment; filename={filename}"},
    )
