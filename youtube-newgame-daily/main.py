from __future__ import annotations

import logging
import sys

from app_pipeline import run_pipeline


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def main() -> int:
    configure_logging()
    result = run_pipeline()
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
