from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from app_models import ExtractedGame, VideoRecord


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_name TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    video_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    published_at TEXT NOT NULL,
    published_date TEXT NOT NULL,
    url TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT NOT NULL,
    channel_name TEXT NOT NULL,
    video_id TEXT NOT NULL,
    video_title TEXT NOT NULL,
    game_name TEXT NOT NULL,
    normalized_game_name TEXT NOT NULL,
    store_url TEXT NOT NULL,
    package_id TEXT NOT NULL,
    apple_app_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    extracted_from TEXT NOT NULL,
    link_type TEXT NOT NULL DEFAULT 'rejected',
    confidence TEXT NOT NULL DEFAULT 'rejected',
    reject_reason TEXT NOT NULL DEFAULT '',
    normalized_store_url TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(report_date, channel_name, video_id, store_url)
);

CREATE TABLE IF NOT EXISTS game_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedupe_key TEXT NOT NULL UNIQUE,
    game_name TEXT NOT NULL,
    package_id TEXT NOT NULL,
    apple_app_id TEXT NOT NULL,
    first_seen_date TEXT NOT NULL,
    last_seen_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date TEXT NOT NULL,
    previous_date TEXT NOT NULL,
    target_date TEXT NOT NULL,
    status TEXT NOT NULL,
    channels_total INTEGER NOT NULL,
    channels_success INTEGER NOT NULL,
    channels_failed INTEGER NOT NULL,
    games_found INTEGER NOT NULL,
    report_path TEXT NOT NULL,
    error_message TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report_output_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date TEXT NOT NULL,
    output_dedupe_key TEXT NOT NULL,
    source_report_date TEXT NOT NULL,
    channel_name TEXT NOT NULL,
    game_name TEXT NOT NULL,
    normalized_game_name TEXT NOT NULL,
    store_url TEXT NOT NULL,
    package_id TEXT NOT NULL,
    apple_app_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    video_id TEXT NOT NULL,
    report_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(run_date, output_dedupe_key)
);

