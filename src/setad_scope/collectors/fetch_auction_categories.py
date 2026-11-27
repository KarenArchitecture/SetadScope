"""Multi-group Setad auction collection with shared pagination and raw snapshots."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
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


class SourceContextMismatch(RuntimeError):
    """Raised when EAUC returns records from a different owning collection."""


def _record_auctioneer_id(record: dict, category: str):
    if category == "movable":
        party = record.get("auctionParty")
        party = party if isinstance(party, dict) else {}
        auction = party.get("auction")
    elif category == "minor":
        auction = record
    else:
        auction = record.get("auction") or record.get("immovableAuction")

    auction = auction if isinstance(auction, dict) else {}
    auctioneer = auction.get("auctioneer")
    auctioneer = auctioneer if isinstance(auctioneer, dict) else {}
    return auctioneer.get("id")


def validate_source_context(rows: list[dict], source) -> None:
    """Reject a snapshot if EAUC's session context returned another organization."""
    expected_id = source.expected_auctioneer_id
    if expected_id is None or not rows:
        return

    observed_ids = []
    mismatches = []
    for row_number, record in enumerate(rows, start=1):
        if not isinstance(record, dict):
            continue
        actual_id = _record_auctioneer_id(record, source.category)
        if actual_id is None:
            continue
        actual_id = str(actual_id)
        observed_ids.append(actual_id)
        if actual_id != str(expected_id):
            mismatches.append((row_number, actual_id))

    if mismatches:
        examples = ", ".join(
            f"row {row_number}: auctioneer.id={actual_id}"
            for row_number, actual_id in mismatches[:5]
        )
        unexpected_ids = ", ".join(sorted({actual_id for _, actual_id in mismatches}))
        raise SourceContextMismatch(
            f"EAUC source context mismatch for {source.collection_group}/{source.category}: "
            f"expected auctioneer.id={expected_id}, received {unexpected_ids} ({examples}). "
            "The response was rejected to prevent cross-collection data contamination."
        )

    if not observed_ids:
        raise SourceContextMismatch(
            f"Cannot verify EAUC source context for {source.collection_group}/{source.category}: "
            f"no auctioneer.id was present; expected {expected_id}. "
            "The response was rejected rather than stored under an unverified collection."
        )


def _centralboard_response_diagnostic(response, page: int) -> dict[str, Any]:
    """Capture safe, useful diagnostics for a Central Board HTTP failure."""
    allowed_headers = {
        "content-type", "content-length", "date", "server", "retry-after",
        "via", "x-request-id", "x-correlation-id", "cf-ray", "x-cache",
        "x-envoy-upstream-service-time", "request-id", "traceparent",
    }
    response_headers = getattr(response, "headers", {}) or {}
    selected_headers = {
        str(name): str(value)
        for name, value in response_headers.items()
        if str(name).lower() in allowed_headers
        or str(name).lower().startswith(("x-ratelimit-", "x-rate-limit-"))
    }
    try:
        body = response.text or ""
    except Exception:
        body = "<response body unavailable>"
    request = getattr(response, "request", None)
    request_headers = getattr(request, "headers", {}) or {}
    elapsed = getattr(response, "elapsed", None)
    try:
        elapsed_ms = int(elapsed.total_seconds() * 1000) if elapsed is not None else None
    except (AttributeError, TypeError, ValueError):
        elapsed_ms = None
    return {
        "status_code": getattr(response, "status_code", None),
        "page_number": page,
        "page_number_base": 0,
        "url": getattr(response, "url", None),
        "elapsed_ms": elapsed_ms,
        "response_headers": selected_headers,
        # Header names only: never persist Cookie or Authorization values.
        "request_header_names": sorted(str(name) for name in request_headers.keys()),
        "body_preview": body[:2000],
    }


class ClearancePreconditionError(RuntimeError):
    def __init__(self, source_key: str, page: int, response):
        self.diagnostic = _centralboard_response_diagnostic(response, page)
        headers = self.diagnostic["response_headers"]
        header_summary = ", ".join(f"{key}={value}" for key, value in headers.items())
        body_summary = " ".join(self.diagnostic["body_preview"].split())[:500]
        super().__init__(
            f"{source_key}: HTTP 428 در صفحهٔ {page} (شماره‌گذاری از صفر); "
            f"elapsed_ms={self.diagnostic['elapsed_ms']}; "
            f"headers=[{header_summary or 'none'}]; "
            f"request_headers={','.join(self.diagnostic['request_header_names']) or 'unknown'}; "
            f"body={body_summary!r}"
        )


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
            if source.adapter == "centralboard" and response.status_code == 428:
                raise ClearancePreconditionError(
                    f"{source.collection_group}/{category}", page, response
                )
            response.raise_for_status()
            payload = response.json()
            rows = extract_rows(payload, source.adapter)
            validate_source_context(rows, source)
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




