"""PostgreSQL integration: Alembic schema, per-category upsert and HTTP API.

CI starts postgres:17 and sets SETADSCOPE_TEST_POSTGRES=1; local pytest skips.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

if os.getenv("SETADSCOPE_TEST_POSTGRES") != "1":
    pytest.skip("Requires dedicated ephemeral PostgreSQL", allow_module_level=True)

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from app.db.models import Auction
from app.db.session import SessionLocal
from app.main import app
from app.services.auction_ingestion import SOURCES, import_auction_pages

ROWS = {
    "movable": {
        "auctionParty": {
            "id": 73000001,
            "title": "فروش چوب درخت",
            "baseTotalPrice": 4000,
            "visitCity": {"name": "گرگان", "province": {"name": "گلستان"}},
            "auction": {
                "id": 81001, "auctionNo": 1105001,
                "title": "فروش چوب درخت",
                "toProposalDate": "1405/09/18 13:00:00",
                "auctioneer": {"name": "سازمان آزمایشی"},
            },
        }
    },
    "immovable": {
        "id": 73000002, "organizationBasePrice": 700000,
        "city": {"name": "ری", "province": {"name": "تهران"}},
        "auction": {
            "id": 81002, "auctionNo": 2205001, "title": "فروش ملک آزمایشی",
            "toProposalDate": "1405/09/19 14:00:00",
            "auctioneer": {"name": "سازمان آزمایشی"},
        },
    },
    "rental": {
        "id": 73000003, "rentBasePrice": 10000,
        "rentMonthDuration": 12, "title": "مغازه مورد اجاره",
        "rentalItemNo": 5105095363000018,
        "auction": {
            "id": 81003, "auctionNo": 3305001, "title": "اجاره سه مغازه",
            "toProposalDate": "1405/09/26 19:00:00",
            "auctioneer": {"name": "سازمان آزمایشی"},
        },
    },
    "minor": {
        "id": 73000004, "auctionNo": 4405001,
        "title": "اموال مازاد آزمایشی", "totalBasePrice": 1100,
        "auctioneer": {"name": "سازمان آزمایشی"},
        "toProposalDate": "1405/09/01 13:00:00",
    },
    "clearance": {
        "cartId": 73000005, "tableId": 9500, "number": 3105001053005896,
        "title": "حراج کتری برقی", "basePrice": 9000000,
        "orgName": "سازمان جمع آوری و فروش اموال تملیکی",
        "provinceName": "کرمان", "cityName": "کرمان",
        "jalaliSendDeadlineDate": "1405/09/01 - 19:00",
        "jalaliFromProposalDate": "1405/09/01 - 08:00",
    },
}


def test_all_category_imports_idempotence_and_http_filters(tmp_path):
    with SessionLocal() as db:
        try:
            for category, row in ROWS.items():
                path = tmp_path / f"{category}.json"
                body = {"content" if category == "clearance" else "gridModel": [row]}
                path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
                first = import_auction_pages(db, [path], category)
                second = import_auction_pages(db, [path], category)
                assert first["stored"] == 1 and second["stored"] == 1

                db_rows = db.scalars(
                    select(Auction).where(Auction.source == SOURCES[category])
                ).all()
                matching = [record for record in db_rows if record.source_party_id == str(
                    73000005 if category == "clearance" else
                    row.get("id", row.get("auctionParty", {}).get("id"))
                )]
                assert len(matching) == 1
                assert matching[0].category == category
                assert matching[0].raw_payload == row

            client = TestClient(app)
            for category in ROWS:
                response = client.get(
                    "/api/auctions",
                    params={"category": category, "matched_only": "false", "page_size": 100},
                )
                assert response.status_code == 200, response.text
                body = response.json()
                assert body["total"] >= 1
                assert all(item["category"] == category for item in body["items"])

                workbook = client.get(
                    "/api/auctions/export.xlsx",
                    params={"category": category, "matched_only": "false"},
                )
                assert workbook.status_code == 200, workbook.text
                assert workbook.content.startswith(b"PK")

            matched = client.get("/api/auctions", params={"category": "movable"})
            assert matched.status_code == 200
            assert any(x["source_party_id"] == "73000001" for x in matched.json()["items"])
            excluded = client.get("/api/auctions", params={"category": "clearance"})
            assert excluded.status_code == 200
            assert all(x["source_party_id"] != "73000005" for x in excluded.json()["items"])

            detail_row = db.scalar(select(Auction).where(Auction.source_party_id == "73000005"))
            details = client.get(f"/api/auctions/{detail_row.id}")
            assert details.status_code == 200
            assert details.json()["raw_payload"] == ROWS["clearance"]
        finally:
            db.execute(delete(Auction).where(Auction.source.in_(list(SOURCES.values()))))
            db.commit()
