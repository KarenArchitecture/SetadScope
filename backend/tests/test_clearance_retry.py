from copy import deepcopy
import time

import pytest
from fastapi import HTTPException

from app import main


@pytest.mark.parametrize("collection_group", ["executive_agencies", "amval_tamliki"])
def test_clearance_retry_endpoint_signals_the_matching_owner(tmp_path, collection_group):
    state_key = main.collection_state_key(collection_group, "clearance")
    previous_state = deepcopy(main.collection_states[state_key])
    previous_signal = main.retry_signal_paths.get(state_key)
    signal_path = tmp_path / collection_group / "retry"
    signal_path.parent.mkdir(parents=True)

    state = main.initial_collection_state("auctions", collection_group, "clearance")
    state.update(
        status="collecting",
        phase="waiting_for_access",
        retry_id="active-retry-token",
        retry_at=time.time() + 120,
    )
    main.collection_states[state_key] = state
    main.retry_signal_paths[state_key] = signal_path

    try:
        result = main.request_clearance_retry(
            retry_id="active-retry-token",
            collection_group=collection_group,
        )
        assert result == {"accepted": True}
        assert signal_path.read_text(encoding="utf-8") == "active-retry-token"
    finally:
        main.collection_states[state_key] = previous_state
        if previous_signal is None:
            main.retry_signal_paths.pop(state_key, None)
        else:
            main.retry_signal_paths[state_key] = previous_signal


def test_clearance_retry_endpoint_rejects_stale_retry_token(tmp_path):
    collection_group = "executive_agencies"
    state_key = main.collection_state_key(collection_group, "clearance")
    previous_state = deepcopy(main.collection_states[state_key])
    previous_signal = main.retry_signal_paths.get(state_key)
    signal_path = tmp_path / "retry"
    state = main.initial_collection_state("auctions", collection_group, "clearance")
    state.update(
        status="collecting",
        phase="waiting_for_access",
        retry_id="current-token",
        retry_at=time.time() + 120,
    )
    main.collection_states[state_key] = state
    main.retry_signal_paths[state_key] = signal_path

    try:
        with pytest.raises(HTTPException) as error:
            main.request_clearance_retry(
                retry_id="stale-token",
                collection_group=collection_group,
            )
        assert error.value.status_code == 409
        assert not signal_path.exists()
    finally:
        main.collection_states[state_key] = previous_state
        if previous_signal is None:
            main.retry_signal_paths.pop(state_key, None)
        else:
            main.retry_signal_paths[state_key] = previous_signal


def test_waiting_clearance_retry_metadata_reaches_global_batch_state():
    previous_states = deepcopy(main.collection_states)
    try:
        collection_group = "amval_tamliki"
        state_key = main.collection_state_key(collection_group, "clearance")
        with main.collection_lock:
            for key, state in main.collection_states.items():
                if key == "global":
                    main.collection_states[key] = main.initial_global_collection_state()
                elif state.get("kind") == "auction_batch":
                    state["status"] = "idle"
            main.collection_states["global"].update(
                status="running",
                current_source_key=state_key,
            )

        main.update_collection_state(
            state_key,
            status="collecting",
            phase="waiting_for_access",
            collection_group=collection_group,
            retry_at=1234567890,
            manual_retry_at=1234567800,
            retry_id="batch-retry-token",
            progress_percent=42,
        )

        batch = main.collection_states["global"]
        assert batch["current_phase"] == "waiting_for_access"
        assert batch["retry_id"] == "batch-retry-token"
        assert batch["retry_collection_group"] == "amval_tamliki"
        assert batch["retry_at"] == 1234567890
    finally:
        with main.collection_lock:
            main.collection_states.clear()
            main.collection_states.update(previous_states)



def test_interrupted_checkpoint_metadata_is_exposed_for_manual_resume():
    previous_states = deepcopy(main.collection_states)
    try:
        collection_group = "executive_agencies"
        state_key = main.collection_state_key(collection_group, "clearance")
        with main.collection_lock:
            main.collection_states["global"] = main.initial_global_collection_state()
            main.collection_states["global"].update(
                status="running",
                current_source_key=state_key,
            )

        state = main.update_collection_state(
            state_key,
            status="collecting",
            phase="interrupted",
            resumable=True,
            resume_page=381,
            resume_records_saved=3810,
            progress_percent=48,
        )
        assert state["resumable"] is True
        assert state["resume_page"] == 381
        assert state["resume_records_saved"] == 3810

        batch = main.collection_states["global"]
        assert batch["current_resumable"] is True
        assert batch["current_resume_page"] == 381
        assert batch["current_resume_records_saved"] == 3810
    finally:
        with main.collection_lock:
            main.collection_states.clear()
            main.collection_states.update(previous_states)
