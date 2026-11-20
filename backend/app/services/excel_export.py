"""Styled, searchable Excel worksheets shared by auctions and tenders."""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.utils import get_column_letter


def build_excel(
    sheet_name: str,
    table_name: str,
    headers: Sequence[str],
    rows: Iterable[Sequence[object]],
    widths: Sequence[int],
    numeric_columns: Sequence[int] = (),
) -> BytesIO:
    """Keep identifiers as text; style numeric values and expose native Excel filter/sort."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    sheet.sheet_view.rightToLeft = True
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.sheet_properties.tabColor = "315F9F"
    sheet.freeze_panes = "C2"
    sheet.append(list(headers))
    sheet.row_dimensions[1].height = 32

    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width

    for cell in sheet[1]:
        cell.fill = PatternFill("solid", fgColor="24466E")
        cell.font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="right", vertical="center", wrap_text=True)

    count = 0
    numeric = set(numeric_columns)
    for values in rows:
        sheet.append(list(values))
        count += 1
        row = sheet.max_row
        sheet.row_dimensions[row].height = 25
        for cell in sheet[row]:
            cell.alignment = Alignment(horizontal="right", vertical="center")
            cell.font = Font(name="Arial", size=10, color="253B53")
            if cell.column in numeric and cell.value is not None:
                cell.number_format = '#,##0.00'
            if isinstance(cell.value, str) and cell.value.startswith(("https://", "http://")):
                cell.hyperlink = cell.value
                cell.font = Font(name="Arial", size=10, color="2767A4", underline="single")

    table_ref = f"A1:{get_column_letter(len(headers))}{sheet.max_row}"
    if count:
        table = Table(displayName=table_name, ref=table_ref)
        table.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium2", showFirstColumn=False,
            showLastColumn=False, showRowStripes=True, showColumnStripes=False,
        )
        sheet.add_table(table)
    else:
        sheet.auto_filter.ref = table_ref

    sheet.print_title_rows = "1:1"
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return stream
