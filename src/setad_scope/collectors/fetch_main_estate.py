from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests


BASE_URL = "https://eauc.setadiran.ir"
LANDING_URL = f"{BASE_URL}/eauc/welcome.action?gateway=setad"
ENDPOINT = f"{BASE_URL}/eauc/mainEstate-Load.action"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "raw"


def fetch_page(page: int = 0, rows: int = 30) -> dict:
    """Fetch one public main-estate listing page and return its JSON response."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "SetadScope/0.1 (public listing research)",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        }
    )

    # Establish a normal site session before requesting the listing endpoint.
    landing = session.get(LANDING_URL, timeout=30)
    landing.raise_for_status()

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

    response = session.get(ENDPOINT, params=params, timeout=45)
    response.raise_for_status()

    try:
        payload = response.json()
    except requests.exceptions.JSONDecodeError as exc:
        preview = response.text[:500].replace("\n", " ")
        raise RuntimeError(
            f"Endpoint did not return valid JSON. "
            f"Content-Type={response.headers.get('Content-Type')!r}; "
            f"body preview={preview!r}"
        ) from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("gridModel"), list):
        raise RuntimeError("JSON response does not contain the expected 'gridModel' array.")

    return payload


def main() -> int:
    page = 0
    rows = 30

    try:
        payload = fetch_page(page=page, rows=rows)
    except (requests.RequestException, RuntimeError) as exc:
        print(f"FETCH FAILED: {exc}", file=sys.stderr)
        return 1

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = RAW_DIR / f"main_estate_page_{page}_{timestamp}.json"
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    records = payload.get("records")
    total_pages = payload.get("total")
    items = payload["gridModel"]

    print("FETCH SUCCESS")
    print(f"Saved: {output_path.relative_to(PROJECT_ROOT)}")
    print(f"Page requested: {page}; page reported by server: {payload.get('page')}")
    print(f"Rows returned: {len(items)}")
    print(f"Total records reported: {records}")
    print(f"Total pages reported: {total_pages}")

    if items:
        first = items[0]
        auction = first.get("auction") or first.get("immovableAuction") or {}
        auctioneer = auction.get("auctioneer") or {}
        print("\nFirst record preview:")
        print(f"  Auction title: {auction.get('title')}")
        print(f"  Auction number: {auction.get('auctionNo')}")
        print(f"  Organization: {auctioneer.get('name')}")
        print(f"  Address: {first.get('address')}")
        print(f"  Base price field: {first.get('organizationBasePrice')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
