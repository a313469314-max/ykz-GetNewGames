from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

import requests

from app_config import load_config
from app_dates import build_date_window


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send latest YouTube new game report to Feishu webhook.")
    parser.add_argument("--path", help="Explicit report file path")
    parser.add_argument("--test", action="store_true", help="Send to the test Feishu webhook instead of the normal webhook")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config()
    webhook, webhook_env, target_name = resolve_webhook(config, use_test=args.test)
    if not webhook:
        print(
            f"Feishu {target_name} webhook is missing. Configure it in channels.yaml or set {webhook_env}."
        )
        return 1

    report_path = Path(args.path).resolve() if args.path else resolve_report_path(config.output_dir, config.timezone_name)
    if not report_path or not report_path.exists():
        print("Report file not found.")
        return 1

    text = report_path.read_text(encoding="utf-8")
    response = requests.post(
        webhook,
        json={"msg_type": "text", "content": {"text": text}},
        timeout=config.request_timeout_seconds,
    )
    response.raise_for_status()
    print(f"Feishu report sent to {target_name}: {report_path}")
    return 0


def resolve_webhook(config, *, use_test: bool) -> tuple[str, str, str]:
    if use_test:
        return config.feishu_test_webhook.strip(), config.feishu_test_webhook_env, "test webhook"
    return config.feishu_webhook.strip(), config.feishu_webhook_env, "normal webhook"


def resolve_report_path(output_dir: Path, timezone_name: str) -> Path | None:
    date_window = build_date_window(timezone_name)
    expected = output_dir / f"youtube_new_games_{date_window.target_date.isoformat()}.txt"
    if expected.exists():
        return expected

    cutoff = datetime.now() - timedelta(hours=6)
    candidates = sorted(output_dir.glob("youtube_new_games_*.txt"), key=lambda path: path.stat().st_mtime, reverse=True)
    for candidate in candidates:
        modified_at = datetime.fromtimestamp(candidate.stat().st_mtime)
        if modified_at >= cutoff:
            return candidate
    return None


if __name__ == "__main__":
    raise SystemExit(main())
