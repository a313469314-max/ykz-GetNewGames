from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests


LOGGER = logging.getLogger(__name__)
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
HANDLE_PATTERN = re.compile(r"youtube\.com/@([A-Za-z0-9._-]+)", re.IGNORECASE)
CHANNEL_ID_PATTERN = re.compile(r"youtube\.com/channel/([A-Za-z0-9_-]+)", re.IGNORECASE)


class YoutubeApiError(RuntimeError):
    pass


class YoutubeClient:
    def __init__(self, api_key: str, timeout_seconds: int = 20, retry_count: int = 3) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count
        self.session = requests.Session()

    def resolve_channel_id(self, channel_url: str, existing_channel_id: str = "") -> str:
        if existing_channel_id:
            return existing_channel_id

        parsed = urlparse(channel_url)
        query = parse_qs(parsed.query)

        channel_id_match = CHANNEL_ID_PATTERN.search(channel_url)
        if channel_id_match:
            return channel_id_match.group(1)

        if "channel_id" in query and query["channel_id"]:
            return query["channel_id"][0]

        handle_match = HANDLE_PATTERN.search(channel_url)
        if handle_match:
            handle = handle_match.group(1)
            data = self._request_json(
                "/channels",
                {
                    "part": "id",
                    "forHandle": handle,
                    "maxResults": 1,
                },
            )
            items = data.get("items", [])
            if items:
                return items[0]["id"]
            raise YoutubeApiError(f"Unable to resolve channel handle @{handle}")

        raise YoutubeApiError(f"Unsupported channel URL format: {channel_url}")

    def get_uploads_playlist_id(self, channel_id: str) -> str:
        data = self._request_json(
            "/channels",
            {
                "part": "contentDetails",
                "id": channel_id,
                "maxResults": 1,
            },
        )
        items = data.get("items", [])
        if not items:
            raise YoutubeApiError(f"Channel not found: {channel_id}")
        return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    def list_video_ids_in_window(self, uploads_playlist_id: str, start_utc: datetime, end_utc: datetime) -> list[str]:
        video_ids: list[str] = []
        next_page_token = ""
        should_stop = False

        while True:
            params: dict[str, Any] = {
                "part": "snippet,contentDetails",
                "playlistId": uploads_playlist_id,
                "maxResults": 50,
            }
            if next_page_token:
                params["pageToken"] = next_page_token

            data = self._request_json("/playlistItems", params)
            items = data.get("items", [])
            if not items:
                break

            for item in items:
                published_at = parse_youtube_datetime(
                    item.get("contentDetails", {}).get("videoPublishedAt")
                    or item.get("snippet", {}).get("publishedAt")
                )
                if published_at < start_utc:
                    should_stop = True
                    continue
                if start_utc <= published_at < end_utc:
                    video_id = item.get("contentDetails", {}).get("videoId")
                    if video_id:
                        video_ids.append(video_id)

            if should_stop:
                break

            next_page_token = data.get("nextPageToken", "")
            if not next_page_token:
                break

        return list(dict.fromkeys(video_ids))

    def get_video_details(self, video_ids: list[str]) -> list[dict[str, Any]]:
        if not video_ids:
            return []

        details: list[dict[str, Any]] = []
        for index in range(0, len(video_ids), 50):
            chunk = video_ids[index : index + 50]
            data = self._request_json(
                "/videos",
                {
                    "part": "snippet,contentDetails,status",
                    "id": ",".join(chunk),
                    "maxResults": len(chunk),
                },
            )
            details.extend(data.get("items", []))
        return details

    def _request_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise YoutubeApiError("Missing YouTube API key")

        params = dict(params)
        params["key"] = self.api_key
        url = f"{YOUTUBE_API_BASE}{path}"
        last_error: Exception | None = None

        for attempt in range(1, self.retry_count + 2):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout_seconds)
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise requests.HTTPError(f"Retryable status code {response.status_code}", response=response)
                response.raise_for_status()
                return response.json()
            except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
                last_error = exc
                response = getattr(exc, "response", None)
                retryable = response is None or response.status_code in {429, 500, 502, 503, 504}
                if attempt > self.retry_count + 1 or not retryable:
                    break
                sleep_seconds = min(2 ** (attempt - 1), 8)
                LOGGER.warning("YouTube API request failed (attempt %s/%s): %s", attempt, self.retry_count + 1, exc)
                time.sleep(sleep_seconds)

        raise YoutubeApiError(f"YouTube API request failed: {last_error}") from last_error


def parse_youtube_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
