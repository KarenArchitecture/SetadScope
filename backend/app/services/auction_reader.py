from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "raw"


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    """Map a raw Setad auction-party record to a stable API response shape."""
    party = record.get("auctionParty") or {}
    auction = party.get("auction") or {}
    auctioneer = auction.get("auctioneer") or {}
    visit_city = party.get("visitCity") or {}
    province = (visit_city.get("province") or {}).get("name")

    return {
        "id": party.get("id"),
        "auction_id": auction.get("id"),
        "auction_no": auction.get("auctionNo"),
        "auction_reference_no": auction.get("auctionReferenceNo"),
        "title": auction.get("title") or party.get("title") or record.get("title"),
        "organization": auctioneer.get("name"),
        "province": province,
        "city": visit_city.get("name"),
        "base_total_price": party.get("baseTotalPrice"),
        "trust_amount": party.get("trustAmount"),
        "state": auction.get("state") or party.get("state"),
        "proposal_start": auction.get("fromProposalDate"),
        "proposal_deadline": auction.get("toProposalDate"),
    }


def load_auctions() -> list[dict[str, Any]]:
    """Load saved raw pages and deduplicate listing rows by auctionParty.id."""
    if not RAW_DIR.exists():
        return []

    records_by_id: dict[int, dict[str, Any]] = {}
    files = sorted(RAW_DIR.glob("main_estate_page_*.json"))

    for file_path in files:
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        for raw_record in payload.get("gridModel", []):
            normalized = normalize_record(raw_record)
            record_id = normalized.get("id")
            if record_id is not None:
                # Later snapshots replace earlier versions of the same listing row.
                records_by_id[int(record_id)] = normalized

    return list(records_by_id.values())
