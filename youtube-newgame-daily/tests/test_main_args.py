from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import main


class MainArgsTests(unittest.TestCase):
    def test_run_date_keeps_existing_meaning(self) -> None:
        with patch("main.load_config", return_value=SimpleNamespace(timezone_name="Asia/Shanghai")):
            parsed = main.parse_run_datetime(run_date="2026-05-29", report_date=None)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.date().isoformat(), "2026-05-29")
        self.assertEqual(parsed.hour, 12)

    def test_report_date_alias_adds_one_day_for_internal_run_date(self) -> None:
        with patch("main.load_config", return_value=SimpleNamespace(timezone_name="Asia/Shanghai")):
            parsed = main.parse_run_datetime(run_date=None, report_date="2026-05-28")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.date().isoformat(), "2026-05-29")
        self.assertEqual(parsed.hour, 12)

    def test_no_date_uses_current_runtime(self) -> None:
        with patch("main.load_config") as load_config:
            parsed = main.parse_run_datetime(run_date=None, report_date=None)

        self.assertIsNone(parsed)
        load_config.assert_not_called()

    def test_date_and_run_date_are_mutually_exclusive(self) -> None:
        with self.assertRaises(SystemExit):
            main.parse_args(["--date", "2026-05-28", "--run-date", "2026-05-29"])


if __name__ == "__main__":
    unittest.main()
