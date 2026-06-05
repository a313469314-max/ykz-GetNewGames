from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import send_feishu_report


def build_config(output_dir: Path) -> send_feishu_report.FeishuConfig:
    return send_feishu_report.FeishuConfig(
        output_dir=output_dir,
        normal_webhook_env="OVERSEAS_CASUAL_NEWGAME_FEISHU_WEBHOOK",
        normal_webhook="https://example.com/normal",
        test_webhook_env="OVERSEAS_CASUAL_NEWGAME_FEISHU_TEST_WEBHOOK",
        test_webhook="https://example.com/test",
        request_timeout_seconds=20,
    )


class FeishuSenderTests(unittest.TestCase):
    def test_default_send_uses_normal_webhook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.md"
            report_path.write_text("normal report", encoding="utf-8")
            config = build_config(Path(tmp))

            with patch("send_feishu_report.load_config", return_value=config), patch(
                "send_feishu_report.requests.post"
            ) as post, patch.object(sys, "argv", ["send_feishu_report.py", "--path", str(report_path)]):
                post.return_value.raise_for_status.return_value = None
                exit_code = send_feishu_report.main()

            self.assertEqual(exit_code, 0)
            self.assertEqual(post.call_args.args[0], "https://example.com/normal")
            self.assertEqual(post.call_args.kwargs["json"], {"msg_type": "text", "content": {"text": "normal report"}})

    def test_test_send_uses_test_webhook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.md"
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

    def test_resolve_report_path_uses_new_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            new_report = output_dir / "海外休闲新品日报_2026-06-04.md"
            new_report.write_text("new", encoding="utf-8")

            with patch("send_feishu_report.default_report_date") as default_report_date:
                default_report_date.return_value.isoformat.return_value = "2026-06-04"
                resolved = send_feishu_report.resolve_report_path(output_dir)

            self.assertEqual(resolved, new_report)

    def test_load_config_prefers_new_webhook_names(self) -> None:
        env = {
            "OVERSEAS_CASUAL_NEWGAME_FEISHU_WEBHOOK": "https://example.com/new-normal",
            "OVERSEAS_CASUAL_FEISHU_WEBHOOK": "https://example.com/old-normal",
            "OVERSEAS_CASUAL_NEWGAME_FEISHU_TEST_WEBHOOK": "https://example.com/new-test",
            "FEISHU_WEBHOOK": "https://example.com/old-test",
        }
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", env, clear=True):
            config = send_feishu_report.load_config(Path(tmp))

        self.assertEqual(config.normal_webhook_env, "OVERSEAS_CASUAL_NEWGAME_FEISHU_WEBHOOK")
        self.assertEqual(config.normal_webhook, "https://example.com/new-normal")
        self.assertEqual(config.test_webhook_env, "OVERSEAS_CASUAL_NEWGAME_FEISHU_TEST_WEBHOOK")
        self.assertEqual(config.test_webhook, "https://example.com/new-test")

    def test_load_config_falls_back_to_old_webhook_names(self) -> None:
        env = {
            "OVERSEAS_CASUAL_FEISHU_WEBHOOK": "https://example.com/old-normal",
            "FEISHU_WEBHOOK": "https://example.com/old-test",
        }
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", env, clear=True):
            config = send_feishu_report.load_config(Path(tmp))

        self.assertEqual(config.normal_webhook_env, "OVERSEAS_CASUAL_FEISHU_WEBHOOK")
        self.assertEqual(config.normal_webhook, "https://example.com/old-normal")
        self.assertEqual(config.test_webhook_env, "FEISHU_WEBHOOK")
        self.assertEqual(config.test_webhook, "https://example.com/old-test")


if __name__ == "__main__":
    unittest.main()
