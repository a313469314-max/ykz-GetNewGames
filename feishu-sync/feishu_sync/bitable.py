from __future__ import annotations

from dataclasses import dataclass

from .client import FeishuClient
from .schema import TABLES, FieldSpec, TableSpec


@dataclass(frozen=True)
class TableInfo:
    table_id: str
    name: str


def ensure_tables_and_fields(client: FeishuClient) -> dict[str, TableInfo]:
    existing_tables = {item["name"]: item for item in client.list_tables()}
    table_infos: dict[str, TableInfo] = {}

    for spec in TABLES:
        table = existing_tables.get(spec.name)
        if not table:
            table = client.create_table(spec.name, spec.fields[0].name)
            existing_tables[spec.name] = table
            print(f"created table: {spec.name}")
        else:
            print(f"found table: {spec.name}")

        table_id = table["table_id"]
        ensure_fields(client, table_id, spec)
        table_infos[spec.name] = TableInfo(table_id=table_id, name=spec.name)

    return table_infos


def ensure_fields(client: FeishuClient, table_id: str, spec: TableSpec) -> None:
    existing_fields = {item["field_name"]: item for item in client.list_fields(table_id)}

    first_field = spec.fields[0]
    default_field = existing_fields.get("文本")
    if first_field.name not in existing_fields and default_field:
        client.update_field(table_id, default_field["field_id"], first_field.name, first_field.field_type)
        print(f"  renamed field: {spec.name}.文本 -> {first_field.name}")
        existing_fields = {item["field_name"]: item for item in client.list_fields(table_id)}

    for field in spec.fields:
        if field.name in existing_fields:
            continue
        client.create_field(table_id, field.name, field.field_type)
        print(f"  created field: {spec.name}.{field.name}")


def resolve_table_ids(client: FeishuClient) -> dict[str, str]:
    tables = {item["name"]: item["table_id"] for item in client.list_tables()}
    missing = [spec.name for spec in TABLES if spec.name not in tables]
    if missing:
        raise RuntimeError(f"Missing Feishu tables, run setup_bitable.py first: {', '.join(missing)}")
    return {spec.name: tables[spec.name] for spec in TABLES}


def field_names(spec: TableSpec) -> list[str]:
    return [field.name for field in spec.fields]


def date_field_names(spec: TableSpec) -> set[str]:
    return {field.name for field in spec.fields if field.field_type == 5}
