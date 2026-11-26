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
from app.db.models import Auction, IngestionRun
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
        "orgName": "اداره کل منابع طبیعی",
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
        assert legacy.collection_group == "executive_agencies"
        assert legacy.has_keyword_match is True
        assert legacy.matched_keywords == ["چوب"]
        assert legacy.raw_payload == {"marker": "pre-migration"}
        assert legacy.first_seen_at is not None


def test_legacy_clearance_source_is_restored_to_amval_scope():
    with SessionLocal() as db:
        legacy = db.scalar(
            select(Auction).where(
                Auction.source == "setad_clearance_amval_tamliki",
                Auction.source_party_id == "pre-migration-clearance",
            )
        )
        assert legacy is not None, "Legacy Amval Tamliki clearance row was lost"
        assert legacy.category == "clearance"
        assert legacy.collection_group == "amval_tamliki"


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
                assert first["changed"] == 1 and first["unchanged"] == 0
                assert second["changed"] == 0 and second["unchanged"] == 1

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

                collection_group = "executive_agencies"
                collection_status = client.get(f"/api/collection/auctions/{category}/status")
                assert collection_status.status_code == 200
                assert collection_status.json()["collection_group"] == collection_group
                with SessionLocal() as history_db:
                    expected_update = history_db.scalar(
                        select(IngestionRun.finished_at)
                        .where(
                            IngestionRun.kind == "auctions",
                            IngestionRun.collection_group == collection_group,
                            IngestionRun.category == category,
                            IngestionRun.status == "success",
                        )
                        .order_by(IngestionRun.finished_at.desc())
                        .limit(1)
                    )
                assert expected_update is not None
                assert collection_status.json()["last_updated_at"] == expected_update.isoformat()

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



def test_same_source_identity_is_isolated_between_collection_groups(tmp_path):
    from io import BytesIO
    from openpyxl import load_workbook

    source_id = "73120001"
    raw = {
        "auctionParty": {
            "id": int(source_id),
            "title": "فروش چوب آزمایشی برای تفکیک مجموعه",
            "baseTotalPrice": 125000,
            "auction": {
                "id": 819991,
                "auctionNo": "GROUP-A-991",
                "title": "فروش چوب آزمایشی برای تفکیک مجموعه",
                "toProposalDate": "1405/10/10 13:00:00",
                "auctioneer": {"name": "سازمان آزمایشی"},
            },
        }
    }
    path = tmp_path / "same-source-id.json"
    path.write_text(json.dumps({"gridModel": [raw]}, ensure_ascii=False), encoding="utf-8")

    with SessionLocal() as db:
        try:
            for group in ("executive_agencies", "amval_tamliki"):
                first = import_auction_pages(db, [path], "movable", collection_group=group)
                second = import_auction_pages(db, [path], "movable", collection_group=group)
                assert first["stored"] == 1 and second["stored"] == 1

            rows = db.scalars(
                select(Auction).where(
                    Auction.source == SOURCES["movable"],
                    Auction.source_party_id == source_id,
                )
            ).all()
            assert {row.collection_group for row in rows} == {
                "executive_agencies", "amval_tamliki",
            }
            assert len(rows) == 2

            client = TestClient(app)
            amval_list = client.get(
                "/api/auctions",
                params={
                    "category": "movable",
                    "collection_group": "amval_tamliki",
                    "matched_only": "false",
                    "search": "GROUP-A-991",
                },
            )
            assert amval_list.status_code == 200, amval_list.text
            assert amval_list.json()["total"] == 1
            assert amval_list.json()["items"][0]["collection_group"] == "amval_tamliki"

            global_search = client.get(
                "/api/search",
                params={
                    "kind": "auction",
                    "collection_group": "amval_tamliki",
                    "matched_only": "false",
                    "search": "GROUP-A-991",
                },
            )
            assert global_search.status_code == 200, global_search.text
            assert global_search.json()["total"] == 1
            assert global_search.json()["items"][0]["collection_group"] == "amval_tamliki"

            invalid_group_filter = client.get(
                "/api/auctions",
                params={"category": "clearance", "collection_group": "shared"},
            )
            assert invalid_group_filter.status_code == 422
            invalid_search_filter = client.get(
                "/api/search",
                params={
                    "kind": "auction",
                    "category": "clearance",
                    "collection_group": "shared",
                },
            )
            assert invalid_search_filter.status_code == 422

            history = client.get(
                "/api/collection/auctions/history",
                params={"collection_group": "amval_tamliki", "category": "movable"},
            )
            assert history.status_code == 200
            assert history.json()["items"]
            assert all(item["collection_group"] == "amval_tamliki" for item in history.json()["items"])

            export = client.get(
                "/api/auctions/export.xlsx",
                params={
                    "category": "movable",
                    "collection_group": "amval_tamliki",
                    "matched_only": "false",
                    "search": "GROUP-A-991",
                },
            )
            assert export.status_code == 200
            sheet = load_workbook(BytesIO(export.content)).active
            headers = [cell.value for cell in sheet[1]]
            assert "مجموعه" in headers
            group_column = headers.index("مجموعه") + 1
            assert sheet.cell(row=2, column=group_column).value == "سازمان اموال تملیکی"
        finally:
            db.execute(delete(Auction).where(Auction.source_party_id == source_id))
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



