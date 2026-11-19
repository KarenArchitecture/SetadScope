import json

from app.jobs import latest_run_files


def test_latest_run_selects_only_its_page_files(tmp_path):
    old_page = tmp_path / "main_estate_page_1_20261118_100000.json"
    new_page = tmp_path / "main_estate_page_1_20261119_100000.json"
    old_page.write_text("{}", encoding="utf-8")
    new_page.write_text("{}", encoding="utf-8")

    old_summary = {
        "pages": [{"file": f"data/raw/{old_page.name}"}]
    }
    new_summary = {
        "pages": [{"file": f"data/raw/{new_page.name}"}]
    }
    (tmp_path / "main_estate_run_20261118_100000.json").write_text(
        json.dumps(old_summary), encoding="utf-8"
    )
    (tmp_path / "main_estate_run_20261119_100000.json").write_text(
        json.dumps(new_summary), encoding="utf-8"
    )

    assert latest_run_files(tmp_path) == [new_page]


def test_latest_run_falls_back_to_page_files_without_summary(tmp_path):
    page = tmp_path / "main_estate_page_1_20261119_100000.json"
    page.write_text("{}", encoding="utf-8")

    assert latest_run_files(tmp_path) == [page]
