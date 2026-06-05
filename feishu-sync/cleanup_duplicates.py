from __future__ import annotations

import argparse

from feishu_sync.bitable import resolve_table_ids
from feishu_sync.client import FeishuApiError, FeishuClient
from feishu_sync.config import load_config
from feishu_sync.values import feishu_text_value, millis_to_date_string


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean duplicate synced records for one report date.")
    parser.add_argument("--date", required=True, help="Report date, YYYY-MM-DD.")
    args = parser.parse_args()

    config = load_config()
    client = FeishuClient(config.app_id, config.app_secret, config.bitable_app_token)
    table_ids = resolve_table_ids(client)

    total_deleted = 0
    total_deleted += clean_table(
        client,
        table_ids["01_概览"],
        date_field="报告日期",
        key_field="去重Key",
        report_date=args.date,
        source_field="来源",
    )
    total_deleted += clean_table(
        client,
        table_ids["04_DataEye源数据"],
        date_field="statDate",
        key_field="dedupeKey",
        report_date=args.date,
    )
    total_deleted += clean_table(
        client,
        table_ids["05_YouTube源数据"],
        date_field="report_date",
        key_field="dedupeKey",
        report_date=args.date,
    )
    total_deleted += clean_table(
        client,
        table_ids["03_新游戏明细"],
        date_field="报告日期",
        key_field="去重Key",
        report_date=args.date,
        source_field="来源",
    )
    print(f"deleted duplicate records: {total_deleted}")
    return 0


def clean_table(
    client: FeishuClient,
    table_id: str,
    *,
    date_field: str,
    key_field: str,
    report_date: str,
    source_field: str | None = None,
) -> int:
    field_names = [date_field, key_field]
    if source_field:
        field_names.append(source_field)
    records = client.search_records(table_id, field_names=field_names)
    seen: set[tuple[str, str]] = set()
    delete_ids: list[str] = []

    for record in records:
        fields = record.get("fields", {})
        if millis_to_date_string(fields.get(date_field)) != report_date:
            continue
        key = feishu_text_value(fields.get(key_field))
        if not key:
            continue
        source = feishu_text_value(fields.get(source_field)) if source_field else ""
        signature = (source, key)
        if signature in seen:
            delete_ids.append(record["record_id"])
        else:
            seen.add(signature)

    for record_id in delete_ids:
        try:
            client.delete_record(table_id, record_id)
        except FeishuApiError as exc:
            if "1254043" not in str(exc):
                raise
    return len(delete_ids)


if __name__ == "__main__":
    raise SystemExit(main())
