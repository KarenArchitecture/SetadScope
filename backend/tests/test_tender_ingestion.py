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
    assert item["public_notification_at"].isoformat().startswith("2026-11-19T22:00:00")
    assert item["documents_deadline_at"].isoformat().startswith("2026-11-26T19:00:00")
    assert item["proposal_deadline_at"].isoformat().startswith("2026-12-08T14:30:00")
    assert item["opening_at"].isoformat().startswith("2026-12-09T09:30:00")
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



def test_keyword_relevance_supports_persian_normalization_and_custom_keywords():
    matched, status = project_tender_record(
        {
            "id": 506,
            "title": "خرید چوب آلات",
            "domainsDescription": "تامین مصالح و چوب‌آلات جنگلی",
            "typeName": "مناقصه عمومی",
        }
    )
    assert status == "ready"
    assert matched["has_keyword_match"] is True
    assert "چوب" in matched["matched_keywords"]

    unrelated, _ = project_tender_record(
        {"id": 507, "title": "خرید تجهیزات اداری"}
    )
    assert unrelated["has_keyword_match"] is False
    assert unrelated["matched_keywords"] == []

    custom, _ = project_tender_record(
        {"id": 508, "title": "فروش ضایعات آلومینیوم"},
        keywords=("آلومینیوم",),
    )
    assert custom["has_keyword_match"] is True
    assert custom["matched_keywords"] == ["آلومینیوم"]

    suppressed, _ = project_tender_record(
        {"id": 509, "title": "تامین الوار چوب"},
        keywords=("آلومینیوم",),
    )
    assert suppressed["has_keyword_match"] is False
