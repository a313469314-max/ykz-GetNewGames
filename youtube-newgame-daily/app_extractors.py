from __future__ import annotations

import re
import unicodedata
from typing import Iterable
from urllib.parse import parse_qs, unquote, urlparse, urlunparse

from app_models import ExtractedGame, VideoRecord


STORE_URL_PATTERN = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
GOOGLE_PLAY_PATTERN = re.compile(r"play\.google\.com/store/apps/details", re.IGNORECASE)
APP_STORE_PATTERN = re.compile(r"apps\.apple\.com(?:/[^/\s]+)*/app(?:/[^/\s]+)?/id(\d+)", re.IGNORECASE)
STEAM_PATTERN = re.compile(r"store\.steampowered\.com/app/\d+", re.IGNORECASE)
PACKAGE_ID_PATTERN = re.compile(
    r"\b((?:com|net|org|io|co|me|games)\.[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+){1,})\b"
)
HASHTAG_PATTERN = re.compile(r"#\w+")
MARKETING_TAIL_PATTERN = re.compile(
    r"\b(gameplay|official launch|official released|official release|gift code|giftcode|redeem code|beta|demo|pre-register|coming soon)\b",
    re.IGNORECASE,
)
TRAILING_PUNCTUATION = ".,;:!?)>]}\"'"
LEADING_PUNCTUATION = "([{<\"'"
URL_REJECT_KEYWORDS = {
    "terms",
    "termsofservice",
    "tos",
    "policy",
    "privacy",
    "privacypolicy",
    "support",
    "help",
    "faq",
    "contact",
    "customer",
    "service",
    "agreement",
    "license",
    "legal",
}
TEXT_REJECT_PHRASES = [
    "官方網站",
    "官方网站",
    "官網",
    "官网",
    "服務條款",
    "服务条款",
    "隱私權政策",
    "隐私权政策",
    "隱私政策",
    "隐私政策",
    "使用條款",
    "使用条款",
    "terms of service",
    "privacy policy",
    "conditions regarding",
    "in-app purchases",
    "應用內購買",
    "应用内购买",
    "support",
    "customer service",
    "contact us",
    "discord",
    "facebook",
    "instagram",
    "youtube",
    "playstore",
    "testflight",
    "join the",
    "official website",
    "official site",
    "official homepage",
    "privacy",
    "policy",
    "service terms",
]
GENERIC_LINK_NAMES = {
    "official site",
    "official website",
    "website",
    "homepage",
    "官网",
    "官網",
    "官方网站",
    "官方網站",
    "服务条款",
    "服務條款",
    "隐私政策",
    "隱私政策",
    "隐私权政策",
    "隱私權政策",
    "support",
    "customer service",
    "contact us",
    "appstore",
    "ios app store",
    "ios",
    "playstore",
    "testflight",
}
THIRD_PARTY_STORE_DOMAINS = {
    "www.taptap.io",
    "taptap.io",
    "www.qoo-app.com",
    "qoo-app.com",
    "apkpure.com",
    "www.apkpure.com",
    "itch.io",
    "www.itch.io",
    "store.epicgames.com",
    "www.epicgames.com",
    "store.steampowered.com",
}
SOCIAL_DOMAINS = {
    "facebook.com",
    "www.facebook.com",
    "m.facebook.com",
    "instagram.com",
    "www.instagram.com",
    "x.com",
    "twitter.com",
    "www.twitter.com",
    "discord.gg",
    "discord.com",
}
REGIONAL_STORE_DOMAINS = {
    "m.onestore.co.kr",
    "onestore.co.kr",
    "appgallery.huawei.com",
    "galaxystore.samsung.com",
    "apps.samsung.com",
}
REJECT_HOSTS = {
    "terms.withhive.com",
    "support.google.com",
}
YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
}
NON_STORE_SIGNAL_WORDS = {
    "game",
    "download",
    "app",
    "pre-register",
    "preregister",
    "store",
    "campaign",
    "landing",
    "play",
    "event",
}
INVALID_NAME_PATTERNS = [
    re.compile(r"^\s*download\b", re.IGNORECASE),
    re.compile(r"\bapk\b", re.IGNORECASE),
    re.compile(r"^\s*ios\s*$", re.IGNORECASE),
    re.compile(r"^\s*android\s*$", re.IGNORECASE),
    re.compile(r"^\s*join the\b", re.IGNORECASE),
    re.compile(r"save\s+\d+%", re.IGNORECASE),
    re.compile(r"testflight", re.IGNORECASE),
    re.compile(r"下载"),
    re.compile(r"安卓版"),
    re.compile(r"儲值"),
    re.compile(r"充值"),
    re.compile(r"\d+(?:\.\d+)?\s*折"),
    re.compile(r"youtube", re.IGNORECASE),
    re.compile(r"playlist", re.IGNORECASE),
]


