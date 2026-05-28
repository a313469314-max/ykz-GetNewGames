from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


@dataclass(slots=True)
class ChannelConfig:
    name: str
    channel_url: str
    enabled: bool
    channel_id: str = ""


@dataclass(slots=True)
class AppConfig:
    project_root: Path
    channels_file: Path
    output_dir: Path
    history_dir: Path
    database_path: Path
    timezone_name: str
    timezone: ZoneInfo
    youtube_api_key_env: str
    youtube_api_key: str
    feishu_webhook_env: str
    feishu_webhook: str
    request_timeout_seconds: int
    request_retry_count: int
    channels: list[ChannelConfig] = field(default_factory=list)


@dataclass(slots=True)
class DateWindow:
    run_date: date
    previous_date: date
    target_date: date
    previous_start_local: datetime
    target_end_local: datetime
    previous_start_utc: datetime
    target_end_utc: datetime

    @property
    def window_start_date(self) -> date:
        return self.previous_date

    @property
    def window_end_date(self) -> date:
        return self.target_date

    @property
    def window_dates(self) -> list[date]:
        return [self.run_date.fromordinal(self.previous_date.toordinal() + offset) for offset in range(3)]


@dataclass(slots=True)
class VideoRecord:
    channel_name: str
    channel_id: str
    video_id: str
    title: str
    description: str
    published_at: datetime
    published_date: date
    url: str
    raw_json: dict[str, Any]


@dataclass(slots=True)
class ExtractedGame:
    report_date: date
    channel_name: str
    video_id: str
    video_title: str
    game_name: str
    normalized_game_name: str
    store_url: str
    package_id: str
    apple_app_id: str
    platform: str
    extracted_from: str
    link_type: str = "rejected"
    confidence: str = "rejected"
    reject_reason: str = ""
    normalized_store_url: str = ""

    @property
    def dedupe_key(self) -> str:
        if self.package_id:
            return f"pkg:{self.package_id.lower()}"
        if self.apple_app_id:
            return f"ios:{self.apple_app_id}"
        if self.normalized_store_url:
            return f"name_url:{self.normalized_game_name}:{self.normalized_store_url}"
        return f"name:{self.normalized_game_name}"


@dataclass(slots=True)
class ChannelRunResult:
    channel_name: str
    success: bool
    videos_found: int = 0
    games_found: int = 0
    error_message: str = ""


@dataclass(slots=True)
class PipelineResult:
    run_date: date
    previous_date: date
    target_date: date
    status: str
    channels_total: int
    channels_success: int
    channels_failed: int
    games_found: int
    report_path: Path
    channel_results: list[ChannelRunResult] = field(default_factory=list)

    @property
    def window_start_date(self) -> date:
        return self.previous_date

    @property
    def window_end_date(self) -> date:
        return self.target_date
