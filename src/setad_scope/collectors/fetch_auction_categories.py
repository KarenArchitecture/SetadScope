"""Public Setad auction collection, paginated per category with raw snapshots.

Four eauc grid endpoints and the separate centralboard clearance cards endpoint.
Capture-only; database writes are delegated to auction_ingestion.py.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

BASE_EAUC = "https://eauc.setadiran.ir"
BASE_GW = "https://gw.setadiran.ir"
LANDING_URL = BASE_EAUC + "/eauc/welcome.action?gateway=setad"
ROUTES = {
    "movable": "/eauc/mainEstate-Load.action",
    "immovable": "/eauc/mainImmovable-Load.action",
    "rental": "/eauc/mainRental-Load.action",
    "minor": "/eauc/mainMinor-Load.action",
}
CATEGORIES = tuple(ROUTES) + ("clearance",)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "auctions"
PROGRESS_PREFIX = "PROGRESS_JSON:"


def emit_progress(**values):
    print(PROGRESS_PREFIX + json.dumps(values, ensure_ascii=False), flush=True)


def create_session(category: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; SetadScope/0.5; public information monitoring)",
        "Accept": "application/json, text/javascript, */*;q=0.01",
    })
    if category != "clearance":
        session.headers["X-Requested-With"] = "XMLHttpRequest"
        landing = session.get(LANDING_URL, timeout=(15, 45))
        landing.raise_for_status()
        session.headers["Referer"] = landing.url
    else:
        session.headers["Referer"] = "https://fe.setadiran.ir/centralboard/"
    return session


def request_details(category: str, page: int, rows: int) -> tuple[str, dict]:
    stamp = int(time.time() * 1000)
    if category == "clearance":
        return BASE_GW + "/api/centralboard/cards/", {
            "tagCode": "342",
            "selectedOrganization": "5315",  # intentionally scoped to اموال تملیکی
            "boardCode": "3",
            "searchTypeCode": "0",
            "isLogin": "false",
            "userRole": "0",
            "queryText": "",
            "pageNumber": page,
            "pageSize": rows,
            "sort": "score,desc",
        }
    params = {
        "_search": "false",
        "nd": stamp,
        "rows": rows,
        "page": page,
        "sidx": "",
        "sord": "asc",
        "_": stamp,
    }
    if category == "immovable":
        params["propertySearchCriteriaDto.auctionType"] = "NON_PROPERTY"
    return BASE_EAUC + ROUTES[category], params


def fetch_page(session: requests.Session, category: str, page: int, rows: int = 30) -> dict[str, Any]:
    url, params = request_details(category, page, rows)
    last_error = None
    for attempt in range(1, 4):
        try:
            response = session.get(url, params=params, timeout=(20, 90))
            response.raise_for_status()
            payload = response.json()
            key = "content" if category == "clearance" else "gridModel"
            if not isinstance(payload, dict) or not isinstance(payload.get(key), list):
                raise ValueError("Response did not contain expected " + key + " list")
            return payload
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(attempt * 2)
    raise RuntimeError(f"{category} page {page} failed after retries: {last_error}")


def page_totals(payload: dict, category: str, rows: int) -> tuple[int, int | None]:
    if category == "clearance":
        page_count = payload.get("totalPages")
        record_count = payload.get("totalElements")
    else:
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
        raise RuntimeError("API did not return a usable page or record count")
    return total_pages, total_records


def collect(
    category: str,
    start_page: int = 0,
    end_page: int | None = None,
    rows: int | None = None,
    delay: float = 0.7,
    raw_dir: Path | None = None,
    session: requests.Session | None = None,
) -> dict:
    if category not in CATEGORIES:
        raise ValueError("Unsupported category")
    if start_page < 0 or (end_page is not None and end_page < start_page):
        raise ValueError("Invalid zero-based page range")
    if delay < 0:
        raise ValueError("delay cannot be negative")
    rows = rows or (5 if category == "clearance" else 30)
    if rows < 1 or rows > 100:
        raise ValueError("rows must be between 1 and 100")
    raw_dir = raw_dir or RAW_DIR / category
    raw_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    # No manifest is written on failure: importing a partial fetch is forbidden.
    summary_path = raw_dir / f"{category}_run_{stamp}.json"
    page_summaries = []
    total_fetched = 0
    total_records = None
    total_pages = None

    emit_progress(
        phase="collecting", current_page=0, total_pages=None,
        pages_completed=0, records_fetched=0, records_total=None,
        progress_percent=0, message=f"در حال اتصال به منبع {category}...",
    )

    active_session = session or create_session(category)
    first = fetch_page(active_session, category, start_page, rows)
    total_pages, total_records = page_totals(first, category, rows)
    last = min(end_page if end_page is not None else total_pages - 1, total_pages - 1)
    if start_page >= total_pages:
        raise ValueError(f"start_page {start_page} exceeds the last page {total_pages - 1}")

    try:
        for page in range(start_page, last + 1):
            payload = first if page == start_page else fetch_page(active_session, category, page, rows)
            items = payload["content" if category == "clearance" else "gridModel"]
            path = raw_dir / f"{category}_page_{page}_{stamp}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            total_fetched += len(items)
            page_summaries.append({
                "page": page,
                "file": str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path),
                "rows": len(items),
            })
            completed = len(page_summaries)
            expected = last - start_page + 1
            emit_progress(
                phase="collecting", current_page=page + 1,
                total_pages=expected, pages_completed=completed,
                records_fetched=total_fetched, records_total=total_records,
                progress_percent=int(85 * completed / expected),
                message=f"دریافت {completed} از {expected} صفحه {category}",
            )
            if page < last and delay:
                time.sleep(delay)
        summary = {
            "category": category, "started_at": stamp,
            "total_pages_reported": total_pages,
            "total_records_reported": total_records,
            "rows_saved": total_fetched, "pages": page_summaries,
            "complete_source": start_page == 0 and last == total_pages - 1,
        }
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"FETCH SUCCESS {category}: {total_fetched} records in {len(page_summaries)} pages", flush=True)
        return summary
    except Exception:
        # Partial pages stay on disk for forensic troubleshooting but are never
        # pointed to by a completed run manifest.
        raise


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch Setad auction listing categories")
    parser.add_argument("--category", choices=CATEGORIES, required=True)
    parser.add_argument("--start-page", type=int, default=0)
    parser.add_argument("--end-page", type=int, default=None)
    parser.add_argument("--rows", type=int, default=None)
    parser.add_argument("--delay", type=float, default=0.7)
    parser.add_argument("--raw-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        collect(args.category, args.start_page, args.end_page, args.rows, args.delay, args.raw_dir)
        return 0
    except Exception as exc:
        print(f"FETCH FAILED: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