def extract_games_from_video(video: VideoRecord) -> list[ExtractedGame]:
    lines = [line.strip() for line in video.description.splitlines()]
    extracted: list[ExtractedGame] = []
    seen_urls: set[str] = set()

    for index, line in enumerate(lines):
        urls = [normalize_store_url(url) for url in STORE_URL_PATTERN.findall(line)]
        if not urls:
            continue

        candidate_names = build_name_candidates(lines, index, video.title)
        for raw_url in urls:
            if raw_url in seen_urls:
                continue
            seen_urls.add(raw_url)
            extracted.append(build_candidate_from_url(video, lines, index, raw_url, candidate_names))

    if extracted:
        return dedupe_games_by_store_url(extracted)

    package_games = extract_games_from_package_ids(video, lines)
    if package_games:
        return package_games

    fallback_name = fallback_game_name(video.title)
    if fallback_name:
        return [
            create_game(
                video=video,
                game_name=fallback_name,
                store_url="",
                package_id="",
                apple_app_id="",
                platform="unknown",
                extracted_from="video_title_fallback",
                link_type="rejected",
                confidence="low",
                reject_reason="missing_store_url",
            )
        ]
    return []


def build_candidate_from_url(
    video: VideoRecord,
    lines: list[str],
    line_index: int,
    store_url: str,
    candidate_names: list[str],
) -> ExtractedGame:
    classification = classify_url(store_url)
    best_name = select_best_name(candidate_names)

    if classification["reject"]:
        reject_name = best_name or fallback_game_name(video.video_title if hasattr(video, "video_title") else video.title)
        return create_game(
            video=video,
            game_name=reject_name,
            store_url=store_url,
            package_id=classification["package_id"],
            apple_app_id=classification["apple_app_id"],
            platform=classification["platform"],
            extracted_from="description_link_context",
            link_type="rejected",
            confidence="rejected",
            reject_reason=classification["reject_reason"],
        )

    name = best_name or fallback_game_name(video.title)
    if not is_valid_game_name(name):
        return create_game(
            video=video,
            game_name=name or "",
            store_url=store_url,
            package_id=classification["package_id"],
            apple_app_id=classification["apple_app_id"],
            platform=classification["platform"],
            extracted_from="description_link_context",
            link_type="rejected",
            confidence="rejected" if classification["link_type"] != "google_play" and classification["link_type"] != "app_store" else "low",
            reject_reason="invalid_game_name",
        )

    confidence = classification["base_confidence"]
    if classification["link_type"] == "non_store" and not has_non_store_context_signal(lines, line_index, name):
        confidence = "low"

    return create_game(
        video=video,
        game_name=name,
        store_url=store_url,
        package_id=classification["package_id"],
        apple_app_id=classification["apple_app_id"],
        platform=classification["platform"],
        extracted_from="description_link_context",
        link_type=classification["link_type"],
        confidence=confidence,
        reject_reason="" if confidence in {"high", "medium"} else "weak_non_store_context",
    )


def extract_games_from_package_ids(video: VideoRecord, lines: list[str]) -> list[ExtractedGame]:
    results: list[ExtractedGame] = []
    seen_packages: set[str] = set()

    for index, line in enumerate(lines):
        for package_id in find_package_ids(line):
            normalized_package = package_id.lower()
            if normalized_package in seen_packages:
                continue
            seen_packages.add(normalized_package)
            candidate_names = build_name_candidates(lines, index, video.title)
            game_name = select_best_name(candidate_names) or fallback_game_name(video.title)
            confidence = "medium" if is_valid_game_name(game_name) else "low"
            reject_reason = "" if confidence == "medium" else "invalid_game_name"
            results.append(
                create_game(
                    video=video,
                    game_name=game_name,
                    store_url=f"https://play.google.com/store/apps/details?id={normalized_package}",
                    package_id=normalized_package,
                    apple_app_id="",
                    platform="google_play",
                    extracted_from="package_id_fallback",
                    link_type="google_play",
                    confidence=confidence,
                    reject_reason=reject_reason,
                )
            )

    return results


def build_name_candidates(lines: list[str], line_index: int, video_title: str) -> list[str]:
    indices = [line_index, line_index - 1, line_index + 1, line_index - 2, line_index + 2]
    candidates: list[str] = []
    for idx in indices:
        if 0 <= idx < len(lines):
            cleaned = cleanup_name_fragment(remove_store_urls(lines[idx]))
            if cleaned:
                candidates.append(cleaned)
    fallback = fallback_game_name(video_title)
    if fallback:
        candidates.append(fallback)
    return candidates


def select_best_name(candidates: list[str]) -> str:
    for candidate in candidates:
        if is_valid_game_name(candidate):
            return candidate
    return ""


