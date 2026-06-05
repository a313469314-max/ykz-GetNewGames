from __future__ import annotations

import json
import re
import time
from collections.abc import Iterable
from datetime import date
from typing import Any
from urllib.parse import parse_qs, urlparse

from .dataeye_browser import (
    absolute_dataeye_url,
    collect_product_links,
    extract_product_id_from_url,
    has_facebook_media,
    safe_page_text,
    scroll_to_load,
    try_click_text,
)
from .dates import dataeye_date_labels, format_date
from .stores import parse_store_identity


PRODUCT_ID_KEYS = ("productId", "product_id", "id", "productID")
PRODUCT_NAME_KEYS = ("productName", "product_name", "name", "title", "appName", "app_name")
STORE_URL_KEYS = ("storeUrl", "store_url", "appStoreUrl", "app_store_url", "downloadUrl", "download_url")
PACKAGE_KEYS = ("packageName", "package_name", "package", "bundleId", "bundle_id")
APP_ID_KEYS = ("appId", "app_id", "trackId", "track_id")
COMPANY_NAME_KEYS = ("companyName", "company_name", "developerName", "developer_name", "publisherName")
COMPANY_ID_KEYS = ("companyId", "company_id", "dataeyeCompanyId", "dataeye_company_id")
FIRST_SEEN_KEYS = ("firstSeenDate", "first_seen_date", "firstFindDate", "first_find_date", "statDate", "stat_date")
MEDIA_KEYS = ("mediaList", "media_list", "medias", "media", "platforms", "channels")


class DataEyeExtractor:
    def __init__(self, page: Any, stat_date: date, max_products: int | None = None) -> None:
        self.page = page
        self.stat_date = stat_date
        self.max_products = max_products
        self._api_products: list[dict[str, Any]] = []
        self._seen_response_ids: set[int] = set()

    def attach_response_listener(self) -> None:
        def handle_response(response: Any) -> None:
            try:
                url = response.url.lower()
                if not any(token in url for token in ("newproduct", "product", "material")):
                    return
                response_id = id(response)
                if response_id in self._seen_response_ids:
                    return
                self._seen_response_ids.add(response_id)
                content_type = response.headers.get("content-type", "")
                if "json" not in content_type.lower():
                    return
                payload = response.json()
                self._api_products.extend(extract_products_from_payload(payload, self.stat_date))
            except Exception:
                return

        self.page.on("response", handle_response)

    def extract(self) -> list[dict[str, Any]]:
        self.attach_response_listener()
        self._open_new_product_view()
        scroll_to_load(self.page)
        candidates = merge_products(self._api_products, collect_product_links(self.page))
        if self.max_products:
            candidates = candidates[: self.max_products]

        detailed: list[dict[str, Any]] = []
        for candidate in candidates:
            detail = dict(candidate)
            dataeye_url = detail.get("dataeye_url") or ""
            if dataeye_url:
                try:
                    detail.update(extract_product_detail(self.page, dataeye_url, self.stat_date))
                except Exception as exc:
                    detail["detail_error"] = str(exc)
            detail.setdefault("first_seen_date", format_date(self.stat_date))
            detailed.append(detail)
        return merge_products(detailed)

    def _open_new_product_view(self) -> None:
        self.page.goto(self.page.url or "https://oversea-v2.dataeye.com/dashboard/home", wait_until="domcontentloaded")
        try:
            self.page.wait_for_load_state("networkidle", timeout=12_000)
        except Exception:
            pass
        try_click_text(self.page, ["新品发现", "New Products", "New Product"])
        self.page.wait_for_timeout(1_000)

        for label in dataeye_date_labels(self.stat_date):
            if try_click_text(self.page, [label], timeout_ms=1_000):
                break
        try:
            self.page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            self.page.wait_for_timeout(2_000)


