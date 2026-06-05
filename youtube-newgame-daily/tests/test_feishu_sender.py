from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

import send_feishu_report


def build_config(output_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(
        output_dir=output_dir,
        timezone_name="Asia/Shanghai",
        feishu_webhook_env="YOUTUBE_FEISHU_WEBHOOK",
        feishu_webhook="https://example.com/normal",
        feishu_test_webhook_env="FEISHU_WEBHOOK",
        feishu_test_webhook="https://example.com/test",
        request_timeout_seconds=20,
    )


class FeishuSenderTests(unittest.TestCase):
    def test_default_send_uses_normal_webhook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.txt"
            report_path.write_text("normal report", encoding="utf-8")
            config = build_config(Path(tmp))

            with patch("send_feishu_report.load_config", return_value=config), patch(
                "send_feishu_report.requests.post"
            ) as post, patch.object(sys, "argv", ["send_feishu_report.py", "--path", str(report_path)]):
                post.return_value.raise_for_status.return_value = None
                exit_code = send_feishu_report.main()

            self.assertEqual(exit_code, 0)
            self.assertEqual(post.call_args.args[0], "https://example.com/normal")

    def test_test_send_uses_test_webhook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.txt"
            report_path.write_text("test report", encoding="utf-8")
            config = build_config(Path(tmp))

            with patch("send_feishu_report.load_config", return_value=config), patch(
                "send_feishu_report.requests.post"
            ) as post, patch.object(
                sys,
                "argv",
                ["send_feishu_report.py", "--test", "--path", str(report_path)],
            ):
                post.return_value.raise_for_status.return_value = None
                exit_code = send_feishu_report.main()

            self.assertEqual(exit_code, 0)
            self.assertEqual(post.call_args.args[0], "https://example.com/test")


if __name__ == "__main__":
    unittest.main()
