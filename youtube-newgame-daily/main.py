from __future__ import annotations

import logging
import sys
from argparse import ArgumentParser, Namespace
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app_config import load_config
from app_pipeline import run_pipeline


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def parse_args(argv: list[str] | None = None) -> Namespace:
    parser = ArgumentParser(description="Run YouTube new game daily report pipeline.")
    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument("--run-date", help="Run date in YYYY-MM-DD. Target report date is run-date minus one day.")
    date_group.add_argument("--date", help="Report date in YYYY-MM-DD. Internally uses run-date = date plus one day.")
    return parser.parse_args(argv)


def parse_run_datetime(*, run_date: str | None, report_date: str | None) -> datetime | None:
    if not run_date and not report_date:
        return None
    config = load_config()
    if report_date:
        parsed_date = datetime.strptime(report_date, "%Y-%m-%d").date() + timedelta(days=1)
    else:
        parsed_date = datetime.strptime(run_date or "", "%Y-%m-%d").date()
    return datetime.combine(parsed_date, time(hour=12), tzinfo=ZoneInfo(config.timezone_name))


def main() -> int:
    configure_logging()
    args = parse_args()
    result = run_pipeline(now=parse_run_datetime(run_date=args.run_date, report_date=args.date))
    logging.info(
        "run_date=%s window_start_date=%s window_end_date=%s success_channels=%s failed_channels=%s games_found=%s report_path=%s",
        result.run_date,
        result.previous_date,
        result.target_date,
        result.channels_success,
        result.channels_failed,
        result.games_found,
        result.report_path,
    )
    return 1 if result.channels_total > 0 and result.channels_success == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
