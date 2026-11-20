from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import requests


BASE_URL = "https://etend.setadiran.ir"
DEFAULT_LANDING_URL = f"{BASE_URL}/etend/welcome.action?gateway=setad"
LANDING_URLS = (
    DEFAULT_LANDING_URL,
    f"{BASE_URL}/etend/",
)
ENDPOINT = f"{BASE_URL}/etend/callMainPageCartable-anonymous.action"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "tenders"
MAX_RETRIES = 3
PROGRESS_PREFIX = "PROGRESS_JSON:"


class CsrfTokenParser(HTMLParser):
    """Extract the token used by the Struts token interceptor from landing HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.token: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value for key, value in attrs}
        if tag.lower() == "input":
            name = (values.get("name") or "").strip().lower()
            value = (values.get("value") or "").strip()
            if name == "csrf_token" and value:
                self.token = value
        elif tag.lower() == "meta":
            name = (values.get("name") or values.get("id") or "").strip().lower()
            value = (values.get("content") or "").strip()
            if name in {"csrf_token", "csrf-token"} and value:
                self.token = value


def extract_csrf_token(html: str, cookies: requests.cookies.RequestsCookieJar | None = None) -> str | None:
    parser = CsrfTokenParser()
    parser.feed(html or "")
    if parser.token:
        return parser.token

    patterns = (
        r"""["']csrf_token["']\s*[:=]\s*["']([^"']+)["']""",
        r"""csrf_token\s*=\s*["']([^"']+)["']""",
    )
    for pattern in patterns:
        match = re.search(pattern, html or "", re.IGNORECASE)
        if match:
            return match.group(1)

    if cookies is not None:
        for cookie in cookies:
            if cookie.name.lower() in {"csrf_token", "csrf-token"} and cookie.value:
                return cookie.value
    return None


def sanitize_error(value: object) -> str:
    return re.sub(r"(?i)(csrf_token=)[^&\s]+", r"\1[REDACTED]", str(value))


def emit_progress(**values: Any) -> None:
    print(PROGRESS_PREFIX + json.dumps(values, ensure_ascii=False), flush=True)


def create_session(landing_url: str | None = None) -> tuple[requests.Session, str, str]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": BASE_URL,
        }
    )

    configured_url = landing_url or os.getenv("SETAD_TENDER_LANDING_URL")
    candidates = [configured_url] if configured_url else list(LANDING_URLS)
    last_error: Exception | None = None

    for candidate in candidates:
        try:
            response = session.get(candidate, timeout=(20, 60))
            response.raise_for_status()
            token = extract_csrf_token(response.text, session.cookies)
            if token:
                session.headers["Referer"] = response.url
                return session, token, response.url
            last_error = RuntimeError(
                f"No csrf_token field was found in the HTML returned by {response.url}"
            )
        except requests.RequestException as exc:
            last_error = exc

    raise RuntimeError(
        "Could not obtain the tender CSRF token from the public landing page. "
        "The collector did not send a hard-coded or stale token. "
        f"Last landing-page result: {last_error}"
    )


def refresh_csrf_token(
    session: requests.Session, landing_url: str
) -> str | None:
    response = session.get(landing_url, timeout=(20, 60))
    response.raise_for_status()
    token = extract_csrf_token(response.text, session.cookies)
    if token:
        session.headers["Referer"] = response.url
    return token


def page_params(token: str, page: int, rows: int, now_ms: int | None = None) -> dict[str, Any]:
    stamp = now_ms if now_ms is not None else int(time.time() * 1000)
    return {
        "struts.token.name": "csrf_token",
        "csrf_token": token,
        "_search": "false",
        "nd": stamp,
        "rows": rows,
        "page": page,
        "sidx": "",
        "sord": "asc",
        "_": stamp,
    }


def fetch_page(
    session: requests.Session,
    token: str,
    page: int,
    rows: int = 30,
    landing_url: str | None = None,
) -> tuple[dict[str, Any], str]:
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(
                ENDPOINT,
                params=page_params(token, page, rows),
                timeout=(20, 90),
            )
            if response.status_code in {400, 401, 403, 419} and landing_url:
                refreshed = refresh_csrf_token(session, landing_url)
                if refreshed:
                    token = refreshed
                    continue

            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("gridModel"), list):
                raise RuntimeError(
                    "Tender response did not contain the expected top-level gridModel array. "
                    "The endpoint may have changed or the session may have expired."
                )
            return payload, token
        except (requests.RequestException, requests.exceptions.JSONDecodeError, RuntimeError) as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                break
            wait_seconds = attempt * 2
            print(
                f"Tender page {page}: attempt {attempt} failed ({sanitize_error(exc)}); "
                f"retrying in {wait_seconds}s...",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(wait_seconds)

    raise RuntimeError(
        f"Could not fetch tender page {page} after {MAX_RETRIES} attempts: {sanitize_error(last_error)}"
    )


def get_page_count(payload: dict[str, Any], rows: int) -> tuple[int, int | None]:
    reported_pages = payload.get("total")
    reported_records = payload.get("records")

    try:
        total_pages = int(reported_pages)
    except (TypeError, ValueError):
        total_pages = 0

    try:
        total_records = int(reported_records)
    except (TypeError, ValueError):
        total_records = None

    if total_pages <= 0 and total_records is not None:
        total_pages = math.ceil(total_records / rows) if total_records else 1
    if total_pages <= 0:
        raise RuntimeError(
            "The first tender response did not report a valid total page count "
            "or total record count; refusing to guess how many pages to fetch."
        )
    return total_pages, total_records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch all public Setad tender listing pages into raw JSON snapshots."
    )
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument(
        "--end-page",
        type=int,
        default=None,
        help="Optional last page. When omitted, the total is discovered from page 1.",
    )
    parser.add_argument("--rows", type=int, default=30)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--landing-url", default=None)
    args = parser.parse_args()

    if args.start_page < 1:
        parser.error("start-page must be >= 1.")
    if args.end_page is not None and args.end_page < args.start_page:
        parser.error("end-page must be >= start-page.")
    if args.rows < 1 or args.delay < 0:
        parser.error("rows must be positive and delay cannot be negative.")
    return args