CENTRALBOARD_RETRY_INITIAL_SECONDS = 30.0
CENTRALBOARD_RETRY_MAX_SECONDS = 300.0
CENTRALBOARD_CHECKPOINT_VERSION = 1


def _write_json_atomically(path: Path, payload: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _centralboard_checkpoint_identity(source, rows: int) -> dict:
    return {
        "version": CENTRALBOARD_CHECKPOINT_VERSION,
        "collection_group": source.collection_group,
        "category": source.category,
        "source": source.source,
        "adapter": source.adapter,
        "rows": rows,
    }


def _load_centralboard_checkpoint(path: Path, raw_dir: Path, identity: dict) -> dict | None:
    if not path.is_file():
        return None
    try:
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
        if any(checkpoint.get(key) != value for key, value in identity.items()):
            return None
        if checkpoint.get("status") not in {"collecting", "waiting", "interrupted", "partial"}:
            return None
        if not isinstance(checkpoint.get("stamp"), str):
            return None
        if not isinstance(checkpoint.get("next_page"), int) or checkpoint["next_page"] < 0:
            return None
        pages = checkpoint.get("pages")
        if not isinstance(pages, list):
            return None
        for item in pages:
            if not isinstance(item, dict) or not item.get("file"):
                return None
            filename = Path(str(item["file"])).name
            if not filename or not (raw_dir / filename).is_file():
                return None
        return checkpoint
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _retry_after_seconds(error: ClearancePreconditionError) -> float | None:
    headers = error.diagnostic.get("response_headers", {})
    value = next(
        (str(item) for key, item in headers.items() if str(key).lower() == "retry-after"),
        None,
    )
    if not value:
        return None
    try:
        return max(1.0, float(value.strip()))
    except (TypeError, ValueError):
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(1.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def _fetch_centralboard_page_with_wait(
    session: requests.Session,
    category: str,
    page: int,
    rows: int,
    collection_group: str,
    checkpoint: dict,
    checkpoint_path: Path,
    page_summaries: list[dict],
    total_pages: int | None,
    total_records: int | None,
    retry_initial_seconds: float,
    retry_max_seconds: float,
) -> dict:
    retry_count = int(checkpoint.get("retry_count", 0) or 0)
    while True:
        try:
            payload = _fetch_for_group(session, category, page, rows, collection_group)
            if checkpoint.get("status") == "waiting":
                checkpoint.update({
                    "status": "collecting",
                    "waiting_page": None,
                    "retry_count": 0,
                    "last_error": None,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
                _write_json_atomically(checkpoint_path, checkpoint)
                emit_progress(
                    collection_group=collection_group,
                    category=category,
                    phase="collecting",
                    current_page=len(page_summaries) + 1,
                    total_pages=total_pages,
                    pages_completed=len(page_summaries),
                    records_fetched=sum(int(item.get("rows", 0)) for item in page_summaries),
                    records_total=total_records,
                    progress_percent=int(
                        85 * len(page_summaries) / max(int(total_pages or 1), 1)
                    ),
                    message=f"دسترسی به منبع برقرار شد؛ ادامه دریافت از صفحه {page}.",
                )
            return payload
        except ClearancePreconditionError as exc:
            retry_count += 1
            retry_after = _retry_after_seconds(exc)
            initial = max(float(retry_initial_seconds), 0.0)
            cap = max(float(retry_max_seconds), initial)
            backoff = min(initial * (2 ** min(retry_count - 1, 10)), cap)
            wait_seconds = retry_after if retry_after is not None else backoff
            checkpoint.update({
                "status": "waiting",
                "waiting_page": page,
                "retry_count": retry_count,
                "last_retry_delay_seconds": wait_seconds,
                "last_error": exc.diagnostic,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            _write_json_atomically(checkpoint_path, checkpoint)
            completed = len(page_summaries)
            emit_progress(
                collection_group=collection_group,
                category=category,
                phase="waiting_for_access",
                current_page=completed + 1,
                total_pages=total_pages,
                pages_completed=completed,
                records_fetched=sum(int(item.get("rows", 0)) for item in page_summaries),
                records_total=total_records,
                progress_percent=int(85 * completed / max(int(total_pages or 1), 1)),
                retry_count=retry_count,
                retry_in_seconds=wait_seconds,
                waiting_page=page,
                message=(
                    f"سرور برای صفحه {page} پاسخ HTTP 428 داده است؛ "
                    f"درخواست متوقف شد و {int(wait_seconds)} ثانیه دیگر دوباره بررسی می‌شود."
                ),
            )
            time.sleep(wait_seconds)


def _collect_centralboard(
    session: requests.Session,
    category: str,
    start_page: int,
    end_page: int | None,
    rows: int,
    delay: float,
    raw_dir: Path,
    source,
    retry_initial_seconds: float,
    retry_max_seconds: float,
    resume: bool,
) -> dict:
    group = source.collection_group
    raw_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = raw_dir / f"{category}_checkpoint.json"
    identity = _centralboard_checkpoint_identity(source, rows)
    checkpoint = (
        _load_centralboard_checkpoint(checkpoint_path, raw_dir, identity)
        if resume and start_page == 0
        else None
    )
    resumed = checkpoint is not None

    if checkpoint:
        stamp = checkpoint["stamp"]
        page_summaries = list(checkpoint["pages"])
        total_fetched = sum(int(item.get("rows", 0)) for item in page_summaries)
        total_pages = checkpoint.get("total_pages")
        total_records = checkpoint.get("total_records")
        effective_start = int(checkpoint["next_page"])
        first_payload = None
        emit_progress(
            collection_group=group,
            category=category,
            phase="resuming",
            current_page=len(page_summaries),
            total_pages=total_pages,
            pages_completed=len(page_summaries),
            records_fetched=total_fetched,
            records_total=total_records,
            progress_percent=int(85 * len(page_summaries) / max(int(total_pages or 1), 1)),
            message=f"نقطه ذخیره‌شده پیدا شد؛ ادامه دریافت از صفحه {effective_start}.",
        )
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        page_summaries = []
        total_fetched = 0
        total_pages = None
        total_records = None
        effective_start = start_page
        first_payload = None
        checkpoint = {
            **identity,
            "stamp": stamp,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "collecting",
            "next_page": start_page,
            "waiting_page": None,
            "retry_count": 0,
            "total_pages": None,
            "total_records": None,
            "pages": [],
        }
        _write_json_atomically(checkpoint_path, checkpoint)

    summary_path = raw_dir / f"{category}_run_{stamp}.json"

    try:
        if total_pages is None:
            first_payload = _fetch_centralboard_page_with_wait(
                session, category, effective_start, rows, group,
                checkpoint, checkpoint_path, page_summaries,
                total_pages, total_records,
                retry_initial_seconds, retry_max_seconds,
            )
            total_pages, total_records = page_totals(
                first_payload, category, rows, group,
            )
            checkpoint.update({
                "total_pages": total_pages,
                "total_records": total_records,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            _write_json_atomically(checkpoint_path, checkpoint)

        final_source_page = total_pages - 1
        last = min(end_page if end_page is not None else final_source_page, final_source_page)
        if effective_start > last and not page_summaries:
            raise ValueError(
                f"start_page {effective_start} exceeds the last page {final_source_page}"
            )

        for page in range(effective_start, last + 1):
            if page == effective_start and first_payload is not None:
                payload = first_payload
            else:
                payload = _fetch_centralboard_page_with_wait(
                    session, category, page, rows, group,
                    checkpoint, checkpoint_path, page_summaries,
                    total_pages, total_records,
                    retry_initial_seconds, retry_max_seconds,
                )

            items = extract_rows(payload, source.adapter)
            page_path = raw_dir / f"{category}_page_{page}_{stamp}.json"
            page_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            total_fetched += len(items)
            page_summaries.append({
                "page": page,
                "file": (
                    str(page_path.relative_to(PROJECT_ROOT))
                    if page_path.is_relative_to(PROJECT_ROOT)
                    else str(page_path)
                ),
                "rows": len(items),
            })

            checkpoint.update({
                "status": "collecting",
                "next_page": page + 1,
                "waiting_page": None,
                "retry_count": 0,
                "total_pages": total_pages,
                "total_records": total_records,
                "rows_saved": total_fetched,
                "pages": page_summaries,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            _write_json_atomically(checkpoint_path, checkpoint)

            completed = len(page_summaries)
            emit_progress(
                collection_group=group,
                category=category,
                phase="collecting",
                current_page=completed,
                total_pages=total_pages,
                pages_completed=completed,
                records_fetched=total_fetched,
                records_total=total_records,
                progress_percent=int(85 * completed / max(total_pages, 1)),
                message=f"دریافت {completed} از {total_pages} صفحه {group}/{category}",
            )
            if page < last and delay:
                time.sleep(delay)

        complete_source = (
            start_page == 0
            and last == final_source_page
            and len(page_summaries) >= total_pages
        )
        summary = {
            "collection_group": group,
            "category": category,
            "source": source.source,
            "started_at": stamp,
            "total_pages_reported": total_pages,
            "total_records_reported": total_records,
            "rows_saved": total_fetched,
            "pages": page_summaries,
            "complete_source": complete_source,
            "source_page_base": 0,
            "resumed": resumed,
        }
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if complete_source:
            checkpoint_path.unlink(missing_ok=True)
        else:
            checkpoint.update({
                "status": "partial",
                "next_page": last + 1,
                "pages": page_summaries,
                "rows_saved": total_fetched,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            _write_json_atomically(checkpoint_path, checkpoint)

        print(
            f"FETCH SUCCESS {group}/{category}: "
            f"{total_fetched} records in {len(page_summaries)} pages",
            flush=True,
        )
        return summary
    except Exception as exc:
        checkpoint.update({
            "status": "interrupted",
            "next_page": int(checkpoint.get("next_page", effective_start)),
            "pages": page_summaries,
            "rows_saved": total_fetched,
            "last_error": str(exc)[:2000],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        _write_json_atomically(checkpoint_path, checkpoint)
        if page_summaries:
            partial_path = raw_dir / f"{category}_partial_{stamp}.json"
            partial_path.write_text(
                json.dumps({
                    "collection_group": group,
                    "category": category,
                    "complete_source": False,
                    "pages": page_summaries,
                    "error": str(exc)[:2000],
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print("PARTIAL_MANIFEST:" + partial_path.name, flush=True)
        raise


def collect(
    category: str,
    start_page: int = 0,
    end_page: int | None = None,
    rows: int | None = None,
    delay: float = 0.7,
    raw_dir: Path | None = None,
    session: requests.Session | None = None,
    collection_group: str | None = None,
    retry_initial_seconds: float = CENTRALBOARD_RETRY_INITIAL_SECONDS,
    retry_max_seconds: float = CENTRALBOARD_RETRY_MAX_SECONDS,
    resume: bool = True,
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

    if source.adapter == "centralboard":
        return _collect_centralboard(
            active_session,
            category,
            start_page,
            end_page,
            rows,
            delay,
            raw_dir,
            source,
            retry_initial_seconds,
            retry_max_seconds,
            resume,
        )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    summary_path = raw_dir / f"{category}_run_{stamp}.json"
    page_summaries = []
    total_fetched = 0
    total_records = None
    total_pages = None

    first = _fetch_for_group(active_session, category, start_page, rows, group)
    total_pages, total_records = page_totals(first, category, rows, group)
    first_reported_page = reported_page(first, source.adapter)
    try:
        first_reported_page = int(first_reported_page)
    except (TypeError, ValueError):
        first_reported_page = start_page

    if start_page == 0 and first_reported_page == 1:
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
            payload = first if page == effective_start else _fetch_for_group(
                active_session, category, page, rows, group
            )
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
    except Exception as exc:
        raise RuntimeError(
            f"{group}/{category} page collection failed: {exc}"
        ) from exc
def parse_args():
    parser = argparse.ArgumentParser(description="Fetch Setad auction listing categories")
    parser.add_argument("--group", choices=COLLECTION_GROUPS, default=None)
    parser.add_argument("--category", choices=CATEGORIES, default=None)
    parser.add_argument("--start-page", type=int, default=0)
    parser.add_argument("--end-page", type=int, default=None)
    parser.add_argument("--rows", type=int, default=None)
    parser.add_argument("--delay", type=float, default=0.7)
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("--fresh", action="store_true", help="Ignore an incomplete Central Board checkpoint and start over")
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
                resume=not args.fresh,
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
                resume=not args.fresh,
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
