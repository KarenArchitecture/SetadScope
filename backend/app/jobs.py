"""Import already-collected Setad JSON snapshots."""
from __future__ import annotations
import argparse
from pathlib import Path
from app.db.session import SessionLocal
from app.services.ingestion import RAW_DIR, import_pages

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    args = parser.parse_args()
    files = sorted(args.raw_dir.glob("main_estate_page_*.json"))
    if not files:
        print(f"No raw listing files in {args.raw_dir}")
        return
    with SessionLocal() as session:
        print(import_pages(session, files))

if __name__ == "__main__":
    main()
