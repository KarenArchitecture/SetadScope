"""Import a collector run (latest by default) or all saved raw snapshots."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.db.session import SessionLocal
from app.services.ingestion import RAW_DIR, import_pages


def latest_run_files(raw_dir: Path) -> list[Path]:
    summaries = sorted(raw_dir.glob("main_estate_run_*.json"))
    if not summaries:
        return sorted(raw_dir.glob("main_estate_page_*.json"))

    summary_path = summaries[-1]
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    files: list[Path] = []
    for page in summary.get("pages", []):
        relative_name = page.get("file")
        if not relative_name:
            continue
        candidate = raw_dir / Path(relative_name).name
        if not candidate.is_file():
            raise FileNotFoundError(
                f"Collector summary references a missing page file: {candidate}"
            )
        files.append(candidate)
    return sorted(set(files))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument(
        "--all",
        action="store_true",
        help="Import every saved page snapshot instead of only the latest collector run.",
    )
    args = parser.parse_args()

    files = (
        sorted(args.raw_dir.glob("main_estate_page_*.json"))
        if args.all
        else latest_run_files(args.raw_dir)
    )
    if not files:
        print(f"No raw listing files in {args.raw_dir}")
        return

    with SessionLocal() as session:
        print(import_pages(session, files))


if __name__ == "__main__":
    main()
