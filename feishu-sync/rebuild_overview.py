from __future__ import annotations

import argparse

from feishu_sync.bitable import resolve_table_ids
from feishu_sync.client import FeishuApiError, FeishuClient
from feishu_sync.config import load_config
from feishu_sync.sources import load_dataeye, load_youtube
from feishu_sync.values import millis_to_date_string
from sync_all import build_import_batch_id, convert_fields, default_report_date


OVERVIEW_TABLE = "01_概览"


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild Feishu overview cards for one report date.")
    parser.add_argument("--date", default=default_report_date(), help="Report date, YYYY-MM-DD. Defaults to yesterday.")
    args = parser.parse_args()

    config = load_config()
    client = FeishuClient(config.app_id, config.app_secret, config.bitable_app_token)
    table_ids = resolve_table_ids(client)
    overview_table_id = table_ids[OVERVIEW_TABLE]

    deleted = clear_overview_date(client, overview_table_id, args.date)
    import_batch_id = build_import_batch_id(args.date)

    rows = []
    for loader in (load_dataeye, load_youtube):
        source_data = loader(config.root_dir, args.date, import_batch_id)
        rows.extend({"fields": convert_fields(row)} for row in source_data.overview_rows)

    created = client.batch_create_records(overview_table_id, rows)
    print(f"overview rebuilt: date={args.date} deleted={deleted} created={len(created)}")
    return 0


def clear_overview_date(client: FeishuClient, table_id: str, report_date: str) -> int:
    records = client.search_records(table_id, field_names=["报告日期"], page_size=500)
    record_ids = [
        record["record_id"]
        for record in records
        if millis_to_date_string(record.get("fields", {}).get("报告日期")) == report_date
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
