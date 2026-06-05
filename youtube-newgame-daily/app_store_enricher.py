from __future__ import annotations

import html
import logging
import re
import time
from typing import Iterable
from urllib.parse import unquote, urlparse

import requests

from app_extractors import cleanup_name_fragment, is_valid_game_name, normalize_game_name
from app_models import ExtractedGame
from app_storage import get_cached_store_title, save_store_title_cache


LOGGER = logging.getLogger(__name__)
TITLE_PATTERN = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
META_TAG_PATTERN = re.compile(r"<meta\b[^>]*>", re.IGNORECASE | re.DOTALL)
META_ATTR_PATTERN = re.compile(r"""([:\w-]+)\s*=\s*(['"])(.*?)\2""", re.IGNORECASE | re.DOTALL)
OFFICIAL_STORE_LINK_TYPES = {"google_play", "app_store"}
TITLE_REQUIRED_STORE_PLATFORMS = {"google_play", "app_store", "steam", "third_party_store", "regional_store"}
CONTEXT_NAME_SOURCES = {"description_link_context", "package_id_context"}
TITLE_CLEANUPS = [
    re.compile(r"^[\u200e\u200f\s]+"),
    re.compile(r"\s*-\s*Apps on Google Play\s*$", re.IGNORECASE),
    re.compile(r"\s*-\s*Google Play 上的应用\s*$", re.IGNORECASE),
    re.compile(r"\s*-\s*Google Play上的应用\s*$", re.IGNORECASE),
    re.compile(r"\s*-\s*Google Play のアプリ\s*$", re.IGNORECASE),
    re.compile(r"\s*-\s*App Store\s*$", re.IGNORECASE),
    re.compile(r"\s*on the App Store\s*$", re.IGNORECASE),
    re.compile(r"\s+App\s*$", re.IGNORECASE),
    re.compile(r"\s*-\s*(?:安卓|Android|iOS|苹果)?官方(?:预约|下載|下载)\s*-\s*TapTap\s*$", re.IGNORECASE),
    re.compile(r"\s*-\s*TapTap\s*$", re.IGNORECASE),
    re.compile(r"\s*(?:安卓|Android)(?:版)?(?:游戏|遊戲)?APK(?:下載|下载)\s*$", re.IGNORECASE),
    re.compile(r"\s*APK(?:下載|下载)\s*$", re.IGNORECASE),
    re.compile(r"\s+Old Versions APK Download\s*$", re.IGNORECASE),
    re.compile(r"\s+APK(?:s)?(?: for Android)? Download\s*$", re.IGNORECASE),
    re.compile(r"\s+APK(?: for Android)?\s*$", re.IGNORECASE),
    re.compile(r"\s*-\s*Official Site\s*$", re.IGNORECASE),
    re.compile(r"\s*-\s*Official Website\s*$", re.IGNORECASE),
    re.compile(r"\s*-\s*Apple\s*$", re.IGNORECASE),
]
TITLE_REJECT_WORDS = {
    "terms",
    "privacy",
    "policy",
    "support",
    "help",
    "faq",
    "contact",
    "customer service",
    "terms of service",
    "privacy policy",
}
GENERIC_STORE_TITLE_WORDS = {
    "today",
    "iphone",
    "ipad",
    "app store",
    "appstore",
    "playstore",
    "google play",
    "ios app store",
    "ios",
    "testflight",
}


class AppStoreEnricher:
    def __init__(self, connection, timeout_seconds: int = 20, retry_count: int = 3) -> None:
        self.connection = connection
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0 Safari/537.36"
                )
            }
        )

    def enrich_games(self, games: Iterable[ExtractedGame]) -> list[ExtractedGame]:
        return [self.enrich_game(game) for game in games]

    def enrich_game(self, game: ExtractedGame) -> ExtractedGame:
        if not game.store_url:
            return game

        cached = get_cached_store_title(self.connection, game.store_url)
        if cached and not should_retry_cached_title(game, cached["status"]):
            title, cleaned_name, status = normalize_cached_title_result(cached)
            if (
                title != cached["title"]
                or cleaned_name != cached["cleaned_name"]
                or status != cached["status"]
            ):
                save_store_title_cache(self.connection, game.store_url, title, cleaned_name, status)
            return apply_cached_title_result(game, cleaned_name, status)

        title, cleaned_name, status = self._fetch_page_title(
            game.store_url,
            game.game_name,
            allow_fallback=not is_title_required_store_link(game),
        )
        save_store_title_cache(self.connection, game.store_url, title, cleaned_name, status)
        return apply_cached_title_result(game, cleaned_name, status)

    def _fetch_page_title(
        self,
        store_url: str,
        fallback_name: str,
        *,
        allow_fallback: bool = True,
    ) -> tuple[str, str, str]:
        last_error: Exception | None = None
        for attempt in range(1, self.retry_count + 2):
            try:
                response = self.session.get(store_url, timeout=self.timeout_seconds)
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise requests.HTTPError(f"Retryable status code {response.status_code}", response=response)
                response.raise_for_status()
                html_text = decode_response_text(response)
                title = extract_html_title(html_text)
                cleaned_name = clean_page_title(title)
                if not cleaned_name and allow_fallback:
                    cleaned_name = derive_name_from_url(store_url) or fallback_name
                if not cleaned_name:
                    return title, "", "failed"
                if is_generic_store_title(cleaned_name):
                    return title, "", "failed"
                if is_reject_title(cleaned_name):
                    return title, cleaned_name, "rejected"
                return title, cleaned_name, "ok"
            except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
                last_error = exc
                response = getattr(exc, "response", None)
                retryable = response is None or response.status_code in {429, 500, 502, 503, 504}
                if attempt > self.retry_count or not retryable:
                    break
                LOGGER.warning("Store title fetch failed (attempt %s/%s): %s", attempt, self.retry_count + 1, exc)
                time.sleep(min(2 ** (attempt - 1), 8))
            except Exception as exc:  # pragma: no cover
                last_error = exc
                break

        LOGGER.warning("Store title fetch skipped for %s: %s", store_url, last_error)
        return "", "", "failed"