def test_tender_relevance_filter_and_export_share_same_dataset(tmp_path):
    """Tender checkbox must filter database results and downloadable Excel alike."""
    from io import BytesIO

    from openpyxl import load_workbook
    from app.db.models import Tender
    from app.services.tender_ingestion import import_tender_pages

    rows = [
        {"id": 799901, "number": "T-799901", "title": "تامین چوب و نهال", "typeName": "عمومی"},
        {"id": 799902, "number": "T-799902", "title": "خرید رایانه اداری", "typeName": "عمومی"},
    ]
    raw = tmp_path / "tender-relevance.json"
    raw.write_text(json.dumps({"gridModel": rows}, ensure_ascii=False), encoding="utf-8")
    with SessionLocal() as db:
        try:
            result = import_tender_pages(db, [raw])
            assert result["stored"] == 2
            assert result["changed"] == 2 and result["unchanged"] == 0

            unchanged = import_tender_pages(db, [raw])
            assert unchanged["stored"] == 2
            assert unchanged["changed"] == 0 and unchanged["unchanged"] == 2

            client = TestClient(app)
            collection_status = client.get("/api/collection/tenders/status")
            assert collection_status.status_code == 200
            expected_update = db.scalar(
                select(IngestionRun.finished_at)
                .where(
                    IngestionRun.kind == "tenders",
                    IngestionRun.category.is_(None),
                    IngestionRun.status == "success",
                )
                .order_by(IngestionRun.finished_at.desc())
                .limit(1)
            )
            assert expected_update is not None
            assert collection_status.json()["last_updated_at"] == expected_update.isoformat()

            matched = client.get("/api/tenders", params={"matched_only": "true", "search": "T-7999"})
            assert matched.status_code == 200, matched.text
            source_ids = {r["source_tender_id"] for r in matched.json()["items"]}
            assert source_ids == {"799901"}
            assert matched.json()["items"][0]["matched_keywords"]

            unfiltered = client.get("/api/tenders", params={"matched_only": "false", "search": "T-7999"})
            assert unfiltered.status_code == 200
            assert {r["source_tender_id"] for r in unfiltered.json()["items"]} == {"799901", "799902"}

            export = client.get("/api/tenders/export.xlsx", params={"matched_only": "true", "search": "T-7999"})
            assert export.status_code == 200
            sheet = load_workbook(BytesIO(export.content)).active
            assert sheet.max_row == 2
            assert sheet["B2"].value == "T-799901"
        finally:
            db.execute(delete(Tender).where(Tender.source_tender_id.in_(["799901", "799902"])))
            db.commit()



def test_legacy_tender_relevance_is_backfilled_during_0007_migration():
    from app.db.models import Tender

    with SessionLocal() as db:
        tender = db.scalar(
            select(Tender).where(Tender.source_tender_id == "pre-0007-tender")
        )
        assert tender is not None, "Legacy tender fixture was lost during migration"
        assert tender.has_keyword_match is True
        assert "چوب" in tender.matched_keywords
        assert tender.raw_payload == {"marker": "pre-tender-keyword-migration"}



