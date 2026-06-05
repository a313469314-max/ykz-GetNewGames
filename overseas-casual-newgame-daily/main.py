from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from src.attribution import apply_attribution, load_mapping, load_target_companies
from src.dataeye_api import fetch_products_via_api
from src.dataeye_auth import DataEyeSession, load_settings
from src.dataeye_extract import DataEyeExtractor, filter_fb_new_products_for_dates, merge_products
from src.dates import date_range, default_report_date, default_scan_dates, format_date, parse_date
from src.history import dedupe_products, load_processed_products, remove_history_duplicates
from src.report import write_reports
from src.stores import enrich_store


PROJECT_ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate overseas casual new game daily report from DataEye/AdXray.")
    parser.add_argument("--date", dest="report_date", help="Report/run date in YYYY-MM-DD. Defaults to today in Asia/Shanghai.")
    parser.add_argument("--stat-date", help="Scan one exact DataEye stat date. Overrides the default scan window.")
    parser.add_argument("--start-date", help="Scan window start date in YYYY-MM-DD.")
    parser.add_argument("--end-date", help="Scan window end date in YYYY-MM-DD.")
    parser.add_argument("--lookback-days", type=int, default=3, help="Default scan window length before report date. Default: 3.")
    parser.add_argument("--headed", action="store_true", help="Show browser even when the saved login state is valid.")
    parser.add_argument("--max-products", type=int, default=None, help="Limit products while debugging.")
    parser.add_argument("--from-raw", type=Path, action="append", help="Replay raw JSON instead of opening DataEye. Can be used multiple times.")
    parser.add_argument("--skip-store-enrich", action="store_true", help="Skip Google Play/App Store enrichment requests.")
    parser.add_argument("--no-history-dedupe", action="store_true", help="Do not remove products seen in previous processed outputs.")
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_raw(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload.get("products", [])
    if isinstance(payload, list):
        return payload
    raise ValueError(f"Unsupported raw JSON shape: {path}")


def write_unmatched_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "ignore_reason",
        "product_id",
        "product_name",
        "store_type",
        "package",
        "app_id",
        "store_url",
        "dataeye_url",
        "scan_date",
        "first_seen_date",
        "media_list",
        "dataeye_company_name",
        "developer_name",
        "seller_name",
        "fb_page",
        "privacy_domain",
        "developer_domain",
        "landing_url",
        "canonical_company",
        "duplicate_key",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            compact = dict(row)
            for key, value in list(compact.items()):
                if isinstance(value, list):
                    compact[key] = ", ".join(str(item) for item in value)
            writer.writerow(compact)


def resolve_dates(args: argparse.Namespace) -> tuple[Any, list[Any]]:
    report_date = parse_date(args.report_date) if args.report_date else default_report_date()
    if args.stat_date:
        return report_date, [parse_date(args.stat_date)]
    if args.start_date or args.end_date:
        if not args.start_date or not args.end_date:
            raise ValueError("--start-date and --end-date must be used together.")
        return report_date, date_range(args.start_date, args.end_date)
    return report_date, default_scan_dates(report_date, lookback_days=args.lookback_days)


def scan_label(stat_dates: list[Any]) -> str:
    if not stat_dates:
        return ""
    if len(stat_dates) == 1:
        return format_date(stat_dates[0])
    return f"{format_date(stat_dates[0])} 至 {format_date(stat_dates[-1])}"


def fetch_from_dataeye(stat_dates: list[Any], headed: bool, max_products: int | None) -> dict[str, list[dict[str, Any]]]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise RuntimeError("Playwright is not installed. Run: python -m pip install -r requirements.txt") from exc

    settings = load_settings(PROJECT_ROOT)
    with sync_playwright() as playwright:
        browser, context, page = DataEyeSession(settings, headed=headed).open(playwright)
        context.storage_state(path=str(settings.storage_state))
        context.close()
        browser.close()

    results = fetch_products_via_api(settings.storage_state, stat_dates, max_products=max_products)
    if any(results.values()):
        return results

    with sync_playwright() as playwright:
        browser, context, page = DataEyeSession(settings, headed=headed).open(playwright)
        try:
            results: dict[str, list[dict[str, Any]]] = {}
            for stat_date in stat_dates:
                stat_date_text = format_date(stat_date)
                rows = DataEyeExtractor(page, stat_date=stat_date, max_products=max_products).extract()
                for row in rows:
                    row["scan_date"] = stat_date_text
                results[stat_date_text] = rows
            return results
        finally:
            context.close()
            browser.close()


def main() -> int:
    args = parse_args()
    report_date, stat_dates = resolve_dates(args)
    report_date_text = format_date(report_date)
    stat_date_texts = [format_date(stat_date) for stat_date in stat_dates]
    current_scan_label = scan_label(stat_dates)

    if args.from_raw:
        raw_products: list[dict[str, Any]] = []
        for raw_path in args.from_raw:
            raw_products.extend(read_raw(raw_path))
        raw_by_date = {report_date_text: raw_products}
    else:
        raw_by_date = fetch_from_dataeye(stat_dates, headed=args.headed, max_products=args.max_products)
        raw_products = [row for rows in raw_by_date.values() for row in rows]

    for raw_date, rows in raw_by_date.items():
        write_json(PROJECT_ROOT / "data" / "raw" / f"{raw_date}.json", {"scan_date": raw_date, "products": merge_products(rows)})

    raw_products = merge_products(raw_products)
    write_json(
        PROJECT_ROOT / "data" / "raw" / f"{report_date_text}_scan.json",
        {"report_date": report_date_text, "scan_dates": stat_date_texts, "products": raw_products},
    )

    fb_products, fb_ignored = filter_fb_new_products_for_dates(raw_products, stat_dates)
    enriched_products: list[dict[str, Any]] = []
    for product in fb_products:
        row = dict(product)
        if not args.skip_store_enrich:
            row = enrich_store(row)
        enriched_products.append(row)

    target_companies = load_target_companies(PROJECT_ROOT / "config" / "target_companies.yaml")
    mappings = load_mapping(PROJECT_ROOT / "config" / "company_mapping.csv")
    processed_products, unmatched = apply_attribution(enriched_products, mappings, target_companies)
    unmatched.extend(fb_ignored)

    processed_products, scan_duplicates = dedupe_products(processed_products)
    unmatched.extend(scan_duplicates)
    history_duplicates: list[dict[str, Any]] = []
    if not args.no_history_dedupe:
        history_products = load_processed_products(PROJECT_ROOT, before_date=report_date)
        processed_products, history_duplicates = remove_history_duplicates(processed_products, history_products)
        unmatched.extend(history_duplicates)

    write_json(
        PROJECT_ROOT / "data" / "processed" / f"{report_date_text}.json",
        {
            "report_date": report_date_text,
            "scan_dates": stat_date_texts,
            "scan_start_date": stat_date_texts[0] if stat_date_texts else "",
            "scan_end_date": stat_date_texts[-1] if stat_date_texts else "",
            "products": processed_products,
            "scan_duplicate_count": len(scan_duplicates),
            "history_duplicate_count": len(history_duplicates),
            "unmatched_count": len(unmatched),
        },
    )
    write_unmatched_csv(PROJECT_ROOT / "data" / "unmatched" / f"{report_date_text}.csv", unmatched)
    markdown_path, xlsx_path = write_reports(processed_products, report_date_text, PROJECT_ROOT / "output", current_scan_label)

    print(f"海外休闲新品日报 generated for {report_date_text}")
    print(f"Scan dates: {current_scan_label}")
    print(f"Products kept: {len(processed_products)}")
    print(f"Duplicates in scan window: {len(scan_duplicates)}")
    print(f"Duplicates in history: {len(history_duplicates)}")
    print(f"Unmatched/ignored: {len(unmatched)}")
    print(f"Markdown: {markdown_path}")
    print(f"XLSX: {xlsx_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
