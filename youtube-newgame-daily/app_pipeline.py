from __future__ import annotations

import logging
from datetime import datetime
from typing import Iterable

from app_config import load_config
from app_dates import build_date_window, to_local_date
from app_extractors import dedupe_games_by_store_url, extract_games_from_video
from app_models import ChannelRunResult, PipelineResult, VideoRecord
from app_reporting import (
    build_daily_report_text,
    collect_current_report_rows,
    collect_legacy_report_rows,
    write_daily_report,
)
from app_storage import (
    connect_database,
    fetch_games_between_dates,
    fetch_games_by_date,
    fetch_historical_output_keys_before_run,
    fetch_report_output_run_dates_before,
    fetch_report_runs_before,
    record_report_run,
    save_report_output_items,
    upsert_game,
    upsert_game_catalog,
    upsert_video,
)
from app_store_enricher import AppStoreEnricher
from app_youtube_client import YoutubeClient, parse_youtube_datetime


LOGGER = logging.getLogger(__name__)


def run_pipeline() -> PipelineResult:
    config = load_config()
    date_window = build_date_window(config.timezone_name)

    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.history_dir.mkdir(parents=True, exist_ok=True)
    connection = connect_database(config.database_path)

    enabled_channels = [channel for channel in config.channels if channel.enabled]
    youtube_client = YoutubeClient(
        api_key=config.youtube_api_key,
        timeout_seconds=config.request_timeout_seconds,
        retry_count=config.request_retry_count,
    )
    enricher = AppStoreEnricher(
        connection=connection,
        timeout_seconds=config.request_timeout_seconds,
        retry_count=config.request_retry_count,
    )

    channel_results: list[ChannelRunResult] = []
    total_games_found = 0

    LOGGER.info(
        "run_date=%s window_start_date=%s window_end_date=%s enabled_channels=%s",
        date_window.run_date,
        date_window.previous_date,
        date_window.target_date,
        len(enabled_channels),
    )

    for channel in enabled_channels:
        LOGGER.info("Processing channel: %s", channel.name)
        try:
            channel_id = youtube_client.resolve_channel_id(channel.channel_url, channel.channel_id)
            uploads_playlist_id = youtube_client.get_uploads_playlist_id(channel_id)
            video_ids = youtube_client.list_video_ids_in_window(
                uploads_playlist_id=uploads_playlist_id,
                start_utc=date_window.previous_start_utc,
                end_utc=date_window.target_end_utc,
            )
            details = youtube_client.get_video_details(video_ids)
            videos = build_video_records(channel.name, channel_id, details, config.timezone_name)

            channel_games = []
            for video in videos:
                upsert_video(connection, video)
                extracted = dedupe_games_by_store_url(extract_games_from_video(video))
                enriched = enricher.enrich_games(extracted)
                for game in enriched:
                    upsert_game(connection, game)
                    if game.confidence != "rejected":
                        upsert_game_catalog(connection, game)
                channel_games.extend(enriched)

            connection.commit()
            total_games_found += len(channel_games)
            channel_results.append(
                ChannelRunResult(
                    channel_name=channel.name,
                    success=True,
                    videos_found=len(videos),
                    games_found=len(channel_games),
                )
            )
            LOGGER.info(
                "Channel done: %s videos=%s games=%s",
                channel.name,
                len(videos),
                len(channel_games),
            )
        except Exception as exc:  # noqa: BLE001
            connection.rollback()
            LOGGER.exception("Channel failed: %s", channel.name)
            channel_results.append(
                ChannelRunResult(
                    channel_name=channel.name,
                    success=False,
                    error_message=str(exc),
                )
            )

    backfill_historical_output_history(connection, before_run_date=date_window.run_date.isoformat())
    historical_output_keys = fetch_historical_output_keys_before_run(connection, date_window.run_date.isoformat())
    window_games = fetch_games_between_dates(
        connection,
        date_window.window_start_date.isoformat(),
        date_window.window_end_date.isoformat(),
    )
    report_rows = collect_current_report_rows(window_games, historical_output_keys)
    report_text = build_daily_report_text(
        run_date=date_window.run_date,
        window_start_date=date_window.window_start_date,
        window_end_date=date_window.window_end_date,
        report_rows=report_rows,
    )
    report_path = write_daily_report(config.output_dir, date_window.target_date, report_text)
    save_report_output_items(
        connection,
        run_date=date_window.run_date.isoformat(),
        report_path=str(report_path),
        output_rows=report_rows,
    )

    channels_total = len(enabled_channels)
    channels_success = sum(1 for item in channel_results if item.success)
    channels_failed = sum(1 for item in channel_results if not item.success)
    if channels_total == 0:
        status = "success"
    elif channels_success == 0:
        status = "failed"
    elif channels_failed > 0:
        status = "partial_failed"
    else:
        status = "success"

    error_message = "; ".join(
        f"{item.channel_name}: {item.error_message}" for item in channel_results if item.error_message
    )
    record_report_run(
        connection,
        run_date=date_window.run_date.isoformat(),
        previous_date=date_window.previous_date.isoformat(),
        target_date=date_window.target_date.isoformat(),
        status=status,
        channels_total=channels_total,
        channels_success=channels_success,
        channels_failed=channels_failed,
        games_found=total_games_found,
        report_path=str(report_path),
        error_message=error_message,
    )
    connection.commit()
    connection.close()

    return PipelineResult(
        run_date=date_window.run_date,
        previous_date=date_window.previous_date,
        target_date=date_window.target_date,
        status=status,
        channels_total=channels_total,
        channels_success=channels_success,
        channels_failed=channels_failed,
        games_found=total_games_found,
        report_path=report_path,
        channel_results=channel_results,
    )


def build_video_records(
    channel_name: str,
    channel_id: str,
    details: Iterable[dict],
    timezone_name: str,
) -> list[VideoRecord]:
    videos: list[VideoRecord] = []
    for item in details:
        snippet = item.get("snippet", {})
        published_at = parse_youtube_datetime(snippet["publishedAt"])
        videos.append(
            VideoRecord(
                channel_name=channel_name,
                channel_id=channel_id,
                video_id=item["id"],
                title=snippet.get("title", "").strip(),
                description=snippet.get("description", ""),
                published_at=published_at,
                published_date=to_local_date(published_at, timezone_name),
                url=f"https://www.youtube.com/watch?v={item['id']}",
                raw_json=item,
            )
        )
    return videos


def backfill_historical_output_history(connection, *, before_run_date: str) -> None:
    existing_run_dates = fetch_report_output_run_dates_before(connection, before_run_date)
    report_runs = fetch_report_runs_before(connection, before_run_date)

    for report_run in report_runs:
        run_date = report_run["run_date"]
        if run_date in existing_run_dates:
            continue

        target_games = fetch_games_by_date(connection, report_run["target_date"])
        previous_games = fetch_games_by_date(connection, report_run["previous_date"])
        output_rows = collect_legacy_report_rows(target_games, previous_games)
        save_report_output_items(
            connection,
            run_date=run_date,
            report_path=report_run["report_path"],
            output_rows=output_rows,
        )