def write_run_summary(
    summary_path: Path,
    run_timestamp: str,
    start_page: int,
    end_page: int | None,
    rows: int,
    total_pages_reported: int | None,
    total_records_reported: int | None,
    total_rows_saved: int,
    pages: list[dict[str, Any]],
    status: str,
    error: str | None = None,
) -> None:
    summary = {
        "started_at_local": run_timestamp,
        "requested_page_range": [start_page, end_page],
        "rows_per_page": rows,
        "total_pages_reported": total_pages_reported,
        "total_records_reported": total_records_reported,
        "total_rows_saved": total_rows_saved,
        "status": status,
        "error": error,
        "pages": pages,
        "note": (
            "Raw tender response pages are preserved unchanged. "
            "Jalali date strings are not converted."
        ),
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = RAW_DIR / f"tender_run_{run_timestamp}.json"
    page_summaries: list[dict[str, Any]] = []
    total_rows_saved = 0
    total_pages_reported: int | None = None
    total_records_reported: int | None = None
    target_end_page: int | None = args.end_page

    emit_progress(
        phase="collecting",
        current_page=0,
        total_pages=target_end_page,
        pages_completed=0,
        records_fetched=0,
        records_total=None,
        progress_percent=0,
        message="در حال دریافت اطلاعات اولیه و شناسایی تعداد صفحات مناقصه‌ها...",
    )

    try:
        session, token, landing_url = create_session(args.landing_url)
        page = args.start_page
        while target_end_page is None or page <= target_end_page:
            payload, token = fetch_page(
                session,
                token,
                page=page,
                rows=args.rows,
                landing_url=landing_url,
            )

            if page == args.start_page:
                total_pages_reported, total_records_reported = get_page_count(payload, args.rows)
                target_end_page = min(args.end_page, total_pages_reported) if args.end_page else total_pages_reported
                if target_end_page < args.start_page:
                    raise RuntimeError("The requested start page is beyond the last available tender page.")

            items = payload["gridModel"]
            output_path = RAW_DIR / f"tender_page_{page}_{run_timestamp}.json"
            output_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            total_rows_saved += len(items)
            page_summaries.append(
                {
                    "requested_page": page,
                    "reported_page": payload.get("page"),
                    "rows_returned": len(items),
                    "records_reported": payload.get("records"),
                    "total_pages_reported": payload.get("total"),
                    "file": str(output_path.relative_to(PROJECT_ROOT)),
                }
            )

            pages_completed = len(page_summaries)
            total_pages_to_fetch = target_end_page - args.start_page + 1
            percent = int(85 * pages_completed / total_pages_to_fetch)
            emit_progress(
                phase="collecting",
                current_page=page,
                total_pages=target_end_page,
                pages_completed=pages_completed,
                records_fetched=total_rows_saved,
                records_total=total_records_reported,
                progress_percent=percent,
                message=f"صفحه {page} از {target_end_page} دریافت شد.",
            )
            print(
                f"Tender page {page}: {len(items)} rows | "
                f"reported total: {total_records_reported} records / "
                f"{total_pages_reported} pages | saved: {output_path.name}",
                flush=True,
            )

            if page < target_end_page and args.delay:
                time.sleep(args.delay)
            page += 1

        write_run_summary(
            summary_path,
            run_timestamp,
            args.start_page,
            target_end_page,
            args.rows,
            total_pages_reported,
            total_records_reported,
            total_rows_saved,
            page_summaries,
            "completed",
        )
        print(f"TENDER FETCH SUCCESS: {total_rows_saved} rows across {len(page_summaries)} pages.", flush=True)
        return 0

    except Exception as exc:
        write_run_summary(
            summary_path,
            run_timestamp,
            args.start_page,
            target_end_page,
            args.rows,
            total_pages_reported,
            total_records_reported,
            total_rows_saved,
            page_summaries,
            "failed",
            sanitize_error(exc),
        )
        print(f"TENDER FETCH FAILED: {sanitize_error(exc)}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
