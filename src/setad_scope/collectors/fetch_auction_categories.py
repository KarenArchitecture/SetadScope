"""Multi-group Setad auction collection with shared pagination and raw snapshots."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from .auction_sources.parsers import extract_rows, page_totals as adapter_page_totals, reported_page
from .auction_sources.registry import (
    ALL_CATEGORIES,
    COLLECTION_GROUPS,
    DEFAULT_COLLECTION_GROUP,
    categories_for_group,
    resolve_collection_group,
    source_for,
)

BASE_EAUC = "https://eauc.setadiran.ir"
BASE_GW = "https://gw.setadiran.ir"
LANDING_URL = BASE_EAUC + "/eauc/welcome.action?gateway=setad"
ROUTES = {
    "movable": "/eauc/mainEstate-Load.action",
    "immovable": "/eauc/mainImmovable-Load.action",
    "rental": "/eauc/mainRental-Load.action",
    "minor": "/eauc/mainMinor-Load.action",
}
CATEGORIES = ALL_CATEGORIES
PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "auctions"
PROGRESS_PREFIX = "PROGRESS_JSON:"


def emit_progress(**values):
    print(PROGRESS_PREFIX + json.dumps(values, ensure_ascii=False), flush=True)


def category_raw_dir(collection_group: str, category: str) -> Path:
    # Keep the original executive-agency layout readable by existing scripts.
    if collection_group == DEFAULT_COLLECTION_GROUP:
        return RAW_DIR / category
    return RAW_DIR / collection_group / category


def create_session(category: str, collection_group: str | None = None) -> requests.Session:
    source = source_for(category, collection_group)
    session = requests.Session()
    # Ignore HTTP(S)_PROXY / ALL_PROXY environment variables. This mirrors the
    # known-good collector route and avoids unexpected application proxies.
    session.trust_env = False
    session.proxies.clear()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; SetadScope/0.6; public information monitoring)",
        "Accept": "application/json, text/javascript, */*;q=0.01",
    })
    if source.adapter == "eauc":
        session.headers["X-Requested-With"] = "XMLHttpRequest"
        landing = session.get(source.landing_url or LANDING_URL, timeout=(15, 45))
        landing.raise_for_status()
        session.headers["Referer"] = landing.url
    else:
        session.headers["Referer"] = source.referer or "https://fe.setadiran.ir/centralboard/"
    return session


def request_details(
    category: str,
    page: int,
    rows: int,
    collection_group: str | None = None,
) -> tuple[str, dict]:
    source = source_for(category, collection_group)
    url = source.base_url + source.path
    params = dict(source.fixed_params)
    if source.adapter == "centralboard":
        params.update({"pageNumber": page, "pageSize": rows})
    else:
        stamp = int(time.time() * 1000)
        params.update({
            "_search": "false",
            "nd": stamp,
            "rows": rows,
            "page": page,
            "sidx": "",
            "sord": "asc",
            "_": stamp,
        })
    return url, params


def fetch_page(
    session: requests.Session,
    category: str,
    page: int,
    rows: int = 30,
    collection_group: str | None = None,
) -> dict[str, Any]:
    source = source_for(category, collection_group)
    url, params = request_details(category, page, rows, collection_group)
    last_error = None
    for attempt in range(1, 4):
        try:
            response = session.get(url, params=params, timeout=(20, 90))
            response.raise_for_status()
            payload = response.json()
            extract_rows(payload, source.adapter)
            return payload
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(attempt * 2)
    raise RuntimeError(f"{collection_group or source.collection_group}/{category} page {page} failed after retries: {last_error}")


def page_totals(
    payload: dict,
    category: str,
    rows: int,
    collection_group: str | None = None,
) -> tuple[int, int | None]:
    source = source_for(category, collection_group)
    return adapter_page_totals(payload, source.adapter, rows)


def _fetch_for_group(session, category: str, page: int, rows: int, collection_group: str):
    # Preserve the four-argument call contract used by existing collector tests
    # and integrations for the original executive-agency collection.
    if collection_group == DEFAULT_COLLECTION_GROUP:
        return fetch_page(session, category, page, rows)
    return fetch_page(session, category, page, rows, collection_group)


def collect(
    category: str,
    start_page: int = 0,
    end_page: int | None = None,
    rows: int | None = None,
    delay: float = 0.7,
    raw_dir: Path | None = None,
    session: requests.Session | None = None,
    collection_group: str | None = None,
) -> dict:
    group = resolve_collection_group(category, collection_group)
    source = source_for(category, group)
    if start_page < 0 or (end_page is not None and end_page < start_page):
        raise ValueError("Invalid zero-based page range")
    if delay < 0:
        raise ValueError("delay cannot be negative")
    rows = source.default_rows if rows is None else rows
    if rows < 1 or rows > 100:
        raise ValueError("rows must be between 1 and 100")
    raw_dir = raw_dir or category_raw_dir(group, category)
    raw_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    summary_path = raw_dir / f"{category}_run_{stamp}.json"
    page_summaries = []
    total_fetched = 0
    total_records = None
    total_pages = None

    emit_progress(
        collection_group=group,
        category=category,
        phase="collecting",
        current_page=0,
        total_pages=None,
        pages_completed=0,
        records_fetched=0,
        records_total=None,
        progress_percent=0,
        message=f"در حال اتصال به منبع {group}/{category}...",
    )

    active_session = session or create_session(category, group)
    if isinstance(active_session, requests.Session):
        active_session.trust_env = False
        active_session.proxies.clear()
    first = _fetch_for_group(active_session, category, start_page, rows, group)
    total_pages, total_records = page_totals(first, category, rows, group)
    first_reported_page = reported_page(first, source.adapter)
    try:
        first_reported_page = int(first_reported_page)
    except (TypeError, ValueError):
        first_reported_page = start_page

    if source.adapter == "centralboard":
        effective_start = start_page
        final_source_page = total_pages - 1
    elif start_page == 0 and first_reported_page == 1:
        # EAUC accepts page=0 but returns the first page as page=1.
        effective_start = 1
        final_source_page = total_pages
    else:
        effective_start = start_page
        final_source_page = total_pages if first_reported_page >= 1 else total_pages - 1

    last = min(end_page if end_page is not None else final_source_page, final_source_page)
    if effective_start > final_source_page:
        raise ValueError(f"start_page {start_page} exceeds the last page {final_source_page}")

    try:
        for page in range(effective_start, last + 1):
            payload = first if page == effective_start else _fetch_for_group(active_session, category, page, rows, group)
            if source.adapter == "eauc":
                actual_page = payload.get("page")
                if actual_page is not None and int(actual_page) != page:
                    raise RuntimeError(
                        f"Requested EAUC page {page}, but API reported page {actual_page}; "
                        "aborting to avoid duplicate or missing pages."
                    )
            items = extract_rows(payload, source.adapter)
            path = raw_dir / f"{category}_page_{page}_{stamp}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            total_fetched += len(items)
            page_summaries.append({
                "page": page,
                "file": str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path),
                "rows": len(items),
            })
            completed = len(page_summaries)
            expected = last - effective_start + 1
            emit_progress(
                collection_group=group,
                category=category,
                phase="collecting",
                current_page=completed,
                total_pages=expected,
                pages_completed=completed,
                records_fetched=total_fetched,
                records_total=total_records,
                progress_percent=int(85 * completed / expected),
                message=f"دریافت {completed} از {expected} صفحه {group}/{category}",
            )
            if page < last and delay:
                time.sleep(delay)
        summary = {
            "collection_group": group,
            "category": category,
            "source": source.source,
            "started_at": stamp,
            "total_pages_reported": total_pages,
            "total_records_reported": total_records,
            "rows_saved": total_fetched,
            "pages": page_summaries,
            "complete_source": start_page == 0 and last == final_source_page,
            "source_page_base": final_source_page - total_pages + 1,
        }
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"FETCH SUCCESS {group}/{category}: {total_fetched} records in {len(page_summaries)} pages", flush=True)
        return summary
    except Exception:
        # Partial pages remain available for diagnostics, but no successful
        # manifest is written, so ingestion cannot mistake them for a snapshot.
        raise


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch Setad auction listing categories")
    parser.add_argument("--group", choices=COLLECTION_GROUPS, default=None)
    parser.add_argument("--category", choices=CATEGORIES, default=None)
    parser.add_argument("--start-page", type=int, default=0)
    parser.add_argument("--end-page", type=int, default=None)
    parser.add_argument("--rows", type=int, default=None)
    parser.add_argument("--delay", type=float, default=0.7)
    parser.add_argument("--raw-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    group = args.group
    if args.category:
        try:
            group = resolve_collection_group(args.category, group)
            collect(
                args.category,
                args.start_page,
                args.end_page,
                args.rows,
                args.delay,
                args.raw_dir,
                collection_group=group,
            )
            return 0
        except Exception as exc:
            print(f"FETCH FAILED: {exc}", file=sys.stderr, flush=True)
            return 1

    group = group or DEFAULT_COLLECTION_GROUP
    failures = []
    for category in categories_for_group(group):
        try:
            collect(
                category,
                args.start_page,
                args.end_page,
                args.rows,
                args.delay,
                args.raw_dir,
                collection_group=group,
            )
        except Exception as exc:
            failures.append(f"{category}: {exc}")
            print(f"FETCH FAILED {group}/{category}: {exc}", file=sys.stderr, flush=True)
    if failures:
        print("One or more auction sources failed: " + " | ".join(failures), file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