def first_value(row: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if row.get(key) not in (None, ""):
            return row[key]
    return ""


def normalize_api_product(row: dict[str, Any], stat_date: date) -> dict[str, Any]:
    product: dict[str, Any] = {
        "product_id": str(first_value(row, PRODUCT_ID_KEYS) or ""),
        "product_name": str(first_value(row, PRODUCT_NAME_KEYS) or ""),
        "store_url": str(first_value(row, STORE_URL_KEYS) or ""),
        "package": str(first_value(row, PACKAGE_KEYS) or ""),
        "app_id": str(first_value(row, APP_ID_KEYS) or ""),
        "dataeye_company_name": str(first_value(row, COMPANY_NAME_KEYS) or ""),
        "dataeye_company_id": str(first_value(row, COMPANY_ID_KEYS) or ""),
        "first_seen_date": str(first_value(row, FIRST_SEEN_KEYS) or format_date(stat_date)),
        "media_list": first_value(row, MEDIA_KEYS) or [],
        "source": "dataeye_api",
    }
    detail_path = row.get("productUrl") or row.get("product_url") or row.get("detailUrl") or row.get("detail_url")
    if detail_path:
        product["dataeye_url"] = absolute_dataeye_url(str(detail_path))
    elif product["product_id"]:
        product["dataeye_url"] = f"https://oversea-v2.dataeye.com/product/{product['product_id']}?type=2&isPlaylet=false"
    if product["store_url"]:
        product.update(parse_store_identity(product["store_url"]))
    return {key: value for key, value in product.items() if value not in ("", [], None)}


def looks_like_product(row: dict[str, Any]) -> bool:
    has_id = any(row.get(key) for key in PRODUCT_ID_KEYS)
    has_name = any(row.get(key) for key in PRODUCT_NAME_KEYS)
    return bool(has_id and has_name)


def extract_products_from_payload(payload: Any, stat_date: date) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if looks_like_product(value):
                products.append(normalize_api_product(value, stat_date))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    return merge_products(products)


def merge_products(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for group in groups:
        for row in group:
            key = row.get("package") or row.get("package_name") or row.get("app_id") or row.get("product_id") or row.get("dataeye_url")
            if not key:
                key = json.dumps(row, sort_keys=True, ensure_ascii=False)
            if key not in merged:
                merged[key] = {}
                order.append(key)
            merged[key].update({k: v for k, v in row.items() if v not in ("", [], None)})
    return [merged[key] for key in order]


def _extract_store_links(page: Any) -> list[str]:
    try:
        return page.evaluate(
            """
            () => Array.from(document.querySelectorAll('a[href]'))
              .map((a) => a.href)
              .filter((href) => href.includes('play.google.com/store/apps/details') || href.includes('apps.apple.com'))
            """
        )
    except Exception:
        return []


def _extract_external_links(page: Any) -> list[str]:
    try:
        return page.evaluate(
            """
            () => Array.from(document.querySelectorAll('a[href]'))
              .map((a) => a.href)
              .filter((href) => /^https?:/.test(href))
            """
        )
    except Exception:
        return []


def _extract_name(page: Any, fallback: str = "") -> str:
    try:
        names = page.evaluate(
            """
            () => Array.from(document.querySelectorAll('h1,h2,[class*="name" i],[class*="title" i]'))
              .map((node) => (node.innerText || node.textContent || '').trim())
              .filter(Boolean)
              .slice(0, 8)
            """
        )
    except Exception:
        names = []
    for name in names:
        clean = " ".join(str(name).split())
        if 1 < len(clean) <= 120 and not any(skip in clean.lower() for skip in ("ad creative", "adxray")):
            return clean
    try:
        title = page.title()
        if title:
            return title.split("-")[0].strip()
    except Exception:
        pass
    return fallback


def _regex_after_label(text: str, labels: tuple[str, ...]) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if any(label in line for label in labels):
            if index + 1 < len(lines):
                return lines[index + 1].strip()
            parts = re.split(r"[:：]", line, maxsplit=1)
            if len(parts) == 2:
                return parts[1].strip()
    return ""


def _extract_date(text: str, labels: tuple[str, ...]) -> str:
    value = _regex_after_label(text, labels)
    match = re.search(r"20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}", value or "")
    if match:
        return match.group(0).replace("/", "-").replace(".", "-")
    pattern = r"(?:" + "|".join(re.escape(label) for label in labels) + r").{0,20}(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})"
    match = re.search(pattern, text)
    if match:
        return match.group(1).replace("/", "-").replace(".", "-")
    return ""


def extract_product_detail(page: Any, dataeye_url: str, stat_date: date) -> dict[str, Any]:
    page.goto(dataeye_url, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=12_000)
    except Exception:
        page.wait_for_timeout(2_000)

    text = safe_page_text(page)
    store_links = _extract_store_links(page)
    external_links = _extract_external_links(page)
    product_id = extract_product_id_from_url(dataeye_url)
    detail: dict[str, Any] = {
        "product_id": product_id,
        "product_name": _extract_name(page),
        "dataeye_url": dataeye_url,
        "first_seen_date": _extract_date(text, ("首次发现", "首次投放", "发现时间")) or format_date(stat_date),
        "campaign_period": _regex_after_label(text, ("投放周期", "广告周期", "Campaign Period")),
        "dataeye_company_name": _regex_after_label(text, ("公司", "开发者", "发行商", "Developer", "Publisher")),
    }

    if store_links:
        detail["store_url"] = store_links[0]
        detail.update(parse_store_identity(store_links[0]))
    if product_id and "type=1" in dataeye_url and not detail.get("store_type"):
        detail["store_type"] = "app_store"
    elif product_id and "type=2" in dataeye_url and not detail.get("store_type"):
        detail["store_type"] = "google_play"

    media_list = [name for name in ("Facebook", "Instagram", "Messenger", "FacebookAudience") if name.lower() in text.lower()]
    if media_list:
        detail["media_list"] = media_list

    try_click_text(page, ["素材", "Creative", "广告素材"])
    page.wait_for_timeout(1_000)
    creative_text = safe_page_text(page)
    combined_text = f"{text}\n{creative_text}"
    if not detail.get("media_list"):
        detail["media_list"] = [name for name in ("Facebook", "Instagram", "Messenger", "FacebookAudience") if name.lower() in combined_text.lower()]

    fb_page = _regex_after_label(combined_text, ("FB主页", "Facebook Page", "主页名称"))
    if fb_page:
        detail["fb_page"] = fb_page

    landing_urls = [
        href
        for href in external_links
        if "oversea-v2.dataeye.com" not in href
        and "play.google.com" not in href
        and "apps.apple.com" not in href
    ]
    if landing_urls:
        detail["landing_url"] = landing_urls[0]

    package_match = re.search(r"\b[a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+){2,}\b", combined_text)
    if package_match and not detail.get("package"):
        detail["package"] = package_match.group(0)

    app_id_match = re.search(r"apps\.apple\.com/[^\\s]+/id(\d+)", combined_text)
    if app_id_match and not detail.get("app_id"):
        detail["app_id"] = app_id_match.group(1)

    return {key: value for key, value in detail.items() if value not in ("", [], None)}


def filter_fb_new_products(products: list[dict[str, Any]], stat_date: date) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    wanted_date = format_date(stat_date)
    kept: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []

    for product in products:
        row = dict(product)
        first_seen = str(row.get("first_seen_date") or wanted_date)[:10]
        date_ok = first_seen == wanted_date
        media_ok = has_facebook_media(row.get("media_list"), extra_text=json.dumps(row, ensure_ascii=False))
        if date_ok and media_ok:
            row["first_seen_date"] = wanted_date
            kept.append(row)
        else:
            row["ignore_reason"] = "not_stat_date" if not date_ok else "not_facebook_media"
            ignored.append(row)
    return kept, ignored


def filter_fb_new_products_for_dates(
    products: list[dict[str, Any]],
    stat_dates: list[date],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    wanted_dates = {format_date(stat_date) for stat_date in stat_dates}
    kept: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []

    for product in products:
        row = dict(product)
        first_seen = str(row.get("first_seen_date") or row.get("scan_date") or "")[:10]
        date_ok = first_seen in wanted_dates
        media_ok = has_facebook_media(row.get("media_list"), extra_text=json.dumps(row, ensure_ascii=False))
        if date_ok and media_ok:
            row["first_seen_date"] = first_seen
            kept.append(row)
        else:
            row["ignore_reason"] = "not_scan_window" if not date_ok else "not_facebook_media"
            ignored.append(row)
    return kept, ignored