def apply_cached_title_result(game: ExtractedGame, cleaned_name: str, status: str) -> ExtractedGame:
    if status == "rejected":
        game.confidence = "rejected"
        game.link_type = "rejected"
        game.reject_reason = "page_title_rejected"
        return game

    if status == "ok" and cleaned_name and is_valid_game_name(cleaned_name):
        game.game_name = cleaned_name
        game.normalized_game_name = normalize_game_name(cleaned_name)
        if is_title_required_store_link(game):
            game.extracted_from = "store_page_title"
            game.confidence = "high"
            game.reject_reason = ""
            return game
        if game.link_type == "non_store" and game.confidence == "low":
            if game.platform in {"third_party_store", "regional_store", "landing_page", "steam"}:
                game.confidence = "medium"
                game.reject_reason = ""
            elif game.platform == "official_site" and not is_homepage_url(game.store_url):
                game.confidence = "medium"
                game.reject_reason = ""
        return game

    if is_title_required_store_link(game):
        if game.extracted_from in CONTEXT_NAME_SOURCES and is_valid_game_name(game.game_name):
            game.confidence = "medium"
            game.reject_reason = "store_title_unavailable_context_fallback"
            return game
        game.confidence = "rejected"
        game.link_type = "rejected"
        game.reject_reason = "store_title_required"
        return game

    if not is_valid_game_name(game.game_name):
        game.confidence = "rejected"
        game.link_type = "rejected"
        game.reject_reason = game.reject_reason or "invalid_game_name"
    return game


def extract_html_title(html_text: str) -> str:
    og_title = extract_og_title(html_text)
    if og_title:
        return og_title
    match = TITLE_PATTERN.search(html_text)
    return html.unescape(match.group(1).strip()) if match else ""


def extract_og_title(html_text: str) -> str:
    for tag in META_TAG_PATTERN.findall(html_text):
        attrs = {
            name.casefold(): html.unescape(value.strip())
            for name, _quote, value in META_ATTR_PATTERN.findall(tag)
        }
        title_type = (attrs.get("property") or attrs.get("name") or "").casefold()
        if title_type == "og:title" and attrs.get("content"):
            return attrs["content"]
    return ""


def clean_page_title(title: str) -> str:
    cleaned = title
    for pattern in TITLE_CLEANUPS:
        cleaned = pattern.sub("", cleaned)
    cleaned = cleanup_name_fragment(cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip(" -|:：")


def decode_response_text(response: requests.Response) -> str:
    try:
        return response.content.decode("utf-8")
    except UnicodeDecodeError:
        if response.apparent_encoding:
            return response.content.decode(response.apparent_encoding, errors="replace")
        return response.text


def derive_name_from_url(store_url: str) -> str:
    parsed = urlparse(store_url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    for segment in reversed(segments):
        if segment.startswith("id"):
            continue
        if len(segment) <= 2:
            continue
        return cleanup_name_fragment(unquote(segment).replace("-", " "))
    return ""


def is_reject_title(value: str) -> bool:
    lowered = value.casefold()
    return any(word in lowered for word in TITLE_REJECT_WORDS)


def is_generic_store_title(value: str) -> bool:
    lowered = value.casefold()
    return any(word in lowered for word in GENERIC_STORE_TITLE_WORDS)


def is_homepage_url(url: str) -> bool:
    parsed = urlparse(url)
    return (parsed.path or "/") in {"", "/"} and not parsed.query


def is_official_store_link(game: ExtractedGame) -> bool:
    return game.link_type in OFFICIAL_STORE_LINK_TYPES or game.platform in OFFICIAL_STORE_LINK_TYPES


def is_title_required_store_link(game: ExtractedGame) -> bool:
    return is_official_store_link(game) or game.platform in TITLE_REQUIRED_STORE_PLATFORMS


def should_retry_cached_title(game: ExtractedGame, status: str) -> bool:
    return is_title_required_store_link(game) and status == "failed"


def normalize_cached_title_result(cached) -> tuple[str, str, str]:
    title = cached["title"]
    status = cached["status"]
    cleaned_name = clean_page_title(title) if title else cached["cleaned_name"]

    if cleaned_name:
        if is_generic_store_title(cleaned_name):
            return title, "", "failed"
        if is_reject_title(cleaned_name):
            return title, cleaned_name, "rejected"
        return title, cleaned_name, "ok"

    return title, "", status
