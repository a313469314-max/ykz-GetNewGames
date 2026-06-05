from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .dates import parse_date
from .stores import parse_store_identity


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def normalize_store_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    query = [
        (key, val)
        for key, val in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() == "id"
    ]
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), "", urlencode(query), ""))


def product_dedupe_keys(product: dict[str, Any]) -> list[str]:
    row = dict(product)
    store_identity = parse_store_identity(str(row.get("store_url") or ""))
    for key, value in store_identity.items():
        row.setdefault(key, value)

    candidates: list[tuple[str, Any]] = [
        ("package", row.get("package") or row.get("package_name")),
        ("app_id", row.get("app_id")),
        ("product_id", row.get("product_id")),
        ("store_url", normalize_store_url(row.get("store_url"))),
    ]
    keys: list[str] = []
    for key_type, value in candidates:
        normalized = normalize_text(value)
        if normalized:
            keys.append(f"{key_type}:{normalized}")

    name = normalize_text(row.get("product_name"))
    company = normalize_text(row.get("canonical_company"))
    if name and company:
        keys.append(f"name_company:{company}:{name}")
    elif name:
        keys.append(f"name:{name}")
    return keys


def load_processed_products(project_root: Path | str, before_date: date | None = None) -> list[dict[str, Any]]:
    root = Path(project_root)
    products: list[dict[str, Any]] = []
    for path in sorted((root / "data" / "processed").glob("*.json")):
        match = re.match(r"(\d{4}-\d{2}-\d{2})", path.stem)
        if not match:
            continue
        file_date = parse_date(match.group(1))
        if before_date is not None and file_date >= before_date:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows = payload.get("products", []) if isinstance(payload, dict) else payload
        if isinstance(rows, list):
            products.extend(row for row in rows if isinstance(row, dict))
    return products


def dedupe_products(products: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    seen: set[str] = set()
    kept: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    for product in products:
        keys = product_dedupe_keys(product)
        duplicate_key = next((key for key in keys if key in seen), "")
        if duplicate_key:
            row = dict(product)
            row["ignore_reason"] = "duplicate_in_scan_window"
            row["duplicate_key"] = duplicate_key
            duplicates.append(row)
            continue
        kept.append(product)
        seen.update(keys)
    return kept, duplicates


def remove_history_duplicates(
    products: list[dict[str, Any]],
    history_products: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    history_keys: set[str] = set()
    for product in history_products:
        history_keys.update(product_dedupe_keys(product))

    kept: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    for product in products:
        duplicate_key = next((key for key in product_dedupe_keys(product) if key in history_keys), "")
        if duplicate_key:
            row = dict(product)
            row["ignore_reason"] = "duplicate_in_history"
            row["duplicate_key"] = duplicate_key
            duplicates.append(row)
            continue
        kept.append(product)
    return kept, duplicates
