"""Import a successful auction-category snapshot. Never ingest half-finished collections."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.db.session import SessionLocal
from app.services.auction_ingestion import AUCTION_CATEGORIES, import_auction_pages
from app.services.ingestion import PROJECT_ROOT

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "auctions"


def latest_category_files(category: str, raw_dir: Path | None = None) -> list[Path]:
    if category not in AUCTION_CATEGORIES:
        raise ValueError(f"Unsupported category: {category}")
    root = raw_dir or RAW_DIR / category
    manifests = sorted(root.glob(f"{category}_run_*.json"))
    if not manifests:
        return []
    manifest = json.loads(manifests[-1].read_text(encoding="utf-8"))
    if manifest.get("category") != category:
        raise ValueError("Manifest category does not match import category")
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
    parser.add_argument("--category", choices=AUCTION_CATEGORIES, required=True)
    parser.add_argument("--raw-dir", type=Path, default=None)
    args = parser.parse_args()
    files = latest_category_files(args.category, args.raw_dir)
    if not files:
        raise SystemExit(f"No completed {args.category} run found")
    with SessionLocal() as session:
        print(import_auction_pages(session, files, args.category))


if __name__ == "__main__":
    main()
