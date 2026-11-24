"""Readable, filterable Excel exports shared by auctions and tenders."""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from io import BytesIO
from math import ceil
from unicodedata import east_asian_width

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.utils import get_column_letter


def _display_length(value: object) -> int:
    """Estimate a cell's rendered text width, including wider Unicode glyphs."""
    if value is None:
        return 0
    lines = str(value).splitlines() or [""]
    return max(sum(2 if east_asian_width(char) in ("W", "F") else 1 for char in line) for line in lines)


def build_excel(
    sheet_name: str,
    table_name: str,
    headers: Sequence[str],
    rows: Iterable[Sequence[object]],
    widths: Sequence[int],
    numeric_columns: Sequence[int] = (),
) -> BytesIO:
    """Auto-size columns to observed content, with sensible maximums for long descriptions.

    `widths` defines each column's upper bound, not a fixed width. Long content
    wraps instead of producing extremely wide, difficult-to-navigate worksheets.
    """
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    sheet.sheet_view.rightToLeft = True
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.sheet_properties.tabColor = "315F9F"
    sheet.sheet_format.defaultRowHeight = 30
    sheet.freeze_panes = "C2"
    sheet.append(list(headers))
    sheet.row_dimensions[1].height = 39

    # Leave extra room for native Excel Table filter dropdowns.
    observed_widths = [_display_length(header) + 7 for header in headers]
    maximum_widths = [widths[i] if i < len(widths) else 60 for i in range(len(headers))]

    alignment = Alignment(horizontal="right", vertical="center", wrap_text=True)
    header_fill = PatternFill("solid", fgColor="24466E")
    header_font = Font(name="Vazirmatn", size=13, bold=True, color="FFFFFF")
    body_font = Font(name="Vazirmatn", size=12, bold=True, color="253B53")
    link_font = Font(name="Vazirmatn", size=12, bold=True, color="2767A4", underline="single")
    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = alignment

    count = 0
    numeric = set(numeric_columns)
    for values in rows:
        sheet.append(list(values))
        count += 1
        row_index = count + 1
        visible_lines = 1

        # Explicit bounds avoid rescanning the whole sheet for every row.
        cells = next(sheet.iter_rows(min_row=row_index, max_row=row_index, max_col=len(headers)))
        for cell in cells:
            index = cell.column - 1
            length = _display_length(cell.value)
            observed_widths[index] = max(observed_widths[index], length + 4)

            cell.alignment = alignment
            cell.font = body_font
            if cell.column in numeric and cell.value is not None:
                cell.number_format = "#,##0.00"
                # Include the thousands separators and decimals in width estimates.
                number_text = format(cell.value, ",.2f")
                observed_widths[index] = max(observed_widths[index], _display_length(number_text) + 4)

            if isinstance(cell.value, str) and cell.value.startswith(("https://", "http://")):
                cell.hyperlink = cell.value
                cell.font = link_font

            # Avoid enormous rows while showing several lines of long descriptions.
            available = max(8, int(maximum_widths[index] / 1.15) - 3)
            line_count = max(
                1,
                sum(ceil(_display_length(part) / available) or 1 for part in str(cell.value or "").splitlines() or [""]),
            )
            visible_lines = max(visible_lines, min(4, line_count))

        sheet.row_dimensions[row_index].height = 30 + (visible_lines - 1) * 18

    for index, (measured, cap) in enumerate(zip(observed_widths, maximum_widths), start=1):
        # Vazirmatn 12pt bold needs a little extra width compared with the default font.
        sheet.column_dimensions[get_column_letter(index)].width = min(
            cap, max(12, ceil(measured * 1.12)),
        )

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
