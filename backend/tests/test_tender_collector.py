from setad_scope.collectors.fetch_tenders import (
    extract_csrf_token,
    get_page_count,
    page_params,
)


def test_extract_csrf_token_from_struts_hidden_input():
    html = """
    <form>
      <input type="hidden" name="struts.token.name" value="csrf_token">
      <input type="hidden" name="csrf_token" value="fresh-token-123">
    </form>
    """
    assert extract_csrf_token(html) == "fresh-token-123"


def test_extract_csrf_token_from_meta_tag():
    html = '<meta name="csrf-token" content="meta-token-456">'
    assert extract_csrf_token(html) == "meta-token-456"


def test_page_params_match_captured_setad_request_shape():
    params = page_params("fresh-token", page=7, rows=30, now_ms=123456789)
    assert params == {
        "struts.token.name": "csrf_token",
        "csrf_token": "fresh-token",
        "_search": "false",
        "nd": 123456789,
        "rows": 30,
        "page": 7,
        "sidx": "",
        "sord": "asc",
        "_": 123456789,
    }


def test_tender_collector_ignores_environment_proxy_settings(monkeypatch):
    from setad_scope.collectors import fetch_tenders as collector

    class FakeResponse:
        text = '<input type="hidden" name="csrf_token" value="fresh-token">'
        url = "https://etend.setadiran.ir/etend/"

        @staticmethod
        def raise_for_status():
            return None

    class FakeSession:
        def __init__(self):
            self.trust_env = True
            self.proxies = {"https": "http://127.0.0.1:8080"}
            self.headers = {}
            self.cookies = []

        @staticmethod
        def get(*args, **kwargs):
            return FakeResponse()

    session = FakeSession()
    monkeypatch.setattr(collector.requests, "Session", lambda: session)

    created, token, landing_url = collector.create_session()

    assert created is session
    assert created.trust_env is False
    assert created.proxies == {}
    assert token == "fresh-token"
    assert landing_url == FakeResponse.url


def test_page_count_uses_server_reported_total_and_record_count():
    assert get_page_count({"total": "128", "records": "3838"}, rows=30) == (128, 3838)


def test_page_count_can_fall_back_to_record_count():
    assert get_page_count({"records": 61}, rows=30) == (3, 61)


def test_main_discovers_total_pages_and_fetches_every_page(tmp_path, monkeypatch):
    import json
    import sys

    from setad_scope.collectors import fetch_tenders as collector

    calls = []
    progress_events = []

    class FakeSession:
        pass

    def fake_fetch_page(session, token, page, rows=30, landing_url=None):
        calls.append(page)
        return {
            "page": page,
            "total": 3,
            "records": 65,
            "gridModel": [{"id": page * 100 + index} for index in range(2)],
        }, token

    monkeypatch.setattr(collector, "RAW_DIR", tmp_path / "data" / "raw" / "tenders")
    monkeypatch.setattr(collector, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(collector, "create_session", lambda landing_url=None: (FakeSession(), "token", "https://example.test/"))
    monkeypatch.setattr(collector, "fetch_page", fake_fetch_page)
    monkeypatch.setattr(collector, "emit_progress", lambda **values: progress_events.append(values))
    monkeypatch.setattr(sys, "argv", ["fetch_tenders", "--delay", "0"])

    assert collector.main() == 0
    assert calls == [1, 2, 3]

    summaries = list((tmp_path / "data" / "raw" / "tenders").glob("tender_run_*.json"))
    assert len(summaries) == 1
    summary = json.loads(summaries[0].read_text(encoding="utf-8"))
    assert summary["total_pages_reported"] == 3
    assert summary["total_records_reported"] == 65
    assert summary["total_rows_saved"] == 6
    assert len(summary["pages"]) == 3
    assert [event["current_page"] for event in progress_events if event.get("current_page")] == [1, 2, 3]


def test_error_messages_redact_csrf_query_values():
    from setad_scope.collectors.fetch_tenders import sanitize_error

    safe = sanitize_error(
        "403 Forbidden: https://example.test/list?csrf_token=do-not-log&rows=30"
    )
    assert "do-not-log" not in safe
    assert "csrf_token=[REDACTED]" in safe
    assert "rows=30" in safe
