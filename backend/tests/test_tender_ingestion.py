from app.services.tender_ingestion import project_tender_record


def test_project_tender_record_maps_list_fields_and_keeps_jalali_dates():
    source = {
        "id": 682495,
        "number": 2005092998000008,
        "title": "مناقصه عمومی اجرای بازسازی",
        "type": "PUBLIC_TENDER",
        "typeName": "مناقصه عمومی",
        "organization": {"name": "مرکز درمانی رازی"},
        "operationProvinceName": "آذربایجان شرقی",
        "operationCityName": "تبریز",
        "domainsDescription": "اجرای عملیات طبق اسناد پیوست",
        "publicNotificationDate": "1405/08/28 22:00:00",
        "documentsDeadlineDate": "1405/09/05 19:00:00",
        "proposalDeadlineDate": "1405/09/17 14:30:00",
        "openingDate": "1405/09/18 09:30:00",
    }

    item, status = project_tender_record(source)

    assert status == "ready"
    assert item["source_tender_id"] == "682495"
    assert item["tender_number"] == "2005092998000008"
    assert item["organization"] == "مرکز درمانی رازی"
    assert item["province"] == "آذربایجان شرقی"
    assert item["city"] == "تبریز"
    assert item["proposal_deadline_date"] == "1405/09/17 14:30:00"
    assert item["raw_payload"] is source


def test_project_tender_record_accepts_string_organization():
    item, status = project_tender_record(
        {"id": "42", "organization": "سازمان نمونه", "title": "مناقصه"}
    )

    assert status == "ready"
    assert item["organization"] == "سازمان نمونه"


def test_project_tender_record_skips_rows_without_source_id():
    item, status = project_tender_record({"number": "123", "title": "مناقصه"})

    assert item is None
    assert status == "missing_id"
