from app.raw_cleanup import prune_previous_runs


def test_rotation_preserves_complete_snapshot_during_partial_import(tmp_path):
    def snapshot(stamp, marker):
        page = tmp_path / f"clearance_page_0_{stamp}.json"
        page.touch()
        (tmp_path / f"clearance_{marker}_{stamp}.json").touch()
        return [page]

    complete = snapshot("20261101_090000", "run")
    old = snapshot("20261102_090000", "partial")
    current = snapshot("20261103_090000", "partial")
    other = tmp_path / "user.json"
    other.touch()
    assert prune_previous_runs(current, partial=True) == 2
    assert complete[0].exists() and not old[0].exists()
    fresh = snapshot("20261104_090000", "run")
    assert prune_previous_runs(fresh) == 4
    assert fresh[0].exists() and other.exists()
