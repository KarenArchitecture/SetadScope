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


def test_legacy_keyword_matched_auction_survives_0005_migration():
    with SessionLocal() as db:
        legacy = db.scalar(
            select(Auction).where(
                Auction.source == "setad_main_estate",
                Auction.source_party_id == "pre-migration-fixture",
            )
        )
        assert legacy is not None, "Legacy row inserted before 0005 migration was lost"
        assert legacy.category == "movable"
        assert legacy.has_keyword_match is True
        assert legacy.matched_keywords == ["چوب"]
        assert legacy.raw_payload == {"marker": "pre-migration"}
        assert legacy.first_seen_at is not None


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



def test_saved_keyword_settings_affect_next_auction_import(tmp_path):
    from app.db.models import AppSetting
    from app.services.keyword_settings import SETTING_KEY

    client = TestClient(app)
    with SessionLocal() as db:
        existing = db.get(AppSetting, SETTING_KEY)
        previous = existing.value.copy() if existing else None

    try:
        original = client.get("/api/settings/keywords")
        assert original.status_code == 200
        assert original.json()["keywords"]

        invalid = client.put("/api/settings/keywords", json={"keywords": ["چوب", "چوب"]})
        assert invalid.status_code == 422

        saved = client.put("/api/settings/keywords", json={"keywords": ["آلومینیوم"]})
        assert saved.status_code == 200, saved.text
        assert client.get("/api/settings/keywords").json()["keywords"] == ["آلومینیوم"]

        raw = {
            "auctionParty": {
                "id": 73000099,
                "title": "فروش آلومینیوم",
                "baseTotalPrice": 2500,
                "auction": {"id": 81999, "auctionNo": 119999, "title": "فروش آلومینیوم"},
            },
        }
        path = tmp_path / "custom-keywords.json"
        path.write_text(json.dumps({"gridModel": [raw]}, ensure_ascii=False), encoding="utf-8")
        with SessionLocal() as db:
            result = import_auction_pages(db, [path], "movable")
            assert result["matched"] == 1
            row = db.scalar(select(Auction).where(Auction.source_party_id == "73000099"))
            assert row is not None
            assert row.matched_keywords == ["آلومینیوم"]
    finally:
        with SessionLocal() as db:
            db.execute(delete(Auction).where(Auction.source_party_id == "73000099"))
            setting = db.get(AppSetting, SETTING_KEY)
            if previous is None:
                if setting is not None:
                    db.delete(setting)
            elif setting is not None:
                setting.value = previous
            db.commit()
