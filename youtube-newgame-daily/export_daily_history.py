from __future__ import annotations

import argparse
import csv
from pathlib import Path

from app_config import load_config
from app_storage import connect_database, fetch_games_by_date, fetch_latest_report_date


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export daily YouTube new game history to CSV.")
    parser.add_argument("--date", help="Target report date, format: YYYY-MM-DD")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config()
    connection = connect_database(config.database_path)

    report_date = args.date or fetch_latest_report_date(connection)
    if not report_date:
        print("No game history found in database.")
        return 0

    rows = fetch_games_by_date(connection, report_date)
    output_path = config.history_dir / f"youtube_new_games_history_{report_date}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "report_date",
                "channel_name",
                "game_name",
                "normalized_game_name",
                "platform",
                "store_url",
                "normalized_store_url",
                "package_id",
                "apple_app_id",
                "video_id",
                "video_title",
                "video_url",
                "extracted_from",
                "link_type",
                "confidence",
                "reject_reason",
                "created_at",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))

    print(f"Exported {len(rows)} rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
