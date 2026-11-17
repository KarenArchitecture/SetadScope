from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


BASE_URL = "https://eauc.setadiran.ir"
LANDING_URL = f"{BASE_URL}/eauc/welcome.action?gateway=setad"
ENDPOINT = f"{BASE_URL}/eauc/mainEstate-Load.action"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
MAX_RETRIES = 3


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "SetadScope/0.1 (public listing research)",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        }
    )
    landing = session.get(LANDING_URL, timeout=(15, 45))
    landing.raise_for_status()
    return session


def fetch_page(
    session: requests.Session, page: int = 0, rows: int = 30
) -> dict[str, Any]:
    """Fetch one public main-estate listing page using an existing session."""
    now_ms = int(time.time() * 1000)
    params = {
        "_search": "false",
        "nd": now_ms,
        "rows": rows,
        "page": page,
        "sidx": "",
        "sord": "asc",
        "_": now_ms,
    }

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(ENDPOINT, params=params, timeout=(15, 60))
            response.raise_for_status()
            payload = response.json()

            if not isinstance(payload, dict) or not isinstance(payload.get("gridModel"), list):
                raise RuntimeError("JSON response does not contain the expected 'gridModel' array.")
            return payload
        except (requests.RequestException, requests.exceptions.JSONDecodeError, RuntimeError) as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                break
            wait_seconds = attempt * 2
            print(
                f"Page {page}: attempt {attempt} failed ({exc}); retrying in {wait_seconds}s...",
                file=sys.stderr,
            )
            time.sleep(wait_seconds)

    raise RuntimeError(f"Could not fetch page {page} after {MAX_RETRIES} attempts: {last_error}")


def get_record_details(record: dict[str, Any]) -> dict[str, Any]:
    """Read the known nested auctionParty schema without assuming all fields exist."""
    party = record.get("auctionParty") or {}
    auction = party.get("auction") or {}
    auctioneer = auction.get("auctioneer") or {}
    visit_city = party.get("visitCity") or {}
    province = (visit_city.get("province") or {}).get("name")

    return {
        "title": auction.get("title") or party.get("title") or record.get("title"),
        "auction_id": auction.get("id"),
        "auction_no": auction.get("auctionNo"),
        "auction_reference_no": auction.get("auctionReferenceNo"),
        "organization": auctioneer.get("name"),
        "province": province,
        "city": visit_city.get("name"),
        "party_id": party.get("id"),
        "party_no": party.get("partyNo"),
        "base_total_price": party.get("baseTotalPrice"),
        "trust_amount": party.get("trustAmount"),
        "state": auction.get("state") or party.get("state"),
        "proposal_start": auction.get("fromProposalDate"),
        "proposal_deadline": auction.get("toProposalDate"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Setad main-estate listing pages.")
    parser.add_argument("--start-page", type=int, default=0, help="First zero-based page (default: 0).")
    parser.add_argument("--end-page", type=int, default=2, help="Last zero-based page, inclusive (default: 2).")
    parser.add_argument("--rows", type=int, default=30, help="Rows per page (default: 30).")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between page requests in seconds (default: 2).")
    args = parser.parse_args()

    if args.start_page < 0 or args.end_page < args.start_page:
        parser.error("Page range must be non-negative and end-page must be >= start-page.")
    if args.rows < 1 or args.delay < 0:
        parser.error("Rows must be positive and delay cannot be negative.")
    return args


def main() -> int:
    args = parse_args()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    seen_keys: set[str] = set()
    total_rows_saved = 0
    page_summaries: list[dict[str, Any]] = []

    try:
        session = create_session()
        for page in range(args.start_page, args.end_page + 1):
            payload = fetch_page(session, page=page, rows=args.rows)
            items = payload["gridModel"]

            output_path = RAW_DIR / f"main_estate_page_{page}_{run_timestamp}.json"
            output_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            page_keys: list[str] = []
            for item in items:
                details = get_record_details(item)
                key = details.get("party_id") or details.get("party_no") or details.get("auction_no")
                if key is not None:
                    page_keys.append(str(key))

            new_keys = [key for key in page_keys if key not in seen_keys]
            duplicate_count = len(page_keys) - len(set(page_keys)) + len(page_keys) - len(new_keys)
            seen_keys.update(page_keys)
            total_rows_saved += len(items)

            summary = {
                "requested_page": page,
                "reported_page": payload.get("page"),
                "rows_returned": len(items),
                "records_reported": payload.get("records"),
                "total_pages_reported": payload.get("total"),
                "duplicate_keys_seen": duplicate_count,
                "file": str(output_path.relative_to(PROJECT_ROOT)),
            }
            page_summaries.append(summary)

            print(
                f"Page {page}: {len(items)} rows | "
                f"reported total: {payload.get('records')} records / {payload.get('total')} pages | "
                f"saved: {output_path.name}"
            )
            if page < args.end_page:
                time.sleep(args.delay)

    except (requests.RequestException, RuntimeError) as exc:
        print(f"FETCH FAILED: {exc}", file=sys.stderr)
        print(f"Completed pages before failure: {len(page_summaries)}", file=sys.stderr)
        return 1

    summary_path = RAW_DIR / f"main_estate_run_{run_timestamp}.json"
    run_summary = {
        "started_at_local": run_timestamp,
        "requested_page_range": [args.start_page, args.end_page],
        "rows_per_page": args.rows,
        "total_rows_saved": total_rows_saved,
        "unique_record_keys_across_run": len(seen_keys),
        "pages": page_summaries,
        "note": "Raw page responses are preserved unchanged. Counts and keys are preliminary diagnostics.",
    }
    summary_path.write_text(
        json.dumps(run_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\nFETCH RUN SUCCESS")
    print(f"Pages fetched: {len(page_summaries)}")
    print(f"Rows saved: {total_rows_saved}")
    print(f"Unique record keys: {len(seen_keys)}")
    print(f"Run summary: {summary_path.relative_to(PROJECT_ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
