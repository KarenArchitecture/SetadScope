from datetime import datetime, timedelta, timezone

from app.services.ingestion import project_record, to_datetime


def test_jalali_date_not_misread():
    assert to_datetime("1404-08-28") is None
    assert to_datetime("2026-11-19T12:00:00+03:30") is not None


def test_active_match_and_expiry():
    now = datetime.now(timezone.utc)
    future = (now + timedelta(days=4)).isoformat()
    past = (now - timedelta(days=1)).isoformat()
    record = {
        "auctionParty": {
            "id": 42,
            "auction": {"title": "فروش چوب صنوبر", "toProposalDate": future},
        }
    }
    item, result = project_record(record, now)
    assert result == "matched"
    assert item["source_party_id"] == "42"
    assert "صنوبر" in item["matched_keywords"]

    record["auctionParty"]["auction"]["toProposalDate"] = past
    assert project_record(record, now)[1] == "expired"


def test_unrelated_and_unknown_deadline():
    now = datetime.now(timezone.utc)
    record = {
        "auctionParty": {
            "id": 43,
            "auction": {
                "title": "فروش خودرو",
                "toProposalDate": (now + timedelta(days=4)).isoformat(),
            },
        }
    }
    assert project_record(record, now)[1] == "not_matched"

    del record["auctionParty"]["auction"]["toProposalDate"]
    assert project_record(record, now)[1] == "unknown_deadline"
