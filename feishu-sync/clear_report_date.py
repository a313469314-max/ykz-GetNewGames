from __future__ import annotations

import argparse

from feishu_sync.bitable import resolve_table_ids
from feishu_sync.client import FeishuApiError, FeishuClient
from feishu_sync.config import load_config
from feishu_sync.values import millis_to_date_string


DATE_FIELD_BY_TABLE = {
    "01_概览": "报告日期",
    "03_新游戏明细": "报告日期",
    "04_DataEye源数据": "statDate",
    "05_YouTube源数据": "report_date",
    "06_运行记录": "报告日期",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete all synced Feishu records for one report date.")
    parser.add_argument("--date", required=True, help="Report date, YYYY-MM-DD.")
    args = parser.parse_args()

    config = load_config()
    client = FeishuClient(config.app_id, config.app_secret, config.bitable_app_token)
    table_ids = resolve_table_ids(client)

    total = 0
    for table_name, date_field in DATE_FIELD_BY_TABLE.items():
        table_id = table_ids[table_name]
        deleted = clear_table(client, table_id, date_field, args.date)
        total += deleted
        print(f"{table_name}: deleted={deleted}")

    print(f"total deleted={total}")
    return 0


def clear_table(client: FeishuClient, table_id: str, date_field: str, report_date: str) -> int:
    records = client.search_records(table_id, field_names=[date_field], page_size=500)
    record_ids = [
        record["record_id"]
        for record in records
        if millis_to_date_string(record.get("fields", {}).get(date_field)) == report_date
    ]

    deleted = 0
    for record_id in record_ids:
        try:
            client.delete_record(table_id, record_id)
            deleted += 1
        except FeishuApiError as exc:
            if "1254043" not in str(exc):
                raise
    return deleted


if __name__ == "__main__":
    raise SystemExit(main())