def test_global_search_combines_auctions_and_tenders_with_server_side_filters(tmp_path):
    from app.db.models import Tender
    from app.services.tender_ingestion import import_tender_pages

    auction_source_id = "73110991"
    tender_source_id = "79980991"
    auction_record = {
        "auctionParty": {
            "id": int(auction_source_id),
            "title": "فروش چوب جنگلی برای آزمون جست‌وجوی سراسری",
            "baseTotalPrice": 125000,
            "visitCity": {"name": "ساری", "province": {"name": "مازندران"}},
            "auction": {
                "id": 819991,
                "auctionNo": "GS-A-991",
                "title": "فروش چوب جنگلی برای آزمون جست‌وجوی سراسری",
                "fromSiteShowDate": "1405/09/02 10:00:00",
                "toProposalDate": "1405/10/10 13:00:00",
                "auctioneer": {"name": "سازمان آزمایشی جست‌وجوی سراسری"},
            },
        }
    }
    tender_record = {
        "id": int(tender_source_id),
        "number": "GS-T-991",
        "title": "تأمین چوب جنگلی برای آزمون جست‌وجوی سراسری",
        "typeName": "مناقصه عمومی",
        "organization": "سازمان آزمایشی جست‌وجوی سراسری",
        "operationProvinceName": "مازندران",
        "operationCityName": "ساری",
        "publicNotificationDate": "1405/09/03 09:00:00",
        "proposalDeadlineDate": "1405/10/12 12:00:00",
    }

    auction_path = tmp_path / "global-search-auction.json"
    auction_path.write_text(
        json.dumps({"gridModel": [auction_record]}, ensure_ascii=False),
        encoding="utf-8",
    )
    tender_path = tmp_path / "global-search-tender.json"
    tender_path.write_text(
        json.dumps({"gridModel": [tender_record]}, ensure_ascii=False),
        encoding="utf-8",
    )

    with SessionLocal() as db:
        try:
            assert import_auction_pages(db, [auction_path], "movable")["stored"] == 1
            assert import_tender_pages(db, [tender_path])["stored"] == 1

            client = TestClient(app)
            response = client.get(
                "/api/search",
                params={"search": "چوب جنگلی برای آزمون جست‌وجوی سراسری", "page_size": 100},
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["total"] == 2
            assert body["summary"] == {"all": 2, "auctions": 1, "tenders": 1}
            assert {item["record_type"] for item in body["items"]} == {"auction", "tender"}
            assert len({item["row_key"] for item in body["items"]}) == 2
            assert all(item["source_label"] for item in body["items"])

            auctions = client.get(
                "/api/search",
                params={"search": "چوب جنگلی برای آزمون جست‌وجوی سراسری", "kind": "auction"},
            )
            assert auctions.status_code == 200
            assert auctions.json()["total"] == 1
            assert all(item["record_type"] == "auction" for item in auctions.json()["items"])
            assert auctions.json()["summary"]["tenders"] == 1

            categorized = client.get(
                "/api/search",
                params={
                    "search": "چوب جنگلی برای آزمون جست‌وجوی سراسری",
                    "kind": "auction",
                    "category": "movable",
                },
            )
            assert categorized.status_code == 200
            assert categorized.json()["total"] == 1
            assert categorized.json()["summary"]["tenders"] == 1

            tenders = client.get(
                "/api/search",
                params={"search": "چوب جنگلی برای آزمون جست‌وجوی سراسری", "source": "setad_tender"},
            )
            assert tenders.status_code == 200
            assert tenders.json()["total"] == 1
            assert tenders.json()["items"][0]["record_type"] == "tender"

            matched = client.get(
                "/api/search",
                params={"search": "چوب جنگلی برای آزمون جست‌وجوی سراسری", "matched_only": "true"},
            )
            assert matched.status_code == 200
            assert matched.json()["total"] == 2

            paged = client.get(
                "/api/search",
                params={"search": "چوب جنگلی برای آزمون جست‌وجوی سراسری", "page": 2, "page_size": 1},
            )
            assert paged.status_code == 200
            assert paged.json()["total"] == 2
            assert len(paged.json()["items"]) == 1
            assert paged.json()["pages"] == 2
        finally:
            db.execute(
                delete(Auction).where(Auction.source_party_id == auction_source_id)
            )
            db.execute(
                delete(Tender).where(Tender.source_tender_id == tender_source_id)
            )
            db.commit()


def test_combined_auction_selection_and_today_filter_match_excel(monkeypatch):
    from datetime import datetime, timedelta
    from io import BytesIO
    from uuid import uuid4

    from openpyxl import load_workbook

    from app.services import listing_filters
    from app.services.date_normalization import TEHRAN

    midnight = datetime(2026, 11, 24, tzinfo=TEHRAN)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return (midnight + timedelta(hours=1)).astimezone(tz)

    monkeypatch.setattr(listing_filters, "datetime", FixedDateTime)
    fixtures = [
        ("movable", "executive_agencies", midnight),
        ("immovable", "executive_agencies", midnight - timedelta(microseconds=1)),
        ("rental", "executive_agencies", midnight + timedelta(days=1)),
        ("clearance", "executive_agencies", midnight + timedelta(hours=4))
        ("movable", "amval_tamliki", midnight),
    ]
    ids = [f"uiux-selection-{index}" for index in range(len(fixtures))]
    with SessionLocal() as db, TestClient(app) as client:
        try:
            db.add_all(
                Auction(
                    source_party_id=source_id, category=category, collection_group=group,
                    title=source_id, publish_start_at=published, raw_payload={},
                )
                for source_id, (category, group, published) in zip(ids, fixtures)
            )
            db.commit()
            params = {"search": "uiux-selection", "matched_only": False, "category": "all"}
            combined = client.get("/api/auctions", params=params)
            assert combined.status_code == 200, combined.text
            assert combined.json()["total"] == 5

            params.update(
                categories=["movable", "clearance"], collection_group="executive_agencies", today_only=True,
            )
            page = client.get("/api/auctions", params=params)
            assert page.status_code == 200, page.text
            assert {item["source_party_id"] for item in page.json()["items"]} == {ids[0], ids[3]}

            export_id = uuid4().hex
            workbook = client.get("/api/auctions/export.xlsx", params={**params, "export_id": export_id})
            assert workbook.status_code == 200, workbook.text
            sheet = load_workbook(BytesIO(workbook.content)).active
            assert {cell.value for cell in sheet["A"][1:]} == {ids[0], ids[3]}
            assert client.get(f"/api/excel/progress/{export_id}").json() is None

            params["collection_group"] = "all"
            params.pop("categories")
            page = client.get("/api/auctions", params=params)
            assert {item["source_party_id"] for item in page.json()["items"]} == {ids[0], ids[3], ids[4]}
        finally:
            db.rollback()
            db.execute(delete(Auction).where(Auction.source_party_id.in_(ids)))
            db.commit()


def test_global_advanced_tender_filters_match_excel():
    from datetime import datetime
    from io import BytesIO

    from openpyxl import load_workbook

    from app.db.models import Tender
    from app.services.date_normalization import TEHRAN

    notice = datetime(2026, 11, 24, 9, tzinfo=TEHRAN)
    ids = ["uiux-tender-1", "uiux-tender-2"]
    with SessionLocal() as db, TestClient(app) as client:
        try:
            db.add_all(
                Tender(
                    source_tender_id=source_id, title=source_id, city=city, province="تهران",
                    state="PUBLISHED", type_name="عمومی", public_notification_at=notice,
                    documents_deadline_at=notice, raw_payload={},
                )
                for source_id, city in zip(ids, ("ری", "تهران"))
            )
            db.commit()
            params = {
                "search": "uiux-tender", "province": "تهران", "city": "ری", "type_name": "عمومی",
                "state": "PUBLISHED", "announcement_from": "2026-11-24", "documents_deadline_to": "2026-11-24",
            }
            page = client.get("/api/search", params=params)
            assert page.status_code == 200, page.text
            assert [item["record_number"] for item in page.json()["items"]] == ids[:1]
            assert page.json()["summary"]["tenders"] == 1
            assert {"province": "تهران", "city": "ری"} in page.json()["filter_options"]["cities"]

            workbook = client.get("/api/search/export.xlsx", params=params)
            assert workbook.status_code == 200, workbook.text
            sheet = load_workbook(BytesIO(workbook.content)).active
            assert [cell.value for cell in sheet["F"][1:]] == ids[:1]
        finally:
            db.rollback()
            db.execute(delete(Tender).where(Tender.source_tender_id.in_(ids)))
            db.commit()


def test_partial_clearance_is_imported_without_marking_collection_successful(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from app import main

    payload = tmp_path / "clearance_page_0.json"
    payload.write_text(json.dumps({"content": [{"cartId": 73998881, "title": "Partial clearance"}]}))
    manifest = tmp_path / "clearance_partial_fixture.json"
    manifest.write_text(json.dumps({
        "category": "clearance",
        "collection_group": "executive_agencies",
        "complete_source": False,
        "pages": [{"file": payload.name}],
    }))
    monkeypatch.setattr("app.auction_category_jobs.category_raw_dir", lambda *_: tmp_path)
    monkeypatch.setattr(main.subprocess, "Popen", lambda *_, **__: SimpleNamespace(
        stdout=[
            'PROGRESS_JSON:{"pages_completed":1,"total_pages":10,"progress_percent":8}',
            "PARTIAL_MANIFEST:" + manifest.name,
            "FETCH FAILED: executive_agencies/clearance: HTTP 428",
        ],
        wait=lambda: 1,
    ))
    key = main.collection_state_key("executive_agencies", "clearance")
    monkeypatch.setitem(main.collection_states, key, main.initial_collection_state("auctions", "executive_agencies", "clearance"))

    with SessionLocal() as db:
        original_runs = set(db.scalars(select(IngestionRun.id)).all())
        try:
            main.run_collection_job("auctions", "executive_agencies", "clearance")
            state = main.collection_states[key]
            assert state["status"] == "failed"
            assert state["records_stored"] == 1
            assert state["progress_percent"] == 8
            assert "HTTP 428" in state["error"]
            assert db.scalar(select(Auction.id).where(Auction.source_party_id == "73998881"))
            run = db.scalar(select(IngestionRun).where(IngestionRun.id.not_in(original_runs)))
            assert run.status == "failed"
            assert run.stored == 1
        finally:
            db.execute(delete(Auction).where(Auction.source_party_id == "73998881"))
            db.execute(delete(IngestionRun).where(IngestionRun.id.not_in(original_runs)))
            db.commit()


def test_registered_listing_type_appears_in_search_and_excel(monkeypatch):
    from dataclasses import replace
    from io import BytesIO
    from openpyxl import load_workbook
    from sqlalchemy import literal
    from app.listing_types import LISTING_TYPES

    auction = LISTING_TYPES["auction"]

    def quote_rows():
        query = auction.project()
        _, *columns = query.selected_columns
        return query.with_only_columns(
            literal("quote").label("record_type"), *columns,
        ).where(Auction.source_party_id == "quote-fixture")

    monkeypatch.setitem(LISTING_TYPES, "quote", replace(
        auction, label="استعلام بها", count_key="quotes", project=quote_rows,
    ))
    with SessionLocal() as db, TestClient(app) as client:
        db.add(Auction(
            source="setad_main_estate", source_party_id="quote-fixture",
            collection_group="executive_agencies", category="movable",
            title="Sample quote", raw_payload={}, matched_keywords=[],
        ))
        db.commit()
        try:
            response = client.get("/api/search", params={"kind": "quote"})
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["summary"]["quotes"] == body["archive_summary"]["quotes"] == 1
            assert [item["record_type_label"] for item in body["items"]] == ["استعلام بها"]

            response = client.get("/api/search/export.xlsx", params={"kind": "quote"})
            assert response.status_code == 200, response.text
            rows = list(load_workbook(BytesIO(response.content)).active.values)
            assert [row[1] for row in rows[1:]] == ["استعلام بها"]
        finally:
            db.execute(delete(Auction).where(Auction.source_party_id == "quote-fixture"))
            db.commit()
