from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

from src.dates import default_report_date
from src.report import REPORT_TITLE


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_NORMAL_WEBHOOK_ENV = "OVERSEAS_CASUAL_NEWGAME_FEISHU_WEBHOOK"
LEGACY_NORMAL_WEBHOOK_ENV = "OVERSEAS_CASUAL_FEISHU_WEBHOOK"
DEFAULT_TEST_WEBHOOK_ENV = "OVERSEAS_CASUAL_NEWGAME_FEISHU_TEST_WEBHOOK"
LEGACY_TEST_WEBHOOK_ENV = "FEISHU_WEBHOOK"
NORMAL_WEBHOOK_SELECTOR_ENV = "OVERSEAS_CASUAL_FEISHU_WEBHOOK_ENV"
TEST_WEBHOOK_SELECTOR_ENV = "OVERSEAS_CASUAL_FEISHU_TEST_WEBHOOK_ENV"


@dataclass(frozen=True)
class FeishuConfig:
    output_dir: Path
    normal_webhook_env: str
    normal_webhook: str
    test_webhook_env: str
    test_webhook: str
    request_timeout_seconds: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send latest overseas casual new game report to Feishu webhook.")
    parser.add_argument("--path", help="Explicit report file path")
    parser.add_argument("--test", action="store_true", help="Send to the test Feishu webhook instead of the normal webhook")
    return parser.parse_args()


def load_config(project_root: Path | str | None = None) -> FeishuConfig:
    root = Path(project_root or PROJECT_ROOT).resolve()
    load_dotenv(root / ".env")
    normal_env, normal_webhook = resolve_env_value(
        (DEFAULT_NORMAL_WEBHOOK_ENV, LEGACY_NORMAL_WEBHOOK_ENV),
        selector_env=NORMAL_WEBHOOK_SELECTOR_ENV,
    )
    test_env, test_webhook = resolve_env_value(
        (DEFAULT_TEST_WEBHOOK_ENV, LEGACY_TEST_WEBHOOK_ENV),
        selector_env=TEST_WEBHOOK_SELECTOR_ENV,
    )
    return FeishuConfig(
        output_dir=root / "output",
        normal_webhook_env=normal_env,
        normal_webhook=normal_webhook,
        test_webhook_env=test_env,
        test_webhook=test_webhook,
        request_timeout_seconds=int(os.getenv("FEISHU_REQUEST_TIMEOUT_SECONDS", "20")),
    )


def resolve_env_value(env_names: tuple[str, ...], *, selector_env: str) -> tuple[str, str]:
    selected_env = os.getenv(selector_env, "").strip()
    candidates = (selected_env, *env_names) if selected_env else env_names
    for env_name in candidates:
        value = os.getenv(env_name, "").strip()
        if value:
            return env_name, value
    return candidates[0], ""


def main() -> int:
    args = parse_args()
    config = load_config()
    webhook, webhook_env, target_name = resolve_webhook(config, use_test=args.test)
    if not webhook:
        print(f"Feishu {target_name} webhook is missing. Set {webhook_env} in .env or environment variables.")
        return 1

    report_path = Path(args.path).resolve() if args.path else resolve_report_path(config.output_dir)
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


def resolve_webhook(config: FeishuConfig, *, use_test: bool) -> tuple[str, str, str]:
    if use_test:
        return config.test_webhook.strip(), config.test_webhook_env, "test webhook"
    return config.normal_webhook.strip(), config.normal_webhook_env, "normal webhook"


def resolve_report_path(output_dir: Path) -> Path | None:
    today = default_report_date().isoformat()
    expected = output_dir / f"{REPORT_TITLE}_{today}.md"
    if expected.exists():
        return expected

    cutoff = datetime.now() - timedelta(hours=6)
    candidates = list(output_dir.glob(f"{REPORT_TITLE}_*.md"))
    candidates = sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)
    for candidate in candidates:
        modified_at = datetime.fromtimestamp(candidate.stat().st_mtime)
        if modified_at >= cutoff:
            return candidate
    return None


if __name__ == "__main__":
    raise SystemExit(main())
