from copy import deepcopy

import pytest
from fastapi import BackgroundTasks, HTTPException

from app import main


def _snapshot_states():
    with main.collection_lock:
        return deepcopy(main.collection_states)


def _restore_states(snapshot):
    with main.collection_lock:
        main.collection_states.clear()
        main.collection_states.update(snapshot)


def test_global_collection_runs_all_sources_sequentially_and_continues_after_failure(monkeypatch):
    previous_states = _snapshot_states()
    try:
        with main.collection_lock:
            for key, state in list(main.collection_states.items()):
                if key == "global":
                    main.collection_states[key] = main.initial_global_collection_state()
                elif key == "tenders":
                    main.collection_states[key] = main.initial_collection_state("tenders")
                else:
                    _, group, category = key.split(":", 2)
                    main.collection_states[key] = main.initial_collection_state(
                        "auctions", group, category
                    )
            main.collection_states["global"].update({
                "status": "running",
                "phase": "starting",
                "started_at": "2026-11-22T00:00:00+00:00",
            })

        failed_key = main.collection_state_key("amval_tamliki", "immovable")
        calls = []

        def fake_run_collection_job(kind, collection_group=None, category=None):
            if kind == "tenders":
                state_key = "tenders"
            else:
                state_key = main.collection_state_key(collection_group, category)
            calls.append(state_key)
            failed = state_key == failed_key
            main.update_collection_state(
                state_key,
                status="failed" if failed else "completed",
                phase="failed" if failed else "completed",
                message="اجرای آزمایشی ناموفق" if failed else "اجرای آزمایشی موفق",
                error="خطای آزمایشی" if failed else None,
                progress_percent=35 if failed else 100,
                finished_at="2026-11-22T00:01:00+00:00",
            )

        monkeypatch.setattr(main, "run_collection_job", fake_run_collection_job)
        main.run_global_collection_job()

        expected = [main.global_source_state_key(source) for source in main.GLOBAL_COLLECTION_SOURCES]
        state = main.collection_states["global"]
        assert calls == expected
        assert len(calls) == 10
        assert state["status"] == "completed_with_errors"
        assert state["completed_sources"] == 10
        assert state["successful_sources"] == 9
        assert state["overall_progress_percent"] == 100
        assert state["progress_percent"] == 100
        assert len(state["failed_sources"]) == 1
        assert state["failed_sources"][0]["key"] == failed_key
        assert state["failed_sources"][0]["error"] == "خطای آزمایشی"
    finally:
        _restore_states(previous_states)


def test_global_collection_start_rejects_an_individual_job_already_running():
    previous_states = _snapshot_states()
    try:
        with main.collection_lock:
            main.collection_states["global"] = main.initial_global_collection_state()
            main.collection_states["tenders"] = main.initial_collection_state("tenders")
            main.collection_states["tenders"]["status"] = "collecting"

        with pytest.raises(HTTPException) as error:
            main.start_global_collection(BackgroundTasks())

        assert error.value.status_code == 409
    finally:
        _restore_states(previous_states)


def test_individual_collection_start_is_blocked_during_global_collection():
    previous_states = _snapshot_states()
    try:
        with main.collection_lock:
            main.collection_states["global"] = main.initial_global_collection_state()
            main.collection_states["global"]["status"] = "running"

        with pytest.raises(HTTPException) as error:
            main.start_auction_category_collection(
                "movable",
                BackgroundTasks(),
                db=None,
                collection_group="executive_agencies",
            )

        assert error.value.status_code == 409
    finally:
        _restore_states(previous_states)


def test_global_collection_start_registers_background_job_and_reports_source_count():
    previous_states = _snapshot_states()
    try:
        with main.collection_lock:
            main.collection_states["global"] = main.initial_global_collection_state()
            for key, state in main.collection_states.items():
                if key != "global":
                    state["status"] = "idle"

        background_tasks = BackgroundTasks()
        response = main.start_global_collection(background_tasks)

        assert response["status"] == "running"
        assert response["total_sources"] == 10
        assert response["started_at"]
        assert len(background_tasks.tasks) == 1
        assert background_tasks.tasks[0].func is main.run_global_collection_job
    finally:
        _restore_states(previous_states)
