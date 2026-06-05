from __future__ import annotations

import argparse

from feishu_sync.client import FeishuClient
from feishu_sync.config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete one Feishu Bitable table by exact name.")
    parser.add_argument("--name", required=True, help="Exact table name to delete.")
    args = parser.parse_args()

    config = load_config()
    client = FeishuClient(config.app_id, config.app_secret, config.bitable_app_token)
    tables = client.list_tables()
    matches = [table for table in tables if table.get("name") == args.name]
    if not matches:
        print(f"table not found: {args.name}")
        return 0
    if len(matches) > 1:
        raise RuntimeError(f"multiple tables named {args.name}; refusing to delete")

    table = matches[0]
    client.delete_table(table["table_id"])
    print(f"deleted table: {args.name} ({table['table_id']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
