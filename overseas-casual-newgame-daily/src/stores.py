from __future__ import annotations

import re
from html import unescape
from typing import Any
from urllib.parse import parse_qs, urlparse


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)


def domain_from_url(value: str | None) -> str:
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def parse_store_identity(store_url: str | None) -> dict[str, str]:
    if not store_url:
        return {}
    parsed = urlparse(store_url)
    host = parsed.netloc.lower()
    result: dict[str, str] = {"store_url": store_url}
    if "play.google.com" in host:
        package = parse_qs(parsed.query).get("id", [""])[0]
        if package:
            result.update({"store_type": "google_play", "package": package, "package_name": package})
    elif "apps.apple.com" in host:
        match = re.search(r"/id(\d+)", parsed.path)
        if match:
            result.update({"store_type": "app_store", "app_id": match.group(1)})
    return result


def _http_get(url: str, timeout: int = 15) -> str:
    import requests

    response = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.text


def enrich_google_play(store_url: str) -> dict[str, str]:
    result = parse_store_identity(store_url)
    if not result.get("package"):
        return result

    try:
        html = _http_get(store_url)
    except Exception as exc:
        result["store_enrich_error"] = str(exc)
        return result

    dev_match = re.search(r'href="(/store/apps/dev\?id=[^"]+|/store/apps/developer\?id=[^"]+)"[^>]*>(.*?)</a>', html)
    if dev_match:
        developer_name = re.sub("<.*?>", "", unescape(dev_match.group(2))).strip()
        developer_href = unescape(dev_match.group(1))
        result["developer_name"] = developer_name
        parsed = urlparse(developer_href)
        query = parse_qs(parsed.query)
        result["google_developer_id"] = query.get("id", [""])[0]
        result["developer_id"] = result["google_developer_id"]

    website_match = re.search(r'https?://[^"\']+', html)
    if website_match:
        result.setdefault("developer_website", website_match.group(0))
        result.setdefault("developer_domain", domain_from_url(website_match.group(0)))

    privacy_match = re.search(r'https?://[^"\']*(?:privacy|policy)[^"\']*', html, flags=re.I)
    if privacy_match:
        result["privacy_url"] = privacy_match.group(0)
        result["privacy_domain"] = domain_from_url(privacy_match.group(0))

    return result


def enrich_app_store(store_url: str) -> dict[str, str]:
    result = parse_store_identity(store_url)
    app_id = result.get("app_id")
    if not app_id:
        return result

    try:
        import requests

        response = requests.get("https://itunes.apple.com/lookup", params={"id": app_id}, timeout=15)
        response.raise_for_status()
        payload = response.json()
        first = (payload.get("results") or [{}])[0]
    except Exception as exc:
        result["store_enrich_error"] = str(exc)
        return result

    field_map = {
        "sellerName": "seller_name",
        "artistName": "developer_name",
        "artistId": "apple_artist_id",
        "sellerUrl": "seller_url",
        "privacyPolicyUrl": "privacy_url",
        "trackViewUrl": "store_url",
        "bundleId": "package",
    }
    for source, target in field_map.items():
        if first.get(source):
            result[target] = str(first[source])
    if result.get("seller_url"):
        result["seller_domain"] = domain_from_url(result["seller_url"])
    if result.get("privacy_url"):
        result["privacy_domain"] = domain_from_url(result["privacy_url"])
    return result


def enrich_store(product: dict[str, Any]) -> dict[str, Any]:
    store_url = product.get("store_url") or product.get("app_store_url") or ""
    if not store_url:
        return product
    identity = parse_store_identity(store_url)
    if identity.get("store_type") == "google_play":
        identity.update(enrich_google_play(store_url))
    elif identity.get("store_type") == "app_store":
        identity.update(enrich_app_store(store_url))
    product.update({k: v for k, v in identity.items() if v})
    return product
