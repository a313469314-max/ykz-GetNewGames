from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv

from app_models import AppConfig, ChannelConfig


CSV_ENCODINGS = ("utf-8-sig", "utf-8", "gbk", "cp936")


def load_config(project_root: Path | str | None = None) -> AppConfig:
    root = Path(project_root or Path(__file__).resolve().parent).resolve()
    load_dotenv(root / ".env")

    yaml_path = root / "channels.yaml"
    with yaml_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    channels_file = root / raw.get("channels_file", "channels.csv")
    output_dir = root / raw.get("output_dir", "output")
    history_dir = output_dir / "history"
    database_path = root / raw.get("database_path", "data/youtube_newgame.db")
    timezone_name = raw.get("timezone_name", "Asia/Shanghai")
    youtube_api_key_env = raw.get("youtube_api_key_env", "YOUTUBE_API_KEY")
    feishu_webhook_env = raw.get("feishu_webhook_env", "FEISHU_WEBHOOK")

    channels = load_channels_csv(channels_file)

    return AppConfig(
        project_root=root,
        channels_file=channels_file,
        output_dir=output_dir,
        history_dir=history_dir,
        database_path=database_path,
        timezone_name=timezone_name,
        timezone=ZoneInfo(timezone_name),
        youtube_api_key_env=youtube_api_key_env,
        youtube_api_key=(raw.get("youtube_api_key") or os.getenv(youtube_api_key_env, "")).strip(),
        feishu_webhook_env=feishu_webhook_env,
        feishu_webhook=(raw.get("feishu_webhook") or os.getenv(feishu_webhook_env, "")).strip(),
        request_timeout_seconds=int(raw.get("request_timeout_seconds", 20)),
        request_retry_count=int(raw.get("request_retry_count", 3)),
        channels=channels,
    )


def load_channels_csv(path: Path) -> list[ChannelConfig]:
    errors: list[str] = []
    for encoding in CSV_ENCODINGS:
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.DictReader(handle)
                return [parse_channel_row(row) for row in reader if any((value or "").strip() for value in row.values())]
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}: {exc}")

    raise UnicodeDecodeError(
        "channels.csv",
        b"",
        0,
        1,
        "Unable to decode channels.csv with supported encodings: " + "; ".join(errors),
    )


def parse_channel_row(row: dict[str, Any]) -> ChannelConfig:
    return ChannelConfig(
        name=(row.get("name") or "").strip(),
        channel_url=(row.get("channel_url") or "").strip(),
        enabled=parse_bool(row.get("enabled")),
        channel_id=(row.get("channel_id") or "").strip(),
    )


def parse_bool(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y", "on"}
