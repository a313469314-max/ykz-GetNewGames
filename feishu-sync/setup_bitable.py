from __future__ import annotations

import argparse

from feishu_sync.bitable import ensure_tables_and_fields
from feishu_sync.client import FeishuClient
from feishu_sync.config import load_config
from feishu_sync.schema import TABLES


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize Feishu Bitable tables and fields.")
    parser.add_argument(
        "--print-manual-tables",
        action="store_true",
        help="Print table names to create manually when the app cannot create tables.",
    )
    parser.add_argument(
        "--print-manual-fields",
        action="store_true",
        help="Print fields to create manually when the app cannot create fields.",
    )
    args = parser.parse_args()

    if args.print_manual_tables:
        print("Create these tables manually in Feishu Bitable, then rerun python setup_bitable.py:")
        for table in TABLES:
            print(f"- {table.name}")
        return 0

    if args.print_manual_fields:
        print("Create these fields manually in each Feishu Bitable table:")
        for table in TABLES:
            print(f"\n[{table.name}]")
            for field in table.fields:
                type_label = {1: "文本", 2: "数字", 5: "日期"}.get(field.field_type, str(field.field_type))
                print(f"- {field.name} ({type_label})")
        return 0

    config = load_config()
    client = FeishuClient(
        app_id=config.app_id,
        app_secret=config.app_secret,
        app_token=config.bitable_app_token,
    )
    table_infos = ensure_tables_and_fields(client)
    print("")
    print("Feishu Bitable setup complete:")
    for table_name, info in table_infos.items():
        print(f"- {table_name}: {info.table_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
