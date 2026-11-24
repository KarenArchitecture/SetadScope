"""Calendar-aware date normalization for Setad's Jalali and Gregorian timestamps."""
from __future__ import annotations

import re
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

TEHRAN = ZoneInfo("Asia/Tehran")
_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def _jalali_to_gregorian(year: int, month: int, day: int) -> date:
    """Convert a valid Jalali date to Gregorian without external dependencies."""
    if not 1 <= month <= 12:
        raise ValueError("Invalid Jalali month")
    if month <= 6 and not 1 <= day <= 31:
        raise ValueError("Invalid Jalali day")
    if 7 <= month <= 11 and not 1 <= day <= 30:
        raise ValueError("Invalid Jalali day")
    leap_year = year % 33 in {1, 5, 9, 13, 17, 22, 26, 30}
    if month == 12 and not 1 <= day <= (30 if leap_year else 29):
        raise ValueError("Invalid Jalali Esfand day")

    jy = year + 1595
    days = -355668 + (365 * jy) + (jy // 33 * 8) + ((jy % 33 + 3) // 4) + day
    days += (month - 1) * 31 if month < 7 else ((month - 7) * 30) + 186

    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        gy += 100 * ((days - 1) // 36524)
        days = (days - 1) % 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365

    gregorian_day = days + 1
    gregorian_leap = (gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0
    month_lengths = [31, 29 if gregorian_leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gregorian_month = 1
    for month_length in month_lengths:
        if gregorian_day <= month_length:
            break
        gregorian_day -= month_length
        gregorian_month += 1
    return date(gy, gregorian_month, gregorian_day)


def _with_tehran(value: datetime) -> datetime:
    return value.replace(tzinfo=TEHRAN) if value.tzinfo is None else value


def parse_setad_datetime(value: object) -> datetime | None:
    """Parse Setad timestamps into timezone-aware Gregorian datetimes.

    Setad currently returns Jalali values such as 1405/09/17 14:30:00.
    Original source strings remain stored separately / in raw_payload.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return _with_tehran(value)
    if isinstance(value, (int, float)):
        number = int(value)
        if number <= 0:
            return None
        seconds = number / 1000 if number > 100000000000 else number
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    raw = str(value).strip().translate(_DIGITS)
    if not raw:
        return None

    epoch_match = re.fullmatch(r"\d{10,13}", raw)
    if epoch_match:
        number = int(raw)
        try:
            return datetime.fromtimestamp(
                number / 1000 if len(raw) == 13 else number,
                tz=timezone.utc,
            )
        except (OverflowError, OSError, ValueError):
            return None

    dotnet_match = re.fullmatch(r"/Date\((\d+)(?:[+-]\d{4})?\)/", raw)
    if dotnet_match:
        try:
            return datetime.fromtimestamp(int(dotnet_match.group(1)) / 1000, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    jalali_match = re.fullmatch(
        r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})"
        r"(?:[ T](\d{1,2}):(\d{1,2})(?::(\d{1,2})(?:\.(\d{1,6}))?)?)?",
        raw,
    )
    if jalali_match:
        year, month, day, hour, minute, second, microsecond = jalali_match.groups()
        parts = [int(year), int(month), int(day)]
        clock = [int(hour or 0), int(minute or 0), int(second or 0)]
        micros = int((microsecond or "0").ljust(6, "0"))
        try:
            if 1200 <= parts[0] <= 1600:
                converted = _jalali_to_gregorian(*parts)
                return datetime(
                    converted.year, converted.month, converted.day,
                    *clock, micros, tzinfo=TEHRAN,
                )
            return datetime(*parts, *clock, micros, tzinfo=TEHRAN)
        except ValueError:
            return None

    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if not 1900 <= parsed.year <= 2100:
        return None
    return _with_tehran(parsed)


def parse_filter_bound(value: str | None, *, end_of_day: bool = False) -> datetime | None:
    """Parse ISO date-picker values or Jalali date text as Tehran-local day bounds."""
    if value is None or not value.strip():
        return None
    raw = value.strip().translate(_DIGITS)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        try:
            day = date.fromisoformat(raw)
            return datetime.combine(
                day,
                time.max if end_of_day else time.min,
                tzinfo=TEHRAN,
            )
        except ValueError:
            return None
    parsed = parse_setad_datetime(raw)
    if parsed and end_of_day and not re.search(r"\d{1,2}:\d{2}", raw):
        return parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
    return parsed


def persian_timestamp(value: object) -> str:
    instant = parse_setad_datetime(value)
    if instant is None:
        return ""
    local = instant.astimezone(TEHRAN)
    year = local.year - 621
    first_day = _jalali_to_gregorian(year, 1, 1)
    if local.date() < first_day:
        year -= 1
        first_day = _jalali_to_gregorian(year, 1, 1)
    offset = (local.date() - first_day).days
    if offset < 186:
        month, day = divmod(offset, 31)
        month += 1
    else:
        month, day = divmod(offset - 186, 30)
        month += 7
    return f"{year:04}/{month:02}/{day + 1:02}  {local:%H:%M}".translate(
        str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    )
