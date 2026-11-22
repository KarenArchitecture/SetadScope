"""Import completed auction snapshots, scoped by collection group and category."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.db.session import SessionLocal
from app.services.auction_ingestion import (
    AUCTION_CATEGORIES_BY_GROUP,
    AUCTION_CATEGORIES,
    import_auction_pages,
    resolve_collection_group,
)
from app.services.ingestion import PROJECT_ROOT
from setad_scope.collectors.fetch_auction_categories import category_raw_dir

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "auctions"


def latest_category_files(
    category: str,
    raw_dir: Path | None = None,
    collection_group: str | None = None,
) -> list[Path]:
    group = resolve_collection_group(category, collection_group)
    root = raw_dir or category_raw_dir(group, category)
    manifests = sorted(root.glob(f"{category}_run_*.json"))

    if not manifests:
        return []
    manifest = json.loads(manifests[-1].read_text(encoding="utf-8"))
    if manifest.get("category") != category:
        raise ValueError("Manifest category does not match import category")
    manifest_group = manifest.get("collection_group")
    if manifest_group is not None and manifest_group != group:
        raise ValueError("Manifest collection group does not match import group")
    files = []
    for item in manifest.get("pages", []):
        name = Path(item["file"]).name
        path = root / name
        if not path.is_file():
            raise FileNotFoundError(f"Run manifest references missing page: {path}")
        files.append(path)
    if not files:
        raise ValueError("Successful manifest is empty")
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", choices=tuple(AUCTION_CATEGORIES_BY_GROUP), default=None)
    parser.add_argument("--category", choices=AUCTION_CATEGORIES, default=None)
    parser.add_argument("--raw-dir", type=Path, default=None)
    args = parser.parse_args()

    if args.category:
        group = resolve_collection_group(args.category, args.group)
        categories = (args.category,)
    else:
        group = args.group or "executive_agencies"
        categories = AUCTION_CATEGORIES_BY_GROUP[group]

    failures = []
    with SessionLocal() as session:
        for category in categories:
            try:
                files = latest_category_files(category, args.raw_dir, group)
                if not files:
                    raise RuntimeError(f"No completed {group}/{category} run found")
                print(group, category, import_auction_pages(
                    session, files, category, collection_group=group,
                ))
            except Exception as exc:
                failures.append(f"{category}: {exc}")
                print(f"IMPORT FAILED {group}/{category}: {exc}")
    if failures:
        raise SystemExit("One or more imports failed: " + " | ".join(failures))


if __name__ == "__main__":
    main()
