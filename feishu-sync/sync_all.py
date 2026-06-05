from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from typing import Any

from feishu_sync.bitable import resolve_table_ids
from feishu_sync.client import FeishuClient
from feishu_sync.config import load_config
from feishu_sync.sources import SOURCE_REGISTRY
from feishu_sync.values import (
    clean_record_fields,
    date_to_millis,
    datetime_to_millis,
    feishu_text_value,
    millis_to_date_string,
)


SHANGHAI_TZ = timezone(timedelta(hours=8))


def default_report_date() -> str:
    return (datetime.now(SHANGHAI_TZ).date() - timedelta(days=1)).isoformat()


def build_import_batch_id(report_date: str) -> str:
    return f"feishu-sync:{report_date}:{datetime.now(SHANGHAI_TZ).strftime('%Y%m%d%H%M%S')}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync local new-game reports to Feishu Bitable.")
    parser.add_argument("--date", default=default_report_date(), help="Report date, YYYY-MM-DD. Defaults to yesterday.")
    parser.add_argument(
        "--allow-missing-sources",
        action="store_true",
        help="Skip sources without local data instead of writing failed run logs.",
    )
    args = parser.parse_args()

    config = load_config()
    client = FeishuClient(config.app_id, config.app_secret, config.bitable_app_token)
    table_ids = resolve_table_ids(client)

    import_batch_id = build_import_batch_id(args.date)
    print(f"report_date={args.date}")
    print(f"importBatchId={import_batch_id}")

    errors: dict[str, str] = {}

    for source in SOURCE_REGISTRY:
        try:
            source_data = source.loader(config.root_dir, args.date, import_batch_id)
            raw_created, raw_skipped = sync_raw_rows(
                client,
                table_ids[source.raw_table],
                source_data.raw_rows,
                date_field=source.raw_date_field,
                report_date=args.date,
            )
            overview_created, overview_skipped = sync_detail_rows(
                client,
                table_ids["01_概览"],
                source_data.overview_rows,
                report_date=args.date,
                source=source.name,
            )
            detail_created, detail_skipped = sync_detail_rows(
                client,
                table_ids["03_新游戏明细"],
                source_data.detail_rows,
                report_date=args.date,
                source=source.name,
            )
            write_run_log(
                client,
                table_ids["06_运行记录"],
                report_date=args.date,
                source=source.name,
                status="成功",
                raw_count=len(source_data.raw_rows),
                overview_count=overview_created,
                overview_skipped_count=overview_skipped,
                detail_count=detail_created,
                skipped_count=detail_skipped,
                error_message="",
                report_path=str(source_data.report_path or ""),
                import_batch_id=import_batch_id,
            )
            print(
                f"{source.name}: raw_created={raw_created} raw_skipped={raw_skipped} "
                f"overview_created={overview_created} overview_skipped={overview_skipped} "
                f"detail_created={detail_created} detail_skipped={detail_skipped}"
            )
        except Exception as exc:  # noqa: BLE001
            if args.allow_missing_sources and isinstance(exc, FileNotFoundError):
                print(f"{source.name}: skipped missing source: {exc}")
                continue
            errors[source.name] = str(exc)
            write_run_log(
                client,
                table_ids["06_运行记录"],
                report_date=args.date,
                source=source.name,
                status="失败",
                raw_count=0,
                overview_count=0,
                overview_skipped_count=0,
                detail_count=0,
                skipped_count=0,
                error_message=str(exc),
                report_path="",
                import_batch_id=import_batch_id,
            )
            print(f"{source.name}: failed: {exc}")

    return 1 if errors else 0


def sync_raw_rows(
    client: FeishuClient,
    table_id: str,
    rows: list[dict[str, Any]],
    *,
    date_field: str,
    report_date: str,
) -> tuple[int, int]:
    existing_keys = load_existing_keys(
        client,
        table_id,
        date_field=date_field,
        report_date=report_date,
        key_field="dedupeKey",
        source_field=None,
        source=None,
    )
    records = []
    skipped = 0
    seen: set[str] = set()
    for row in rows:
        dedupe_key = str(row.get("dedupeKey", ""))
        if dedupe_key in existing_keys or dedupe_key in seen:
            skipped += 1
            continue
        seen.add(dedupe_key)
        records.append({"fields": convert_fields(row)})
    created = client.batch_create_records(table_id, records)
    return len(created), skipped


def sync_detail_rows(
    client: FeishuClient,
    table_id: str,
    rows: list[dict[str, Any]],
    *,
    report_date: str,
    source: str,
) -> tuple[int, int]:
    existing_keys = load_existing_keys(
        client,
        table_id,
        date_field="报告日期",
        report_date=report_date,
        key_field="去重Key",
        source_field="来源",
        source=source,
    )
    records = []
    skipped = 0
    seen: set[str] = set()
    for row in rows:
        dedupe_key = str(row.get("去重Key", ""))
        if dedupe_key in existing_keys or dedupe_key in seen:
            skipped += 1
            continue
        seen.add(dedupe_key)
        records.append({"fields": convert_fields(row)})
    created = client.batch_create_records(table_id, records)
    return len(created), skipped


def load_existing_keys(
    client: FeishuClient,
    table_id: str,
    *,
    date_field: str,
    report_date: str,
    key_field: str,
    source_field: str | None,
    source: str | None,
) -> set[str]:
    field_names = [date_field, key_field]
    if source_field:
        field_names.append(source_field)
    records = client.search_records(table_id, field_names=field_names)
    keys: set[str] = set()
    for record in records:
        fields = record.get("fields", {})
        if millis_to_date_string(fields.get(date_field)) != report_date:
            continue
        if source_field and source and feishu_text_value(fields.get(source_field)) != source:
            continue
        key = feishu_text_value(fields.get(key_field))
        if key:
            keys.add(key)
    return keys


def convert_fields(row: dict[str, Any]) -> dict[str, Any]:
    converted = dict(row)
    for field_name in ["报告日期", "statDate", "report_date"]:
        if field_name in converted:
            converted[field_name] = date_to_millis(converted[field_name])
    for field_name in ["写入时间", "数据更新时间", "运行时间"]:
        if field_name in converted:
            converted[field_name] = datetime_to_millis(converted[field_name])
    return clean_record_fields(converted)


def write_run_log(
    client: FeishuClient,
    table_id: str,
    *,
    report_date: str,
    source: str,
    status: str,
    raw_count: int,
    overview_count: int,
    overview_skipped_count: int,
    detail_count: int,
    skipped_count: int,
    error_message: str,
    report_path: str,
    import_batch_id: str,
) -> None:
    now = datetime.now(SHANGHAI_TZ).isoformat(timespec="seconds")
    client.batch_create_records(
        table_id,
        [
            {
                "fields": convert_fields(
                    {
                        "运行标题": f"{report_date} {source} {status}",
                        "运行时间": now,
                        "报告日期": report_date,
                        "来源": source,
                        "状态": status,
                        "源数据条数": raw_count,
                        "概览写入条数": overview_count,
                        "概览跳过条数": overview_skipped_count,
                        "明细写入条数": detail_count,
                        "去重跳过条数": skipped_count,
                        "错误信息": error_message,
                        "本地报告路径": report_path,
                        "importBatchId": import_batch_id,
                    }
                )
            }
        ],
    )


if __name__ == "__main__":
    raise SystemExit(main())
