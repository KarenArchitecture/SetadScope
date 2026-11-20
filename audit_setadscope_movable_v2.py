#!/usr/bin/env python3
"""Audit SetadScope movable auctions against a complete raw collector run (v2).

Usage (from SetadScope project root):
    python audit_setadscope_movable.py
    python audit_setadscope_movable.py --deep

Requires only Python standard library; no DB credentials or extra packages.
Writes movable_audit_report.json with differences and counts.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path



KEYWORDS = (
    "تراورس", "صنوبر", "درخت", "درختان", "جنگل", "چوب", "چوب آلات",
    "اشجار", "برگ", "نهال", "منابع طبیعی", "پروانه قطع",
)
CHAR_TRANSLATION = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ة": "ه", "ۀ": "ه", "أ": "ا", "إ": "ا", "ٱ": "ا"})
ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")


def normalize_fa(value):
    text = unicodedata.normalize("NFKC", str(value or "")).translate(CHAR_TRANSLATION)
    text = ZERO_WIDTH.sub(" ", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text).strip().casefold()


def expected_keywords(*texts):
    normalized = normalize_fa(" ".join(str(v or "") for v in texts))
    return [word for word in KEYWORDS if re.search(r"(?<!\w)" + re.escape(normalize_fa(word)) + r"(?!\w)", normalized)]


def latest_snapshot(root: Path):
    manifests = sorted(root.glob("movable_run_*.json"))
    if not manifests:
        raise RuntimeError(f"No completed collection manifest found in {root}. Run the movable collector first.")
    manifest = json.loads(manifests[-1].read_text(encoding="utf-8-sig"))
    if manifest.get("category") != "movable":
        raise RuntimeError("Latest manifest category is not movable")
    if not manifest.get("complete_source", False):
        raise RuntimeError("Latest run is a PARTIAL snapshot (complete_source=false). Perform a full collection first.")
    pages = manifest.get("pages", [])
    if not pages:
        raise RuntimeError("Latest manifest contains no pages")
    rows, per_page, page_numbers = [], [], []
    for entry in pages:
        path = root / Path(entry["file"]).name
        if not path.is_file():
            raise RuntimeError(f"Missing snapshot page: {path}")
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        batch = payload.get("gridModel")
        if not isinstance(batch, list):
            raise RuntimeError(f"Invalid gridModel in {path}")
        page_no = int(payload.get("page", -1))
        page_numbers.append(page_no)
        per_page.append({"file": path.name, "page": page_no, "rows": len(batch),
                         "reported_total": payload.get("records"), "reported_pages": payload.get("total")})
        rows.extend(batch)
    return manifest, rows, per_page, page_numbers


def api_get(base: str, path: str, params=None):
    endpoint = base.rstrip("/") + path
    if params:
        endpoint += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(endpoint, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Could not reach API {endpoint}: {exc}") from exc


def backend_rows(base: str):
    rows, pages, reported = [], None, None
    page = 1
    while pages is None or page <= pages:
        payload = api_get(base, "/api/auctions", {
            "category": "movable", "matched_only": "false", "status": "all",
            "page_size": 100, "page": page, "sort_by": "proposal_deadline", "sort_dir": "asc",
        })
        if pages is None:
            pages, reported = int(payload["pages"]), int(payload["total"])
        elif int(payload["pages"]) != pages or int(payload["total"]) != reported:
            raise RuntimeError("API pagination changed while auditing; run again after collection finishes")
        batch = payload.get("items")
        if not isinstance(batch, list):
            raise RuntimeError("Invalid API items response")
        rows.extend(batch)
        print(f"Backend: page {page}/{pages}, {len(rows)}/{reported} rows", flush=True)
        page += 1
    return rows, reported


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> date:
    jy += 1595
    days = -355668 + 365 * jy + (jy // 33 * 8) + ((jy % 33 + 3) // 4) + jd
    days += (jm - 1) * 31 if jm < 7 else (jm - 7) * 30 + 186
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
    dd = days + 1
    for month, length in enumerate([31, 29 if gy % 4 == 0 and (gy % 100 != 0 or gy % 400 == 0) else 28,
                                    31, 30, 31, 30, 31, 31, 30, 31, 30, 31], 1):
        if dd <= length:
            return date(gy, month, dd)
        dd -= length
    raise ValueError("Invalid Jalali date")


def parse_source_date(value):
    if not value:
        return None
    m = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?", str(value))
    if not m:
        return "unrecognized"
    y, mo, d, h, minute, second = m.groups()
    converted = jalali_to_gregorian(int(y), int(mo), int(d))
    # Iran no longer observes daylight-saving time for 1405 (2026).
    local = datetime(converted.year, converted.month, converted.day, int(h or 0),
                     int(minute or 0), int(second or 0),
                     tzinfo=timezone(timedelta(hours=3, minutes=30)))
    return local.astimezone(timezone.utc)


def source_fields(record):
    party = record.get("auctionParty") or {}
    auction = party.get("auction") or {}
    org = auction.get("auctioneer") or {}
    city = party.get("visitCity") or {}
    province = (city.get("province") or {}).get("name")
    if not province:
        province = ((org.get("city") or {}).get("province") or {}).get("name")
    title = auction.get("title") or party.get("title")
    description = auction.get("description") or party.get("description")
    matched = expected_keywords(
        title, description, party.get("title"), party.get("itemGroupName"),
        party.get("address"), party.get("visitAddress"), record.get("categoryName"),
    )
    return {
        "source": "setad_main_estate",
        "category": "movable",
        "price_type": "sale_base",
        "has_keyword_match": bool(matched),
        "matched_keywords": matched,
        "source_party_id": str(party.get("id")) if party.get("id") is not None else None,
        "auction_id": str(auction["id"]) if auction.get("id") is not None else None,
        "auction_no": str(auction["auctionNo"]) if auction.get("auctionNo") is not None else None,
        "item_reference_no": str(party["partyNo"]) if party.get("partyNo") is not None else None,
        "item_title": party.get("title"),
        "title": title,
        "organization": org.get("name"),
        "province": province,
        "city": city.get("name"),
        "state": auction.get("state") or party.get("state"),
        "base_total_price": party.get("baseTotalPrice"),
        "proposal_start": auction.get("fromProposalDate"),
        "proposal_deadline": auction.get("toProposalDate"),
        "announcement_at": auction.get("fromSiteShowDate"),
    }


def numeric_equal(a, b):
    if a is None or b is None:
        return a is None and b is None
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except (InvalidOperation, ValueError):
        return False


def date_equal(source_value, api_value):
    converted = parse_source_date(source_value)
    if converted == "unrecognized":
        return None
    if converted is None or api_value is None:
        return converted is None and api_value is None
    try:
        return converted == datetime.fromisoformat(api_value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return False


def audit(root: Path, api: str, deep: bool):
    manifest, raw, pages, page_numbers = latest_snapshot(root)
    print(f"Raw snapshot: {len(pages)} pages, {len(raw)} records", flush=True)
    imported, api_total = backend_rows(api)
    raw_ids = [source_fields(r)["source_party_id"] for r in raw]
    api_ids = [str(r.get("source_party_id")) for r in imported]
    raw_index = dict(zip(raw_ids, raw))
    api_index = dict(zip(api_ids, imported))
    raw_duplicates = {k: v for k, v in Counter(raw_ids).items() if v > 1}
    api_duplicates = {k: v for k, v in Counter(api_ids).items() if v > 1}
    missing_in_backend = sorted(set(raw_ids) - set(api_ids))
    extra_in_backend = sorted(set(api_ids) - set(raw_ids))
    errors = []
    skipped_date_checks = 0
    deep_count = 0
    deep_error = None
    for key in sorted(set(raw_ids) & set(api_ids)):
        actual = api_index[key]
        expected = source_fields(raw_index[key])
        for field, wanted in expected.items():
            # /api/auctions exposes category but deliberately does not serialize
            # the internal `source` column. Its absence is not a data mismatch.
            # Validate that column via PostgreSQL separately if needed.
            if field in {"source_party_id", "source"}:
                continue
            got = actual.get(field)
            if field == "base_total_price":
                valid = numeric_equal(wanted, got)
            elif field in {"proposal_start", "proposal_deadline", "announcement_at"}:
                valid = date_equal(wanted, got)
                if valid is None:
                    skipped_date_checks += 1
                    continue
            else:
                valid = wanted == got
            if not valid:
                errors.append({"source_party_id": key, "field": field,
                               "raw_value": wanted, "backend_value": got})
        if deep:
            try:
                detail = api_get(api, "/api/auctions/" + str(actual["id"]))
                if detail.get("raw_payload") != raw_index[key]:
                    errors.append({"source_party_id": key, "field": "raw_payload",
                                   "raw_value": "differs", "backend_value": "differs"})
                deep_count += 1
            except RuntimeError as exc:
                deep_error = str(exc)
                break
    expected_pages = int(manifest.get("total_pages_reported") or len(pages))
    expected_records = int(manifest.get("total_records_reported") or len(raw))
    complete_pages = (len(pages) == expected_pages and len(set(page_numbers)) == expected_pages)
    page_numbers_contiguous = sorted(page_numbers) == list(range(min(page_numbers), max(page_numbers) + 1))
    meta_consistent = all(p["reported_total"] == expected_records and p["reported_pages"] == expected_pages for p in pages)
    check = {
        "complete_manifest": bool(manifest.get("complete_source")),
        "all_reported_pages_saved": complete_pages and page_numbers_contiguous,
        "all_pages_agree_on_total": meta_consistent,
        "raw_count_matches_source_total": len(raw) == expected_records,
        "raw_no_duplicate_ids": not raw_duplicates,
        "backend_count_matches_api_total": len(imported) == api_total,
        "backend_no_duplicate_ids": not api_duplicates,
        "backend_contains_at_least_all_raw_records": api_total >= len(raw),
        "raw_ids_present_in_backend": not missing_in_backend,
        "normalized_fields_and_dates_match": not errors,
    }
    if deep:
        check["raw_payload_jsonb_identical_for_all_rows"] = not deep_error and deep_count == len(raw) and not any(e["field"] == "raw_payload" for e in errors)
    report = {
        "category": "movable", "snapshot_manifest": manifest.get("started_at"),
        "raw_pages": len(pages), "raw_records": len(raw),
        "source_reported_records": expected_records,
        "api_total": api_total, "api_received_records": len(imported),
        "raw_duplicates": raw_duplicates, "api_duplicates": api_duplicates,
        "missing_in_backend_count": len(missing_in_backend),
        "missing_in_backend_sample": missing_in_backend[:30],
        "extra_in_backend_count": len(extra_in_backend),
        "extra_backend_records_are_expected_when_archiving": True,
        "extra_in_backend_sample": extra_in_backend[:30],
        "field_mismatch_count": len(errors), "field_mismatch_sample": errors[:40],
        "field_mismatch_by_field": dict(Counter(e["field"] for e in errors)),
        "api_unexposed_fields_not_compared": ["source"],
        "unrecognized_date_checks": skipped_date_checks,
        "deep_checked_rows": deep_count, "deep_error": deep_error,
        "checks": check, "passed": all(check.values()),
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="Audit complete raw movable snapshot vs local Backend")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/auctions/movable"))
    parser.add_argument("--api", default="http://127.0.0.1:18080")
    parser.add_argument("--deep", action="store_true", help="Also check every raw_payload in PostgreSQL via details API")
    parser.add_argument("--report", type=Path, default=Path("movable_audit_report.json"))
    args = parser.parse_args()
    try:
        report = audit(args.raw_dir, args.api, args.deep)
    except Exception as exc:
        print("AUDIT FAILED TO RUN:", exc, file=sys.stderr)
        return 2
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nResult:", "PASS" if report["passed"] else "FAIL")
    for k, v in report["checks"].items():
        print(" ", "PASS" if v else "FAIL", k)
    print(f"Report: {args.report.resolve()}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