def classify_url(store_url: str) -> dict[str, str | bool]:
    parsed = urlparse(store_url)
    host = (parsed.netloc or "").casefold()
    path = (parsed.path or "").casefold()
    query = (parsed.query or "").casefold()
    full_text = " ".join(part for part in [host, path, query] if part)

    if host in YOUTUBE_HOSTS:
        return rejected_url_classification(store_url, host, path, "youtube_internal_url")

    if any(keyword in full_text for keyword in URL_REJECT_KEYWORDS) or host in REJECT_HOSTS:
        return rejected_url_classification(store_url, host, path)

    if GOOGLE_PLAY_PATTERN.search(store_url):
        package_id = (parse_qs(parsed.query).get("id") or [""])[0].strip().lower()
        return {
            "platform": "google_play",
            "link_type": "google_play",
            "package_id": package_id,
            "apple_app_id": "",
            "base_confidence": "high",
            "reject": False,
            "reject_reason": "",
        }

    app_store_match = APP_STORE_PATTERN.search(store_url)
    if app_store_match:
        return {
            "platform": "app_store",
            "link_type": "app_store",
            "package_id": "",
            "apple_app_id": app_store_match.group(1),
            "base_confidence": "high",
            "reject": False,
            "reject_reason": "",
        }

    if STEAM_PATTERN.search(store_url):
        return non_store_classification("steam")

    if host in THIRD_PARTY_STORE_DOMAINS:
        if looks_like_landing_page(parsed):
            return low_confidence_non_store_classification("landing_page")
        return non_store_classification("third_party_store")

    if host in REGIONAL_STORE_DOMAINS:
        return non_store_classification("regional_store")

    if host in SOCIAL_DOMAINS:
        return low_confidence_non_store_classification("other")

    if is_homepage(parsed):
        return low_confidence_non_store_classification("official_site")

    if looks_like_landing_page(parsed):
        return low_confidence_non_store_classification("landing_page")

    if looks_like_candidate_non_store(parsed):
        return non_store_classification("official_site")

    return low_confidence_non_store_classification("other")


def rejected_url_classification(store_url: str, host: str, path: str, reason: str = "rejected_url") -> dict[str, str | bool]:
    normalized = f"{host}{path}"
    if reason == "rejected_url" and ("privacy" in normalized or "policy" in normalized):
        reason = "privacy_or_policy_url"
    elif reason == "rejected_url" and ("terms" in normalized or "tos" in normalized or "agreement" in normalized or "license" in normalized):
        reason = "terms_or_legal_url"
    elif reason == "rejected_url" and any(token in normalized for token in ["support", "help", "faq", "contact", "customer", "service"]):
        reason = "support_or_help_url"
    return {
        "platform": "rejected",
        "link_type": "rejected",
        "package_id": "",
        "apple_app_id": "",
        "base_confidence": "rejected",
        "reject": True,
        "reject_reason": reason,
    }


def non_store_classification(platform: str) -> dict[str, str | bool]:
    return {
        "platform": platform,
        "link_type": "non_store",
        "package_id": "",
        "apple_app_id": "",
        "base_confidence": "medium",
        "reject": False,
        "reject_reason": "",
    }


def low_confidence_non_store_classification(platform: str) -> dict[str, str | bool]:
    classification = non_store_classification(platform)
    classification["base_confidence"] = "low"
    return classification


def normalize_store_url(url: str) -> str:
    cleaned = url.strip().rstrip(TRAILING_PUNCTUATION).lstrip(LEADING_PUNCTUATION).replace("&amp;", "&")
    parsed = urlparse(cleaned)
    normalized_host = (parsed.netloc or "").casefold()
    normalized_path = parsed.path or "/"
    normalized_query = parsed.query
    return urlunparse((parsed.scheme.lower() or "https", normalized_host, normalized_path, "", normalized_query, ""))


def normalize_non_store_url(url: str) -> str:
    parsed = urlparse(url)
    normalized_host = (parsed.netloc or "").casefold()
    normalized_path = re.sub(r"/+", "/", parsed.path or "/").rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower() or "https", normalized_host, normalized_path, "", "", ""))


def remove_store_urls(text: str) -> str:
    return STORE_URL_PATTERN.sub("", text).strip(" -|:：•*")


def fallback_game_name(video_title: str) -> str:
    title = strip_hashtags_and_emoji(video_title)
    title = re.sub(r"\b(?:android|ios|apk)\b", "", title, flags=re.IGNORECASE)
    title = MARKETING_TAIL_PATTERN.sub("", title)
    title = re.sub(r"\s{2,}", " ", title).strip(" -|:：•*")
    title = cleanup_name_fragment(title)
    if not is_valid_game_name(title):
        return ""
    return title


