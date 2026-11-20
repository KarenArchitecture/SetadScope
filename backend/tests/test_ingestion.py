from datetime import datetime, timedelta, timezone

from app.services.ingestion import project_record, to_datetime


def test_jalali_and_gregorian_dates_are_normalized_to_aware_datetimes():
    jalali = to_datetime("1405/09/17 14:30:00")
    assert jalali is not None
    assert jalali.isoformat().startswith("2026-12-08T14:30:00")
    assert jalali.utcoffset() is not None

    gregorian = to_datetime("2026-11-19T12:00:00+03:30")
    assert gregorian is not None
    assert gregorian.utcoffset() is not None


def test_auction_source_dates_are_projected_from_raw_response():
    record = {
        "auctionParty": {
            "id": 45,
            "publishStartDate": "1405/08/26 08:00:00",
            "auction": {
                "title": "فروش چوب صنوبر",
                "fromProposalDate": "1405/08/26 17:30:00",
                "toProposalDate": "1405/09/17 14:00:00",
                "fromSiteShowDate": "1405/08/26 08:00:00",
                "toSiteShowDate": "1405/09/19 13:01:00",
                "auctioneer": {"name": "سازمان نمونه"},
            },
            "visitCity": {"name": "مشهد", "province": {"name": "خراسان رضوی"}},
        }
    }

    item, status = project_record(record)
    assert status == "matched"
    assert item["proposal_start"] is not None
    assert item["proposal_deadline"].isoformat().startswith("2026-12-08T14:00:00")
    assert item["site_show_start_at"].isoformat().startswith("2026-11-17T08:00:00")
    assert item["site_show_end_at"].isoformat().startswith("2026-12-10T13:01:00")
    assert item["publish_start_at"] == item["site_show_start_at"]


def test_keyword_match_is_kept_even_when_deadline_is_past():
    now = datetime.now(timezone.utc)
    past = (now - timedelta(days=1)).isoformat()
    record = {
        "auctionParty": {
            "id": 42,
            "auction": {"title": "فروش چوب صنوبر", "toProposalDate": past},
        }
    }
    item, result = project_record(record, now)
    assert result == "matched"
    assert item["source_party_id"] == "42"
    assert "صنوبر" in item["matched_keywords"]
    assert item["proposal_deadline"] < now


def test_keyword_match_with_jalali_deadline_is_kept_and_normalized():
    record = {
        "auctionParty": {
            "id": 43,
            "auction": {
                "title": "قطع درختان صنوبر",
                "toProposalDate": "1405/09/14 19:00:00",
            },
        }
    }
    item, result = project_record(record)
    assert result == "matched"
    assert item["proposal_deadline"] is not None
    assert item["proposal_deadline"].isoformat().startswith("2026-12-05T19:00:00")


def test_unrelated_listing_is_filtered_regardless_of_deadline():
    record = {
        "auctionParty": {
            "id": 44,
            "auction": {"title": "فروش خودرو", "toProposalDate": None},
        }
    }
    assert project_record(record)[1] == "not_matched"


def test_date_filter_bounds_use_tehran_local_day_edges():
    from app.services.date_normalization import parse_filter_bound

    start = parse_filter_bound("2026-12-08")
    end = parse_filter_bound("2026-12-08", end_of_day=True)
    assert start is not None and end is not None
    assert start.hour == 0 and start.minute == 0
    assert end.hour == 23 and end.minute == 59
    assert start.utcoffset() == end.utcoffset()
