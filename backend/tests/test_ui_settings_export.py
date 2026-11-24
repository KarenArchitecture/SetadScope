"""Regression tests for persistent keyword validation and useful Excel exports."""
from decimal import Decimal

import pytest
from openpyxl import load_workbook

from app.services.excel_export import build_excel
from app.services.keyword_matching import matched_keywords
from app.services.keyword_settings import validate_keywords


def test_excel_table_filters_and_numeric_cells():
    data = build_excel(
        "مزایده‌ها",
        "TestAuctions",
        ["شناسه", "عنوان", "مبلغ"],
        [["0000123", "فروش چوب", Decimal("190000.50")]],
        [22, 45, 26],
        numeric_columns=(3,),
    )
    sheet = load_workbook(data).active
    assert sheet.sheet_view.rightToLeft is True
    assert sheet.freeze_panes == "C2"
    assert "TestAuctions" in sheet.tables
    assert sheet.tables["TestAuctions"].ref == "A1:C2"
    assert sheet["A2"].value == "0000123"
    assert sheet["A2"].data_type == "s"
    assert sheet["C2"].data_type == "n"
    assert sheet["C2"].value == 190000.5
    # Width follows actual content instead of the configured maximum (45).
    assert 12 <= sheet.column_dimensions["B"].width < 45
    assert sheet["A1"].font.name == "Vazirmatn"
    assert sheet["A1"].font.sz == 13
    assert sheet["A1"].font.bold is True
    assert sheet["B2"].font.name == "Vazirmatn"
    assert sheet["B2"].font.sz == 12
    assert sheet["B2"].font.bold is True
    assert sheet["B2"].alignment.wrap_text is True


def test_long_descriptions_wrap_with_bounded_column_width():
    data = build_excel(
        "مزایده‌ها",
        "LongDescription",
        ["شناسه", "شرح"],
        [["00012", "آگهی فروش چوب با شرایط مزایده و مشخصات تفصیلی " * 7]],
        [22, 48],
    )
    sheet = load_workbook(data).active
    assert sheet.column_dimensions["B"].width == 48
    assert 30 < sheet.row_dimensions[2].height <= 84
    assert sheet.tables["LongDescription"].ref == "A1:B2"


def test_empty_excel_still_has_filterable_headers():
    data = build_excel("مناقصه‌ها", "TestTenders", ["شناسه", "شرح"], [], [22, 40])
    sheet = load_workbook(data).active
    assert sheet.auto_filter.ref == "A1:B1"


def test_validation_keeps_order_and_rejects_normalized_duplicates():
    assert validate_keywords([" چوب ", "چوب آلات", "درخت"]) == [
        "چوب", "چوب آلات", "درخت"
    ]
    with pytest.raises(ValueError):
        validate_keywords(["چوب", "چوب"])
    with pytest.raises(ValueError):
        validate_keywords(["منابع طبيعي", "منابع طبیعی"])
    with pytest.raises(ValueError):
        validate_keywords([])
    with pytest.raises(ValueError):
        validate_keywords([" "])


def test_configurable_keywords_without_changing_default_matching():
    assert "آلومینیوم" in matched_keywords("ضایعات آلومینیوم", keywords=("آلومینیوم",))
    assert "چوب" not in matched_keywords("فروش چوب", keywords=("آلومینیوم",))
    assert "چوب" in matched_keywords("فروش چوب")


def test_export_dates_use_tehran_and_persian_digits():
    from app.services.date_normalization import persian_timestamp
    assert persian_timestamp("2026-11-24T15:30:00+00:00") == "۱۴۰۵/۰۹/۰۳  ۱۹:۰۰"
    assert persian_timestamp("2026-11-24T22:30:00+00:00") == "۱۴۰۵/۰۹/۰۴  ۰۲:۰۰"
