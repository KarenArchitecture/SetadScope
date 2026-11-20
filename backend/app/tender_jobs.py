"""Import tender response JSON pages already saved under data/raw/tenders."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.db.session import SessionLocal
from app.services.tender_ingestion import RAW_DIR, import_tender_pages


def latest_tender_run_files(raw_dir: Path) -> list[Path]:
    summaries = sorted(raw_dir.glob("tender_run_*.json"))
    if not summaries:
        return sorted(raw_dir.glob("tender_page_*.json"))

    summary_path = summaries[-1]
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    files: list[Path] = []
    for page in summary.get("pages", []):
        relative_name = page.get("file")
        if not relative_name:
            continue
        candidate = raw_dir / Path(relative_name).name
        if not candidate.is_file():
            raise FileNotFoundError(f"Tender run summary references a missing page: {candidate}")
        files.append(candidate)
    return sorted(set(files))


def main() -> None:
    parser = argparse.ArgumentParser(description="Import saved Setad tender JSON pages.")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument(
        "--all",
        action="store_true",
        help="Import all saved tender page snapshots instead of the latest run.",
    )
    args = parser.parse_args()

    files = (
        sorted(args.raw_dir.glob("tender_page_*.json"))
        if args.all
        else latest_tender_run_files(args.raw_dir)
    )
    if not files:
        print(f"No tender response pages found in {args.raw_dir}")
        return

    with SessionLocal() as session:
        print(import_tender_pages(session, files))


if __name__ == "__main__":
    main()
