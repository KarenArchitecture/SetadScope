from .centralboard import extract_rows as extract_centralboard_rows
from .centralboard import page_totals as centralboard_page_totals
from .centralboard import reported_page as centralboard_reported_page
from .eauc import extract_rows as extract_eauc_rows
from .eauc import page_totals as eauc_page_totals
from .eauc import reported_page as eauc_reported_page


def extract_rows(payload: dict, adapter: str) -> list:
    if adapter == "eauc":
        return extract_eauc_rows(payload)
    if adapter == "centralboard":
        return extract_centralboard_rows(payload)
    raise ValueError(f"Unsupported auction response adapter: {adapter}")


def page_totals(payload: dict, adapter: str, rows: int) -> tuple[int, int | None]:
    if adapter == "eauc":
        return eauc_page_totals(payload, rows)
    if adapter == "centralboard":
        return centralboard_page_totals(payload, rows)
    raise ValueError(f"Unsupported auction response adapter: {adapter}")


def reported_page(payload: dict, adapter: str):
    if adapter == "eauc":
        return eauc_reported_page(payload)
    if adapter == "centralboard":
        return centralboard_reported_page(payload)
    raise ValueError(f"Unsupported auction response adapter: {adapter}")
