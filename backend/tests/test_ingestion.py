from datetime import datetime, timedelta, timezone

from app.services.ingestion import project_record, to_datetime


def test_jalali_date_is_left_unparsed_for_now():
    assert to_datetime("1405/09/18 13:00:00") is None
    assert to_datetime("2026-11-19T12:00:00+03:30") is not None


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


def test_keyword_match_is_kept_when_deadline_is_unknown():
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
    assert item["proposal_deadline"] is None


def test_unrelated_listing_is_filtered_regardless_of_deadline():
    record = {
        "auctionParty": {
            "id": 44,
            "auction": {"title": "فروش خودرو", "toProposalDate": None},
        }
    }
    assert project_record(record)[1] == "not_matched"
