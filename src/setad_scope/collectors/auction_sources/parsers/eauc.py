from __future__ import annotations

import math


def extract_rows(payload: dict) -> list:
    rows = payload.get("gridModel") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Response did not contain expected gridModel list")
    return rows


def page_totals(payload: dict, rows: int) -> tuple[int, int | None]:
    page_count = payload.get("total")
    record_count = payload.get("records")
    try:
        total_records = int(record_count)
    except (TypeError, ValueError):
        total_records = None
    try:
        total_pages = int(page_count)
    except (TypeError, ValueError):
        total_pages = 0
    if total_pages < 1 and total_records is not None:
        total_pages = max(1, math.ceil(total_records / rows))
    if total_pages < 1:
        raise RuntimeError("EAUC API did not return a usable page or record count")
    return total_pages, total_records


def reported_page(payload: dict):
    return payload.get("page")
