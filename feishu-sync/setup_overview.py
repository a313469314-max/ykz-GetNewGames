from __future__ import annotations

import argparse

from feishu_sync.bitable import ensure_tables_and_fields, resolve_table_ids
from feishu_sync.client import FeishuClient
from feishu_sync.config import load_config
from feishu_sync.values import feishu_text_value


OVERVIEW_TABLE = "01_概览"
DETAIL_TABLE = "03_新游戏明细"

OVERVIEW_VIEWS = (
    ("栏目卡片", "gallery"),
    ("栏目看板", "kanban"),
)

LEGACY_OVERVIEW_VIEWS = {"卡片概览", "双块看板"}
LEGACY_OVERVIEW_FIELDS = {
    "板块",
    "游戏名称",
    "厂商/频道",
    "平台",
    "主链接",
    "辅助链接",
    "来源渠道",
    "关注级别",
    "跟进状态",
    "备注",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize Feishu overview table and views.")
    parser.add_argument(
        "--backfill-detail-titles",
        action="store_true",
        help="Also fill missing card titles in historical detail rows.",
    )
    args = parser.parse_args()

    config = load_config()
    client = FeishuClient(config.app_id, config.app_secret, config.bitable_app_token)

    ensure_tables_and_fields(client)
    table_ids = resolve_table_ids(client)

    prune_legacy_fields(client, table_ids[OVERVIEW_TABLE])
    ensure_views(client, table_ids[OVERVIEW_TABLE])
    if args.backfill_detail_titles:
        backfill_detail_card_titles(client, table_ids[DETAIL_TABLE])

    print("overview setup complete")
    return 0


def prune_legacy_fields(client: FeishuClient, table_id: str) -> None:
    for field in client.list_fields(table_id):
        field_name = field.get("field_name")
        if field_name not in LEGACY_OVERVIEW_FIELDS:
            continue
        client.delete_field(table_id, field["field_id"])
        print(f"deleted legacy field: {OVERVIEW_TABLE}.{field_name}")


def ensure_views(client: FeishuClient, table_id: str) -> None:
    existing = {view["view_name"]: view for view in client.list_views(table_id)}
    for view_name in LEGACY_OVERVIEW_VIEWS:
        view = existing.pop(view_name, None)
        if not view:
            continue
        client.delete_view(table_id, view["view_id"])
        print(f"deleted legacy view: {OVERVIEW_TABLE}.{view_name}")

    for view_name, view_type in OVERVIEW_VIEWS:
        if view_name in existing:
            print(f"found view: {OVERVIEW_TABLE}.{view_name}")
            continue
        view = client.create_view(table_id, view_name, view_type)
        print(f"created view: {OVERVIEW_TABLE}.{view['view_name']} ({view['view_type']})")


def backfill_detail_card_titles(client: FeishuClient, table_id: str) -> None:
    records = client.search_records(table_id, field_names=["卡片标题", "游戏名称"], page_size=500)
    updated = 0
    for record in records:
        fields = record.get("fields", {})
        if feishu_text_value(fields.get("卡片标题")):
            continue
        game_name = feishu_text_value(fields.get("游戏名称"))
        if not game_name:
            continue
        client.update_record(table_id, record["record_id"], {"卡片标题": game_name})
        updated += 1
    print(f"backfilled detail card titles: {updated}")


if __name__ == "__main__":
    raise SystemExit(main())
