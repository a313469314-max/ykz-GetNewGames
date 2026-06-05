from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .stores import domain_from_url


PACKAGE_TYPES = {"package", "package_name", "app_id"}
COMPANY_ID_TYPES = {"dataeye_company_id", "company_id"}
DEVELOPER_TYPES = {
    "developer_id",
    "google_developer_id",
    "apple_artist_id",
    "developer_name",
    "seller_name",
}
DOMAIN_TYPES = {"domain", "privacy_domain", "developer_domain", "seller_domain"}
FACEBOOK_PAGE_TYPES = {"fb_page", "facebook_page"}
MANUAL_TYPES = {"manual", "dataeye_company_name", "company_name"}


PRIORITY_GROUPS = (
    DEVELOPER_TYPES,
    DOMAIN_TYPES,
    COMPANY_ID_TYPES,
    MANUAL_TYPES,
    FACEBOOK_PAGE_TYPES,
    PACKAGE_TYPES,
)


@dataclass(frozen=True)
class MappingRow:
    match_type: str
    match_value: str
    canonical_company: str
    confidence: str = ""
    source: str = ""
    note: str = ""


@dataclass(frozen=True)
class AttributionResult:
    canonical_company: str
    matched_by: str
    matched_value: str
    confidence: str
    source: str
    note: str = ""


def normalize_value(value: Any, match_type: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if match_type in DOMAIN_TYPES:
        return domain_from_url(text)
    lowered = " ".join(text.split()).lower()
    return lowered


def load_target_companies(path: Path | str) -> list[str]:
    path = Path(path)
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return [str(company).strip() for company in data.get("companies", []) if str(company).strip()]
    except Exception:
        companies: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("- "):
                companies.append(line[2:].strip())
        return companies


def load_mapping(path: Path | str) -> list[MappingRow]:
    rows: list[MappingRow] = []
    with Path(path).open("r", newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if not row.get("match_type") or not row.get("match_value") or not row.get("canonical_company"):
                continue
            rows.append(
                MappingRow(
                    match_type=row["match_type"].strip(),
                    match_value=row["match_value"].strip(),
                    canonical_company=row["canonical_company"].strip(),
                    confidence=row.get("confidence", "").strip(),
                    source=row.get("source", "").strip(),
                    note=row.get("note", "").strip(),
                )
            )
    return rows


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, dict):
                out.extend(str(v).strip() for v in item.values() if str(v).strip())
            elif str(item).strip():
                out.append(str(item).strip())
        return out
    if str(value).strip():
        return [str(value).strip()]
    return []


def signals_for_product(product: dict[str, Any]) -> dict[str, list[str]]:
    signals: dict[str, list[str]] = {
        "package": _as_list(product.get("package") or product.get("package_name")),
        "app_id": _as_list(product.get("app_id")),
        "dataeye_company_id": _as_list(product.get("dataeye_company_id")),
        "developer_id": _as_list(product.get("developer_id") or product.get("google_developer_id")),
        "google_developer_id": _as_list(product.get("google_developer_id")),
        "apple_artist_id": _as_list(product.get("apple_artist_id")),
        "developer_name": _as_list(product.get("developer_name")),
        "seller_name": _as_list(product.get("seller_name")),
        "domain": [],
        "fb_page": _as_list(product.get("fb_page")),
        "dataeye_company_name": _as_list(product.get("dataeye_company_name")),
    }

    for field in ("privacy_domain", "developer_domain", "seller_domain"):
        signals["domain"].extend(_as_list(product.get(field)))
    for field in ("privacy_url", "developer_website", "seller_url", "landing_url", "store_url"):
        for url in _as_list(product.get(field)):
            domain = domain_from_url(url)
            if domain:
                signals["domain"].append(domain)

    seen_by_type: dict[str, set[str]] = {}
    for key, values in list(signals.items()):
        seen = seen_by_type.setdefault(key, set())
        compact: list[str] = []
        for value in values:
            normalized = normalize_value(value, key)
            if normalized and normalized not in seen:
                seen.add(normalized)
                compact.append(value)
        signals[key] = compact
    return signals


def _mapping_index(rows: Iterable[MappingRow]) -> dict[tuple[str, str], MappingRow]:
    index: dict[tuple[str, str], MappingRow] = {}
    for row in rows:
        index[(row.match_type, normalize_value(row.match_value, row.match_type))] = row
    return index


def attribute_product(
    product: dict[str, Any],
    mappings: list[MappingRow],
    target_companies: list[str],
) -> AttributionResult | None:
    signals = signals_for_product(product)
    index = _mapping_index(mappings)

    for group in PRIORITY_GROUPS:
        for match_type in group:
            for value in signals.get(match_type, []):
                normalized = normalize_value(value, match_type)
                row = index.get((match_type, normalized))
                if row:
                    return AttributionResult(
                        canonical_company=row.canonical_company,
                        matched_by=match_type,
                        matched_value=value,
                        confidence=row.confidence,
                        source=row.source,
                        note=row.note,
                    )

    target_lookup = {normalize_value(company): company for company in target_companies}
    direct_signal_order = (
        "developer_name",
        "seller_name",
        "dataeye_company_name",
        "fb_page",
    )
    for match_type in direct_signal_order:
        for value in signals.get(match_type, []):
            company = target_lookup.get(normalize_value(value))
            if company:
                return AttributionResult(
                    canonical_company=company,
                    matched_by=f"direct_{match_type}",
                    matched_value=value,
                    confidence="medium",
                    source="direct_target_name",
                    note="Signal exactly matched target company name.",
                )
    return None


def apply_attribution(
    products: list[dict[str, Any]],
    mappings: list[MappingRow],
    target_companies: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    target_set = {company.lower() for company in target_companies}
    kept: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []

    for product in products:
        result = attribute_product(product, mappings, target_companies)
        enriched = dict(product)
        if result:
            enriched.update(
                {
                    "canonical_company": result.canonical_company,
                    "attribution_match_type": result.matched_by,
                    "attribution_match_value": result.matched_value,
                    "attribution_confidence": result.confidence,
                    "attribution_source": result.source,
                    "attribution_note": result.note,
                }
            )
            if result.canonical_company.lower() in target_set:
                kept.append(enriched)
            else:
                enriched["ignore_reason"] = "mapped_company_not_in_target_list"
                unmatched.append(enriched)
        else:
            enriched["ignore_reason"] = "no_company_mapping"
            unmatched.append(enriched)

    return kept, unmatched
