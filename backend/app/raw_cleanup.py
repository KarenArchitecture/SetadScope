"""Rotate older raw runs after the replacement has been imported successfully."""
import re
from pathlib import Path


def prune_previous_runs(imported: list[Path], *, partial: bool = False) -> int:
    page_pattern = r"(?P<source>[a-z_]+)_page_\d+_(?P<stamp>\d{8}_\d{6}(?:_\d{6})?)\.json"
    match = re.fullmatch(page_pattern, imported[0].name)
    if not match:
        return 0
    source, stamp = match.group("source", "stamp")
    folder = imported[0].parent
    marker = "partial" if partial else "run"
    if not (folder / f"{source}_{marker}_{stamp}.json").is_file():
        return 0
    pattern = re.compile(
        rf"{re.escape(source)}_(?:page_\d+|run|partial)_(\d{{8}}_\d{{6}}(?:_\d{{6}})?)\.json"
    )
    old_partials = {p.stem.removeprefix(f"{source}_partial_") for p in folder.glob(f"{source}_partial_*.json")} if partial else set()
    removed = 0
    for file in folder.iterdir():
        old = pattern.fullmatch(file.name)
        if partial and (not old or old[1] not in old_partials):
            continue
        if old and old[1] < stamp and file.is_file() and not file.is_symlink():
            file.unlink(missing_ok=True)
            removed += 1
    return removed
