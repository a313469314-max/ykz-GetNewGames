from __future__ import annotations

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from requests.cookies import RequestsCookieJar

from .dates import format_date
from .stores import parse_store_identity


DATAEYE_ORIGIN = "https://oversea-v2.dataeye.com"
SIGN_KEY = "g:%w0k7&q1v9^tRnLz!M"


def compute_sign(params: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in sorted(params):
        value = params[key]
        if value in (None, "null", "undefined"):
            value_text = ""
        elif isinstance(value, str):
            value_text = quote(value.strip(), safe="").replace("%20", "%20")
            value_text = requests.utils.unquote(value_text)
        else:
            value_text = str(value)
        parts.append(f"{key}={value_text}")
    raw = "&".join(parts) + f"&key={SIGN_KEY}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()


def cookies_from_storage_state(path: Path | str) -> RequestsCookieJar:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    cookies = RequestsCookieJar()
    for cookie in payload.get("cookies", []):
        name = cookie.get("name")
        value = cookie.get("value")
        if name and value is not None:
            cookie_kwargs = {"path": str(cookie.get("path") or "/")}
            domain = str(cookie.get("domain") or "")
            if domain:
                cookie_kwargs["domain"] = domain
            cookies.set(str(name), str(value), **cookie_kwargs)
    return cookies


class DataEyeApiClient:
    def __init__(self, storage_state_path: Path | str) -> None:
        self.session = requests.Session()
        self.session.cookies.update(cookies_from_storage_state(storage_state_path))
        self.session.headers.update(
            {
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Content-Language": "zh-cn",
                "X-Request-With": "XMLHttpRequest",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
                ),
                "Referer": f"{DATAEYE_ORIGIN}/dashboard/home",
            }
        )

    def post(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        last_data: dict[str, Any] | None = None
        for attempt in range(5):
            payload = dict(params)
            payload["thisTimes"] = str(int(time.time() * 1000))
            payload.pop("sign", None)
            payload["sign"] = compute_sign(payload)
            response = self.session.post(f"{DATAEYE_ORIGIN}/api{path}", data=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            last_data = data
            if data.get("statusCode") == 200:
                return data
            if data.get("statusCode") == 429 or "请求频繁" in str(data.get("content") or data.get("msg") or ""):
                time.sleep(10 * (attempt + 1))
                continue
            raise RuntimeError(f"DataEye API failed: {path} {data}")
        raise RuntimeError(f"DataEye API failed after retries: {path} {last_data}")

    def get_new_products(self, stat_date: date) -> list[dict[str, Any]]:
        data = self.post(
            "/workbench/getNewProductListByDate",
            {"mobileType": "", "productType": "", "statDate": format_date(stat_date)},
        )
        rows = data.get("content") or []
        products: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            products.append(
                {
                    "product_id": str(row.get("productId") or ""),
                    "product_name": row.get("productName") or "",
                    "store_type": row.get("storeType"),
                    "product_type": row.get("type"),
                    "unified_product_id": row.get("unifiedProductId"),
                    "material_num": row.get("materialNum"),
                    "first_seen_date": format_date(stat_date),
                    "scan_date": format_date(stat_date),
                    "dataeye_url": f"{DATAEYE_ORIGIN}/product/{row.get('productId')}?type={row.get('storeType')}&isPlaylet=false",
                    "source": "dataeye_api_new_product",
                }
            )
        return products

    def get_product_info(self, product_id: str | int, store_type: str | int) -> dict[str, Any]:
        data = self.post("/product/getProductInfo", {"productId": product_id, "storeType": store_type})
        content = data.get("content") or {}
        return normalize_product_info(content)


def normalize_media_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for item in value:
        if isinstance(item, dict) and item.get("mediaName"):
            names.append(str(item["mediaName"]))
        elif item:
            names.append(str(item))
    return names


def normalize_product_info(content: dict[str, Any]) -> dict[str, Any]:
    store_url = content.get("downloadUrl") or ""
    row: dict[str, Any] = {
        "product_id": str(content.get("productId") or ""),
        "product_name": content.get("productName") or "",
        "store_url": store_url,
        "store_type": content.get("storeType"),
        "dataeye_company_id": str(content.get("publisherId") or ""),
        "dataeye_company_name": content.get("publisherName") or "",
        "developer_name": content.get("publisherName") or "",
        "first_seen_date": content.get("firstSeen") or "",
        "campaign_period": (
            f"{content.get('firstSeen')} ~ {content.get('lastSeen')}"
            if content.get("firstSeen") and content.get("lastSeen")
            else ""
        ),
        "media_list": normalize_media_list(content.get("medias")),
        "material_num": content.get("materialNum"),
        "creative_num": content.get("creativeNum"),
        "country_num": content.get("countryNum"),
    }
    if store_url:
        row.update(parse_store_identity(store_url))
    if row.get("store_type") == 1 and row.get("developer_name"):
        row["seller_name"] = row["developer_name"]
    return {key: value for key, value in row.items() if value not in ("", [], None)}


def fetch_products_via_api(
    storage_state_path: Path | str,
    stat_dates: list[date],
    max_products: int | None = None,
    max_workers: int = 4,
) -> dict[str, list[dict[str, Any]]]:
    client = DataEyeApiClient(storage_state_path)
    thread_state = threading.local()

    def detail_client() -> DataEyeApiClient:
        if not hasattr(thread_state, "client"):
            thread_state.client = DataEyeApiClient(storage_state_path)
        return thread_state.client

    def enrich_candidate(product: dict[str, Any], stat_date_text: str) -> dict[str, Any]:
        detail: dict[str, Any] = {}
        try:
            detail = detail_client().get_product_info(product["product_id"], product.get("store_type") or 2)
        except Exception as exc:
            detail = {"detail_error": str(exc)}
        merged = dict(product)
        merged.update(detail)
        merged["scan_date"] = stat_date_text
        merged.setdefault("first_seen_date", stat_date_text)
        return merged

    results: dict[str, list[dict[str, Any]]] = {}
    for stat_date in stat_dates:
        stat_date_text = format_date(stat_date)
        candidates = client.get_new_products(stat_date)
        if max_products:
            candidates = candidates[:max_products]
        products: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(enrich_candidate, product, stat_date_text) for product in candidates]
            for future in as_completed(futures):
                products.append(future.result())
        results[stat_date_text] = products
    return results