def strip_hashtags_and_emoji(text: str) -> str:
    text = HASHTAG_PATTERN.sub("", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "So")
    return text


def cleanup_name_fragment(text: str) -> str:
    text = strip_hashtags_and_emoji(text)
    text = re.sub(r"\[[^\]]+\]|\([^\)]*\)", "", text)
    text = re.sub(r"\s*-\s*Google Play 上的应用\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*-\s*Apps on Google Play\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*-\s*App Store\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[_\-]{4,}", " ", text)
    text = re.sub(r"[|｜]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" -|:：•*")


def is_valid_game_name(value: str) -> bool:
    if not value:
        return False
    stripped = value.strip()
    if len(stripped) < 2:
        return False
    if len(stripped) > 80:
        return False
    if re.fullmatch(r"[_\-\s=~.]+", stripped):
        return False
    lowered = stripped.casefold()
    if lowered in {item.casefold() for item in GENERIC_LINK_NAMES}:
        return False
    if any(phrase.casefold() in lowered for phrase in TEXT_REJECT_PHRASES):
        return False
    if any(pattern.search(stripped) for pattern in INVALID_NAME_PATTERNS):
        return False
    if looks_like_sentence(stripped):
        return False
    return True


def looks_like_sentence(value: str) -> bool:
    lowered = value.casefold()
    sentence_markers = [
        "regarding",
        "can be viewed",
        "for more information",
        "please refer",
        "please check",
        "follow our",
        "in the game",
        "customer support",
        "privacy policy",
        "terms of service",
    ]
    if any(marker in lowered for marker in sentence_markers):
        return True
    if len(lowered.split()) >= 10 and lowered.endswith("."):
        return True
    if len(value) >= 24 and any(mark in value for mark in "。！？"):
        return True
    return False


def find_package_ids(text: str) -> list[str]:
    matches = []
    for match in PACKAGE_ID_PATTERN.findall(text or ""):
        lowered = match.lower()
        if lowered.startswith(("youtube.com", "www.youtube.", "play.google.", "apps.apple.")):
            continue
        matches.append(match)
    return matches


def normalize_game_name(name: str) -> str:
    lowered = name.casefold()
    lowered = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", lowered)
    return lowered


def dedupe_games_by_store_url(games: Iterable[ExtractedGame]) -> list[ExtractedGame]:
    unique: dict[str, ExtractedGame] = {}
    for game in games:
        key = game.normalized_store_url or game.store_url or f"title:{game.video_id}:{game.normalized_game_name}"
        unique.setdefault(key, game)
    return list(unique.values())


def looks_like_candidate_non_store(parsed_url) -> bool:
    host = (parsed_url.netloc or "").casefold()
    path = (parsed_url.path or "").casefold()
    query = (parsed_url.query or "").casefold()
    full_text = f"{host} {path} {query}"
    return any(signal in full_text for signal in NON_STORE_SIGNAL_WORDS) or host in THIRD_PARTY_STORE_DOMAINS


def looks_like_landing_page(parsed_url) -> bool:
    path = (parsed_url.path or "").casefold()
    query = (parsed_url.query or "").casefold()
    return any(token in path for token in ["/down", "/download", "/landing", "/event"]) or any(
        token in query for token in ["tgid=", "gid=", "redirect=", "target=", "url="]
    )


def is_homepage(parsed_url) -> bool:
    return (parsed_url.path or "/") in {"", "/"} and not parsed_url.query


def has_non_store_context_signal(lines: list[str], line_index: int, game_name: str) -> bool:
    context = " ".join(
        lines[idx]
        for idx in range(max(0, line_index - 1), min(len(lines), line_index + 2))
    ).casefold()
    if game_name and game_name.casefold() in context:
        return True
    return any(signal in context for signal in ["game", "android", "ios", "official", "launch", "download", "play"])


def create_game(
    *,
    video: VideoRecord,
    game_name: str,
    store_url: str,
    package_id: str,
    apple_app_id: str,
    platform: str,
    extracted_from: str,
    link_type: str,
    confidence: str,
    reject_reason: str,
) -> ExtractedGame:
    safe_name = game_name or ""
    normalized_store_url = normalize_non_store_url(store_url) if store_url else ""
    return ExtractedGame(
        report_date=video.published_date,
        channel_name=video.channel_name,
        video_id=video.video_id,
        video_title=video.title,
        game_name=safe_name,
        normalized_game_name=normalize_game_name(safe_name),
        store_url=store_url,
        package_id=package_id,
        apple_app_id=apple_app_id,
        platform=platform,
        extracted_from=extracted_from,
        link_type=link_type,
        confidence=confidence,
        reject_reason=reject_reason,
        normalized_store_url=normalized_store_url,
    )
