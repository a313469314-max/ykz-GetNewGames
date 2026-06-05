from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urljoin


DATAEYE_ORIGIN = "https://oversea-v2.dataeye.com"

FACEBOOK_MEDIA_KEYWORDS = (
    "facebook",
    "instagram",
    "messenger",
    "audience network",
    "facebookaudience",
    "meta audience",
)


def absolute_dataeye_url(value: str | None) -> str:
    if not value:
        return ""
    return urljoin(DATAEYE_ORIGIN, value)


def extract_product_id_from_url(value: str | None) -> str:
    if not value:
        return ""
    match = re.search(r"/product/(\d+)", value)
    return match.group(1) if match else ""


def normalize_media_name(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("mediaName", "media_name", "name", "platform", "channel"):
            if value.get(key):
                return str(value[key]).strip()
        return " ".join(str(v) for v in value.values() if isinstance(v, (str, int)))
    return str(value or "").strip()


def has_facebook_media(media_list: Any, extra_text: str = "") -> bool:
    values: list[str] = []
    if isinstance(media_list, str):
        values.append(media_list)
    elif isinstance(media_list, list):
        values.extend(normalize_media_name(item) for item in media_list)
    elif media_list:
        values.append(normalize_media_name(media_list))
    if extra_text:
        values.append(extra_text)
    haystack = " ".join(values).lower().replace(" ", "")
    return any(keyword.replace(" ", "") in haystack for keyword in FACEBOOK_MEDIA_KEYWORDS)


def safe_page_text(page: Any, limit: int = 120_000) -> str:
    try:
        text = page.locator("body").inner_text(timeout=5_000)
    except Exception:
        return ""
    return text[:limit]


def wait_for_any_text(page: Any, texts: list[str], timeout_ms: int = 15_000) -> bool:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        body = safe_page_text(page)
        title = ""
        try:
            title = page.title()
        except Exception:
            pass
        if any(text and (text in body or text in title) for text in texts):
            return True
        page.wait_for_timeout(500)
    return False


def try_click_text(page: Any, texts: list[str], timeout_ms: int = 2_000) -> bool:
    for text in texts:
        for exact in (True, False):
            try:
                locator = page.get_by_text(text, exact=exact).first
                if locator.count() and locator.is_visible(timeout=timeout_ms):
                    locator.click(timeout=timeout_ms)
                    return True
            except Exception:
                continue
    return False


def scroll_to_load(page: Any, steps: int = 6, pause_ms: int = 500) -> None:
    for _ in range(steps):
        try:
            page.mouse.wheel(0, 2200)
        except Exception:
            try:
                page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            except Exception:
                return
        page.wait_for_timeout(pause_ms)


def collect_product_links(page: Any) -> list[dict[str, str]]:
    try:
        rows = page.evaluate(
            """
            () => Array.from(document.querySelectorAll('a[href*="/product/"]'))
              .map((a) => ({
                url: a.href,
                text: (a.innerText || a.textContent || '').trim()
              }))
              .filter((row) => row.url)
            """
        )
    except Exception:
        return []

    seen: set[str] = set()
    products: list[dict[str, str]] = []
    for row in rows:
        url = absolute_dataeye_url(row.get("url", ""))
        product_id = extract_product_id_from_url(url)
        key = product_id or url
        if not key or key in seen:
            continue
        seen.add(key)
        text = row.get("text", "").strip()
        first_line = text.splitlines()[0].strip() if text.splitlines() else ""
        products.append(
            {
                "product_id": product_id,
                "product_name": first_line,
                "dataeye_url": url,
                "source": "dataeye_dom",
            }
        )
    return products