CREATE TABLE IF NOT EXISTS store_title_cache (
    store_url TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    cleaned_name TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_games_report_date ON games(report_date);
CREATE INDEX IF NOT EXISTS idx_games_channel_name ON games(channel_name);
CREATE INDEX IF NOT EXISTS idx_report_runs_target_date ON report_runs(target_date);
CREATE INDEX IF NOT EXISTS idx_report_output_items_run_date ON report_output_items(run_date);
CREATE INDEX IF NOT EXISTS idx_report_output_items_output_key ON report_output_items(output_dedupe_key);
"""


def connect_database(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_SQL)
    migrate_schema(connection)
    connection.commit()
    return connection


def migrate_schema(connection: sqlite3.Connection) -> None:
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(games)")}
    desired_columns = {
        "link_type": "TEXT NOT NULL DEFAULT 'rejected'",
        "confidence": "TEXT NOT NULL DEFAULT 'rejected'",
        "reject_reason": "TEXT NOT NULL DEFAULT ''",
        "normalized_store_url": "TEXT NOT NULL DEFAULT ''",
    }
    for column_name, ddl in desired_columns.items():
        if column_name not in columns:
            connection.execute(f"ALTER TABLE games ADD COLUMN {column_name} {ddl}")


def upsert_video(connection: sqlite3.Connection, video: VideoRecord) -> None:
    fetched_at = datetime.utcnow().isoformat(timespec="seconds")
    connection.execute(
        """
        INSERT INTO videos (
            channel_name, channel_id, video_id, title, description,
            published_at, published_date, url, raw_json, fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(video_id) DO UPDATE SET
            channel_name=excluded.channel_name,
            channel_id=excluded.channel_id,
            title=excluded.title,
            description=excluded.description,
            published_at=excluded.published_at,
            published_date=excluded.published_date,
            url=excluded.url,
            raw_json=excluded.raw_json,
            fetched_at=excluded.fetched_at
        """,
        (
            video.channel_name,
            video.channel_id,
            video.video_id,
            video.title,
            video.description,
            video.published_at.isoformat(),
            video.published_date.isoformat(),
            video.url,
            json.dumps(video.raw_json, ensure_ascii=False),
            fetched_at,
        ),
    )


def upsert_game(connection: sqlite3.Connection, game: ExtractedGame) -> None:
    created_at = datetime.utcnow().isoformat(timespec="seconds")
    connection.execute(
        """
        INSERT INTO games (
            report_date, channel_name, video_id, video_title, game_name,
            normalized_game_name, store_url, package_id, apple_app_id,
            platform, extracted_from, link_type, confidence, reject_reason,
            normalized_store_url, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(report_date, channel_name, video_id, store_url) DO UPDATE SET
            video_title=excluded.video_title,
            game_name=excluded.game_name,
            normalized_game_name=excluded.normalized_game_name,
            package_id=excluded.package_id,
            apple_app_id=excluded.apple_app_id,
            platform=excluded.platform,
            extracted_from=excluded.extracted_from,
            link_type=excluded.link_type,
            confidence=excluded.confidence,
            reject_reason=excluded.reject_reason,
            normalized_store_url=excluded.normalized_store_url,
            created_at=excluded.created_at
        """,
        (
            game.report_date.isoformat(),
            game.channel_name,
            game.video_id,
            game.video_title,
            game.game_name,
            game.normalized_game_name,
            game.store_url,
            game.package_id,
            game.apple_app_id,
            game.platform,
            game.extracted_from,
            game.link_type,
            game.confidence,
            game.reject_reason,
            game.normalized_store_url,
            created_at,
        ),
    )


def upsert_game_catalog(connection: sqlite3.Connection, game: ExtractedGame) -> None:
    connection.execute(
        """
        INSERT INTO game_catalog (
            dedupe_key, game_name, package_id, apple_app_id, first_seen_date, last_seen_date
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(dedupe_key) DO UPDATE SET
            game_name=excluded.game_name,
            package_id=excluded.package_id,
            apple_app_id=excluded.apple_app_id,
            last_seen_date=excluded.last_seen_date
        """,
        (
            game.dedupe_key,
            game.game_name,
            game.package_id,
            game.apple_app_id,
            game.report_date.isoformat(),
            game.report_date.isoformat(),
        ),
    )


def record_report_run(
    connection: sqlite3.Connection,
    *,
    run_date: str,
    previous_date: str,
    target_date: str,
    status: str,
    channels_total: int,
    channels_success: int,
    channels_failed: int,
    games_found: int,
    report_path: str,
    error_message: str,
) -> None:
    created_at = datetime.utcnow().isoformat(timespec="seconds")
    connection.execute(
        """
        INSERT INTO report_runs (
            run_date, previous_date, target_date, status, channels_total,
            channels_success, channels_failed, games_found, report_path,
            error_message, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_date,
            previous_date,
            target_date,
            status,
            channels_total,
            channels_success,
            channels_failed,
            games_found,
            report_path,
            error_message,
            created_at,
        ),
    )


def fetch_games_by_date(connection: sqlite3.Connection, report_date: str) -> list[sqlite3.Row]:
    return fetch_games_between_dates(connection, report_date, report_date)


def fetch_games_between_dates(
    connection: sqlite3.Connection,
    start_date: str,
    end_date: str,
) -> list[sqlite3.Row]:
    cursor = connection.execute(
        """
        SELECT
            report_date,
            channel_name,
            game_name,
            normalized_game_name,
            platform,
            store_url,
            normalized_store_url,
            package_id,
            apple_app_id,
            video_id,
            video_title,
            ('https://www.youtube.com/watch?v=' || video_id) AS video_url,
            extracted_from,
            link_type,
            confidence,
            reject_reason,
            created_at
        FROM games
        WHERE report_date BETWEEN ? AND ?
        ORDER BY report_date, channel_name, id
        """,
        (start_date, end_date),
    )
    return list(cursor.fetchall())


def fetch_latest_report_date(connection: sqlite3.Connection) -> str | None:
    row = connection.execute(
        """
        SELECT COALESCE(
            (SELECT MAX(report_date) FROM games),
            (SELECT MAX(target_date) FROM report_runs)
        ) AS report_date
        """
    ).fetchone()
    return row["report_date"] if row and row["report_date"] else None


def fetch_report_runs_before(connection: sqlite3.Connection, before_run_date: str) -> list[sqlite3.Row]:
    cursor = connection.execute(
        """
        SELECT
            run_date,
            previous_date,
            target_date,
            report_path
        FROM report_runs
        WHERE run_date < ?
        ORDER BY run_date ASC, id ASC
        """,
        (before_run_date,),
    )
    return list(cursor.fetchall())


def fetch_report_output_run_dates_before(connection: sqlite3.Connection, before_run_date: str) -> set[str]:
    cursor = connection.execute(
        "SELECT DISTINCT run_date FROM report_output_items WHERE run_date < ?",
        (before_run_date,),
    )
    return {row["run_date"] for row in cursor.fetchall()}


def fetch_historical_output_keys_before_run(connection: sqlite3.Connection, before_run_date: str) -> set[str]:
    cursor = connection.execute(
        """
        SELECT DISTINCT output_dedupe_key
        FROM report_output_items
        WHERE run_date < ?
        """,
        (before_run_date,),
    )
    return {row["output_dedupe_key"] for row in cursor.fetchall()}


def save_report_output_items(
    connection: sqlite3.Connection,
    *,
    run_date: str,
    report_path: str,
    output_rows: list[dict],
) -> None:
    created_at = datetime.utcnow().isoformat(timespec="seconds")
    for row in output_rows:
        connection.execute(
            """
            INSERT INTO report_output_items (
                run_date, output_dedupe_key, source_report_date, channel_name, game_name,
                normalized_game_name, store_url, package_id, apple_app_id, platform,
                video_id, report_path, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_date, output_dedupe_key) DO UPDATE SET
                source_report_date=excluded.source_report_date,
                channel_name=excluded.channel_name,
                game_name=excluded.game_name,
                normalized_game_name=excluded.normalized_game_name,
                store_url=excluded.store_url,
                package_id=excluded.package_id,
                apple_app_id=excluded.apple_app_id,
                platform=excluded.platform,
                video_id=excluded.video_id,
                report_path=excluded.report_path,
                created_at=excluded.created_at
            """,
            (
                run_date,
                row["output_dedupe_key"],
                row["report_date"],
                row["channel_name"],
                row["game_name"],
                row["normalized_game_name"],
                row["store_url"],
                row["package_id"],
                row["apple_app_id"],
                row["platform"],
                row["video_id"],
                report_path,
                created_at,
            ),
        )


def get_cached_store_title(connection: sqlite3.Connection, store_url: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT store_url, title, cleaned_name, fetched_at, status FROM store_title_cache WHERE store_url = ?",
        (store_url,),
    ).fetchone()


def save_store_title_cache(
    connection: sqlite3.Connection,
    store_url: str,
    title: str,
    cleaned_name: str,
    status: str,
) -> None:
    fetched_at = datetime.utcnow().isoformat(timespec="seconds")
    connection.execute(
        """
        INSERT INTO store_title_cache (store_url, title, cleaned_name, fetched_at, status)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(store_url) DO UPDATE SET
            title=excluded.title,
            cleaned_name=excluded.cleaned_name,
            fetched_at=excluded.fetched_at,
            status=excluded.status
        """,
        (store_url, title, cleaned_name, fetched_at, status),
    )
