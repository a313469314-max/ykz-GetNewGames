from __future__ import annotations

from dataclasses import dataclass


FIELD_TEXT = 1
FIELD_NUMBER = 2
FIELD_DATE = 5


@dataclass(frozen=True)
class FieldSpec:
    name: str
    field_type: int = FIELD_TEXT


@dataclass(frozen=True)
class TableSpec:
    name: str
    fields: tuple[FieldSpec, ...]


TABLES: tuple[TableSpec, ...] = (
    TableSpec(
        "01_概览",
        (
            FieldSpec("卡片标题"),
            FieldSpec("报告日期", FIELD_DATE),
            FieldSpec("栏目"),
            FieldSpec("展示顺序", FIELD_NUMBER),
            FieldSpec("产品数量", FIELD_NUMBER),
            FieldSpec("产品列表"),
            FieldSpec("展示备注"),
            FieldSpec("明细说明"),
            FieldSpec("来源"),
            FieldSpec("去重Key"),
            FieldSpec("importBatchId"),
            FieldSpec("写入时间", FIELD_DATE),
        ),
    ),
    TableSpec(
        "03_新游戏明细",
        (
            FieldSpec("卡片标题"),
            FieldSpec("游戏名称"),
            FieldSpec("报告日期", FIELD_DATE),
            FieldSpec("来源"),
            FieldSpec("来源渠道"),
            FieldSpec("平台"),
            FieldSpec("厂商名"),
            FieldSpec("商店链接"),
            FieldSpec("DataEye详情链接"),
            FieldSpec("YouTube视频链接"),
            FieldSpec("包名"),
            FieldSpec("Apple App ID"),
            FieldSpec("DataEye产品ID"),
            FieldSpec("置信度"),
            FieldSpec("去重Key"),
            FieldSpec("关注级别"),
            FieldSpec("跟进状态"),
            FieldSpec("备注"),
            FieldSpec("importBatchId"),
            FieldSpec("写入时间", FIELD_DATE),
        ),
    ),
    TableSpec(
        "04_DataEye源数据",
        (
            FieldSpec("productName"),
            FieldSpec("statDate", FIELD_DATE),
            FieldSpec("productId"),
            FieldSpec("platformName"),
            FieldSpec("type"),
            FieldSpec("companyName"),
            FieldSpec("productIcon"),
            FieldSpec("stableProductIcon"),
            FieldSpec("detailUrl"),
            FieldSpec("fetchedAt"),
            FieldSpec("dedupeKey"),
            FieldSpec("importBatchId"),
        ),
    ),
    TableSpec(
        "05_YouTube源数据",
        (
            FieldSpec("game_name"),
            FieldSpec("report_date", FIELD_DATE),
            FieldSpec("channel_name"),
            FieldSpec("video_id"),
            FieldSpec("video_title"),
            FieldSpec("video_url"),
            FieldSpec("store_url"),
            FieldSpec("package_id"),
            FieldSpec("apple_app_id"),
            FieldSpec("platform"),
            FieldSpec("link_type"),
            FieldSpec("confidence"),
            FieldSpec("reject_reason"),
            FieldSpec("normalized_game_name"),
            FieldSpec("normalized_store_url"),
            FieldSpec("dedupeKey"),
            FieldSpec("importBatchId"),
        ),
    ),
    TableSpec(
        "06_运行记录",
        (
            FieldSpec("运行标题"),
            FieldSpec("运行时间", FIELD_DATE),
            FieldSpec("报告日期", FIELD_DATE),
            FieldSpec("来源"),
            FieldSpec("状态"),
            FieldSpec("源数据条数", FIELD_NUMBER),
            FieldSpec("概览写入条数", FIELD_NUMBER),
            FieldSpec("概览跳过条数", FIELD_NUMBER),
            FieldSpec("明细写入条数", FIELD_NUMBER),
            FieldSpec("去重跳过条数", FIELD_NUMBER),
            FieldSpec("错误信息"),
            FieldSpec("本地报告路径"),
            FieldSpec("importBatchId"),
        ),
    ),
)


TABLE_BY_NAME = {table.name: table for table in TABLES}
