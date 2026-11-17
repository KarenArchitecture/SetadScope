from __future__ import annotations

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


def fetch_page(page: int = 0, rows: int = 30) -> dict[str, Any]:
    """Fetch one public main-estate listing page and return its JSON response."""
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

    response = session.get(ENDPOINT, params=params, timeout=(15, 60))
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

    items = payload["gridModel"]
    print("FETCH SUCCESS")
    print(f"Saved: {output_path.relative_to(PROJECT_ROOT)}")
    print(f"Page requested: {page}; page reported by server: {payload.get('page')}")
    print(f"Rows returned: {len(items)}")
    print(f"Total records reported: {payload.get('records')}")
    print(f"Total pages reported: {payload.get('total')}")

    if items:
        print("\nFirst record preview (mapped fields):")
        print(json.dumps(get_record_details(items[0]), ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
