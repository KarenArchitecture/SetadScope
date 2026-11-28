"""Golden-shape tests based on public Setad auction response samples."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.services.auction_ingestion import project_auction
from setad_scope.collectors.fetch_auction_categories import (
    collect,
    page_totals,
    request_details,
)


def auction(title="فروش چوب صنوبر", auction_no=100500):
    return {
        "id": 51001,
        "auctionNo": auction_no,
        "title": title,
        "fromProposalDate": "1405/08/28 13:00:00",
        "toProposalDate": "1405/09/18 13:00:00",
        "fromSiteShowDate": "1405/08/28 13:00:00",
        "state": "PUBLISHED",
        "auctioneer": {"name": "اداره دولتی"},
    }


def city(name="ری", province="تهران"):
    return {"name": name, "province": {"name": province}}


def test_movable_preserves_nested_identity_and_all_raw_rows():
    raw = {
        "auctionParty": {
            "id": 1393501,
            "title": "فروش باتری ups",
            "baseTotalPrice": 1641500000,
            "visitCity": city("مراوه تپه", "گلستان"),
            "auction": auction("فروش باتری ups"),
        }
    }
    item, result = project_auction(raw, "movable")
    assert result == "unmatched"
    assert item["source"] == "setad_main_estate"
    assert item["source_party_id"] == "1393501"
    assert item["base_total_price"] == Decimal("1641500000")
    assert item["province"] == "گلستان"
    assert item["raw_payload"] is raw
    assert not item["has_keyword_match"]


def test_immovable_property_amount_and_location():
    raw = {
        "id": 1393581,
        "no": 2105003088000021,
        "city": city(),
        "address": "خیابان شهید رجایی",
        "type": {"name": "مغازه"},
        "organizationBasePrice": 48900000000,
        "auction": auction("فروش چوب درخت", 2005003088000018),
    }
    item, result = project_auction(raw, "immovable")
    assert result == "matched"
    assert item["source_party_id"] == "1393581"
    assert item["asset_type"] == "مغازه"
    assert item["item_reference_no"] == "2105003088000021"
    assert item["price_type"] == "property_sale_base"
    assert item["base_total_price"] == Decimal("48900000000")
    assert item["organization"] == "اداره دولتی"
    assert item["proposal_deadline"].isoformat().startswith("2026-12-09T13:00:00")


def test_rental_distinguishes_items_sharing_one_auction_number():
    base = {
        "auction": auction("اجاره 4 باب مغازه", 5005095363000005),
        "city": city("خرم آباد", "لرستان"),
        "title": "مغازه کانون هنر",
        "rentBasePrice": 1440000000,
        "rentMonthDuration": 12,
        "rentalItemNo": 5105095363000018,
    }
    first, _ = project_auction({**base, "id": 1393993}, "rental")
    second, _ = project_auction({**base, "id": 1393994}, "rental")
    assert first["auction_no"] == second["auction_no"]
    assert first["source_party_id"] != second["source_party_id"]
    assert first["item_title"] == "مغازه کانون هنر"
    assert first["rent_duration_months"] == 12
    assert first["base_total_price"] == Decimal("1440000000")
    assert first["price_type"] == "rental_base"


def test_minor_root_schema():
    raw = {
        "id": 540036,
        "auctionNo": 6005001365000008,
        "title": "اموال مازاد اداره کل پست",
        "auctioneer": {"name": "اداره کل پست"},
        "city": city("اردبیل", "اردبیل"),
        "fromSiteShowDate": "1405/08/27 12:00:00",
        "toProposalDate": "1405/09/01 13:00:00",
        "totalBasePrice": None,
    }
    row, result = project_auction(raw, "minor")
    assert result == "unmatched"
    assert row["source_party_id"] == "540036"
    assert row["auction_no"] == "6005001365000008"
    assert row["organization"] == "اداره کل پست"
    assert row["base_total_price"] is None
    assert row["proposal_deadline"] is not None


def test_clearance_cards_price_unit_and_jalali_deadline():
    raw = {
        "number": 3105001053005896,
        "cartId": 4577196,
        "tableId": 537644,
        "title": "حراج کتری برقی نام تجاری DEINI",
        "basePrice": 9000000,
        "orgName": "اداره کل منابع طبیعی",
        "provinceName": "کرمان",
        "cityName": "کرمان",
        "categoryName": "لوازم خانگی، صوتی و تصویری",
        "jalaliFromProposalDate": "1405/09/01 - 08:00",
        "jalaliSendDeadlineDate": "1405/09/01 - 19:00",
        "jalaliDocumentDeadlineDate": " - ",
    }
    row, status = project_auction(raw, "clearance")
    assert status == "unmatched"
    assert row["source_party_id"] == "4577196"
    assert row["collection_group"] == "executive_agencies"
    assert row["source"] == "setad_clearance_executive_agencies"
    assert row["auction_no"] == "3105001053005896"
    assert row["money_unit"] == "IRR"
    assert row["base_total_price"] == Decimal("9000000")
    assert row["document_deadline"] is None
    assert row["proposal_deadline"].hour == 19
    assert row["proposal_start"].hour == 8
    assert row["asset_type"] == "لوازم خانگی، صوتی و تصویری"


def test_endpoints_and_zero_based_pagination():
    cases = {
        "movable": "mainEstate-Load.action",
        "immovable": "mainImmovable-Load.action",
        "rental": "mainRental-Load.action",
        "minor": "mainMinor-Load.action",
        "clearance": "/api/centralboard/cards/",
    }
    for category, endpoint in cases.items():
        url, params = request_details(category, 0, 5)
        assert endpoint in url
        assert params["pageNumber" if category == "clearance" else "page"] == 0
        if category == "immovable":
            assert params["propertySearchCriteriaDto.auctionType"] == "NON_PROPERTY"
        if category == "clearance":
            assert params["tagCode"] == "341,343"
            assert params["notOrgId"] == "5315"
            assert "selectedOrganization" not in params
            assert params["boardCode"] == "3"


def test_pagination_totals_for_both_apis():
    assert page_totals({"total": 37, "records": 1095}, "movable", 30) == (37, 1095)
    assert page_totals({"totalPages": 44, "totalElements": 218}, "clearance", 5) == (44, 218)


def test_group_registry_keeps_clearance_sources_independent():
    from setad_scope.collectors.auction_sources.registry import (
        CATEGORIES_BY_GROUP,
        resolve_collection_group,
        source_for,
    )

    expected_categories = ("movable", "immovable", "rental", "minor", "clearance")
    assert CATEGORIES_BY_GROUP["executive_agencies"] == expected_categories
    assert CATEGORIES_BY_GROUP["amval_tamliki"] == expected_categories
    assert set(CATEGORIES_BY_GROUP) == {"executive_agencies", "amval_tamliki"}

    for group in ("executive_agencies", "amval_tamliki"):
        for category, endpoint in {
            "movable": "mainEstate-Load.action",
            "immovable": "mainImmovable-Load.action",
            "rental": "mainRental-Load.action",
            "minor": "mainMinor-Load.action",
        }.items():
            url, params = request_details(category, 0, 30, group)
            assert endpoint in url
            assert params["page"] == 0
            assert params["rows"] == 30

    executive_url, executive_params = request_details("clearance", 0, 5, "executive_agencies")
    assert "/api/centralboard/cards/" in executive_url
    assert executive_params["tagCode"] == "341,343"
    assert executive_params["notOrgId"] == "5315"
    assert "selectedOrganization" not in executive_params

    amval_url, amval_params = request_details("clearance", 0, 5, "amval_tamliki")
    assert "/api/centralboard/cards/" in amval_url
    assert amval_params["tagCode"] == "342"
    assert amval_params["selectedOrganization"] == "5315"
    assert amval_params["pageNumber"] == 0
    assert amval_params["pageSize"] == 5
    assert amval_params["sort"] == "score,desc"
    assert source_for("clearance", "amval_tamliki").default_rows == 5

    assert resolve_collection_group("clearance") == "executive_agencies"
    assert resolve_collection_group("clearance", "executive_agencies") == "executive_agencies"
    assert resolve_collection_group("clearance", "amval_tamliki") == "amval_tamliki"
    with pytest.raises(ValueError, match="Unknown collection group"):
        resolve_collection_group("clearance", "shared")


def test_amval_centralboard_clearance_validates_organization_identity():
    from setad_scope.collectors.auction_sources.registry import source_for
    from setad_scope.collectors.fetch_auction_categories import (
        SourceContextMismatch,
        validate_source_context,
    )

    raw = {
        "cartId": 4618589,
        "ticketId": "92816610-1b59-4234-a76f-f5c8d96afa31",
        "number": 3105001053006339,
        "title": "حراج خودرو GAC spio LNAA3AA18P5693879 مدل -سفید اتومات 2023",
        "basePrice": 12500000000,
        "orgName": "سازمان جمع آوری و فروش اموال تملیکی",
        "orgId": 5315,
        "tagCode": 342,
        "provinceName": "تهران",
        "cityName": "تهران",
        "jalaliSendDeadlineDate": "1405/09/08 - 19:00",
        "jalaliFromProposalDate": "1405/09/08 - 08:00",
    }
    item, _ = project_auction(raw, "clearance", collection_group="amval_tamliki")
    source = source_for("clearance", "amval_tamliki")

    assert item["collection_group"] == "amval_tamliki"
    assert item["source"] == "setad_clearance_amval_tamliki"
    assert item["source_party_id"] == "4618589"
    assert "selectedOrganization=5315" in item["source_url"]
    validate_source_context([raw], source)

    wrong_owner = {**raw, "orgId": 1234}
    with pytest.raises(SourceContextMismatch, match="expected orgId=5315"):
        validate_source_context([wrong_owner], source)

    missing_owner = {key: value for key, value in raw.items() if key != "orgId"}
    with pytest.raises(SourceContextMismatch, match="orgId is missing"):
        validate_source_context([missing_owner], source)

def test_project_auction_records_the_explicit_collection_group():
    raw = {
        "auctionParty": {
            "id": 1393501,
            "title": "فروش باتری ups",
            "baseTotalPrice": 1641500000,
            "visitCity": city("مراوه تپه", "گلستان"),
            "auction": auction("فروش باتری ups"),
        }
    }
    executive, _ = project_auction(raw, "movable", collection_group="executive_agencies")
    amval, _ = project_auction(raw, "movable", collection_group="amval_tamliki")

    assert executive["collection_group"] == "executive_agencies"
    assert amval["collection_group"] == "amval_tamliki"
    assert executive["source"] == amval["source"] == "setad_main_estate"


def test_amval_manifest_is_scoped_even_when_endpoint_and_payload_shape_are_shared(tmp_path, monkeypatch):
    from setad_scope.collectors import fetch_auction_categories as module

    calls = []

    def fake_fetch(session, category, page, rows, collection_group=None):
        calls.append((collection_group, page))
        return {"gridModel": [{"id": 700 + page}], "page": page or 1, "total": 2, "records": 2}

    monkeypatch.setattr(module, "fetch_page", fake_fetch)
    root = tmp_path / "amval" / "movable"
    summary = collect(
        "movable",
        raw_dir=root,
        session=Mock(),
        delay=0,
        collection_group="amval_tamliki",
    )

    assert summary["collection_group"] == "amval_tamliki"
    assert calls == [("amval_tamliki", 0), ("amval_tamliki", 2)]
    manifest = json.loads(next(root.glob("movable_run_*.json")).read_text(encoding="utf-8"))
    assert manifest["collection_group"] == "amval_tamliki"


def test_eauc_groups_use_distinct_gateway_contexts_and_amval_identity_guard():
    from setad_scope.collectors.auction_sources.registry import source_for
    from setad_scope.collectors.fetch_auction_categories import (
        SourceContextMismatch,
        validate_source_context,
    )

    categories = ("movable", "immovable", "rental", "minor")
    for category in categories:
        executive = source_for(category, "executive_agencies")
        amval = source_for(category, "amval_tamliki")
        assert executive.path == amval.path
        assert executive.landing_url.endswith("gateway=setad")
        assert amval.landing_url.endswith("gateway=amvalTamliki")
        assert executive.expected_auctioneer_id is None
        assert amval.expected_auctioneer_id == "2"

    amval = source_for("movable", "amval_tamliki")
    valid_row = {
        "auctionParty": {
            "auction": {"auctioneer": {"id": 2, "name": "سازمان جمع آوری و فروش اموال تملیکی"}}
        }
    }
    wrong_collection_row = {
        "auctionParty": {
            "auction": {"auctioneer": {"id": 43, "name": "بانک مسکن"}}
        }
    }

    validate_source_context([valid_row], amval)
    with pytest.raises(SourceContextMismatch, match="expected auctioneer.id=2"):
        validate_source_context([wrong_collection_row], amval)


def test_create_session_bootstraps_the_selected_eauc_gateway(monkeypatch):
    from setad_scope.collectors import fetch_auction_categories as module

    sessions = []

    class FakeResponse:
        def __init__(self, url):
            self.url = url

        def raise_for_status(self):
            return None

    class FakeSession:
        def __init__(self):
            self.headers = {}
            self.proxies = {}
            self.trust_env = True
            self.visited_urls = []
            sessions.append(self)

        def get(self, url, timeout):
            self.visited_urls.append(url)
            return FakeResponse(url)

    monkeypatch.setattr(module.requests, "Session", FakeSession)

    executive = module.create_session("movable", "executive_agencies")
    amval = module.create_session("movable", "amval_tamliki")

    assert sessions[0] is executive
    assert sessions[1] is amval
    assert executive.visited_urls == [
        "https://eauc.setadiran.ir/eauc/welcome.action?gateway=setad"
    ]
    assert amval.visited_urls == [
        "https://eauc.setadiran.ir/eauc/welcome.action?gateway=amvalTamliki"
    ]
    assert executive.headers["Referer"].endswith("gateway=setad")
    assert amval.headers["Referer"].endswith("gateway=amvalTamliki")
    assert executive.trust_env is False and amval.trust_env is False


def test_auction_collector_ignores_environment_proxy_settings():
    from setad_scope.collectors import fetch_auction_categories as module

    session = module.create_session("clearance")

    assert session.trust_env is False
    assert session.proxies == {}


def test_collect_preserves_complete_snapshot_and_reports_progress(tmp_path, monkeypatch):
    from setad_scope.collectors import fetch_auction_categories as module

    calls = []
    events = []

    def fake_fetch(session, category, page, rows):
        calls.append(page)
        return {"gridModel": [{"id": page + 20}], "page": page, "total": 3, "records": 3}

    monkeypatch.setattr(module, "fetch_page", fake_fetch)
    monkeypatch.setattr(module, "emit_progress", lambda **values: events.append(values))
    root = tmp_path / "raw" / "auctions" / "minor"
    summary = collect("minor", raw_dir=root, session=Mock(), delay=0)

    assert calls == [0, 1, 2]
    assert summary["rows_saved"] == 3
    assert summary["complete_source"] is True
    assert len(list(root.glob("minor_page_*.json"))) == 3
    assert len(list(root.glob("minor_run_*.json"))) == 1
    assert events[-1]["progress_percent"] == 85


def test_failed_collect_never_marks_a_partial_snapshot_complete(tmp_path, monkeypatch):
    from setad_scope.collectors import fetch_auction_categories as module

    def fail_second_page(session, category, page, rows):
        if page == 1:
            raise RuntimeError("source unavailable")
        return {"gridModel": [{"id": 5}], "total": 3, "records": 3}

    monkeypatch.setattr(module, "fetch_page", fail_second_page)
    root = tmp_path / "raw" / "auctions" / "minor"
    with pytest.raises(RuntimeError):
        collect("minor", raw_dir=root, session=Mock(), delay=0)
    assert not list(root.glob("minor_run_*.json"))


def test_eauc_page_zero_response_one_does_not_duplicate_first_or_skip_last(tmp_path, monkeypatch):
    """Actual eauc captures use request page=0 but return response page=1."""
    from setad_scope.collectors import fetch_auction_categories as module

    calls = []

    def fake_fetch(session, category, page, rows):
        calls.append(page)
        reported = 1 if page == 0 else page
        return {"gridModel": [{"id": reported}], "page": reported, "total": 3, "records": 3}

    monkeypatch.setattr(module, "fetch_page", fake_fetch)
    root = tmp_path / "auctions" / "movable"
    summary = collect("movable", raw_dir=root, session=Mock(), delay=0)

    assert calls == [0, 2, 3]
    assert summary["source_page_base"] == 1
    assert summary["complete_source"] is True
    assert summary["rows_saved"] == 3
    assert [p["page"] for p in summary["pages"]] == [1, 2, 3]
    assert sorted(p.name.split("_page_")[1].split("_")[0] for p in root.glob("movable_page_*.json")) == ["1", "2", "3"]


def test_eauc_rejects_wrong_reported_page_to_prevent_missing_data(tmp_path, monkeypatch):
    from setad_scope.collectors import fetch_auction_categories as module

    def fetch_wrong(session, category, page, rows):
        return {"gridModel": [{"id": 1}], "page": 1, "total": 2, "records": 2}

    monkeypatch.setattr(module, "fetch_page", fetch_wrong)
    root = tmp_path / "auctions" / "movable"
    with pytest.raises(RuntimeError, match="duplicate or missing pages"):
        collect("movable", raw_dir=root, session=Mock(), delay=0)
    assert not list(root.glob("movable_run_*.json"))


def test_clearance_428_preserves_partial_pages_without_retrying(tmp_path, capsys):
    from setad_scope.collectors import fetch_auction_categories as module

    requested = []

    class Session:
        def get(self, url, params, timeout):
            page = params["pageNumber"]
            requested.append(page)
            response = module.requests.Response()
            response.status_code = 428 if page == 2 else 200
            response._content = b'{"content":[{"cartId":1}],"totalPages":5,"totalElements":25}'
            return response

    with pytest.raises(module.ClearancePreconditionError, match="HTTP 428"):
        module.collect("clearance", delay=0, raw_dir=tmp_path, session=Session())

    assert requested == [0, 1, 2]
    assert not list(tmp_path.glob("clearance_run_*.json"))
    manifest, = tmp_path.glob("clearance_partial_*.json")
    assert f"PARTIAL_MANIFEST:{manifest.name}" in capsys.readouterr().out
    result = json.loads(manifest.read_text(encoding="utf-8"))
    assert result["complete_source"] is False
    assert [page["page"] for page in result["pages"]] == [0, 1]
