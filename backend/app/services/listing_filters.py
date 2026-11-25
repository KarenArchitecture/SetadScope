"""Date predicates shared by the listing and export queries."""
from datetime import datetime, timedelta

from fastapi import HTTPException

from app.services.date_normalization import TEHRAN, parse_filter_bound


def date_range(column, name: str, start: str | None, end: str | None) -> list:
    bounds = [
        parse_filter_bound(start),
        parse_filter_bound(end, end_of_day=True),
    ]
    for value, bound in zip((start, end), bounds):
        if value and bound is None:
            raise HTTPException(status_code=422, detail=f"Invalid date filter: {value}")
    lower, upper = bounds
    if lower and upper and lower > upper:
        raise HTTPException(status_code=422, detail=f"{name}_from cannot exceed {name}_to")
    return ([column >= lower] if lower else []) + ([column <= upper] if upper else [])


def announced_today(column) -> tuple:
    start = datetime.now(TEHRAN).replace(hour=0, minute=0, second=0, microsecond=0)
    return column >= start, column < start + timedelta(days=1)
