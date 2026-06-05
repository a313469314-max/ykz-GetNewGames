from __future__ import annotations

from collections import OrderedDict, defaultdict
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping


PLATFORM_PRIORITY = {
    "google_play": 1,
    "app_store": 2,
    "steam": 3,
    "regional_store": 4,
    "third_party_store": 4,
    "official_site": 5,
    "landing_page": 5,
    "other": 6,
    "unknown": 99,
    "rejected": 100,
}
REPORTABLE_CONFIDENCE = {"high", "medium"}


def build_daily_report_text(
    *,
    run_date: date,
    window_start_date: date,
    window_end_date: date,
    report_rows: Iterable[Mapping[str, str]],
) -> str:
    channel_items = build_channel_items(report_rows)
    total_items = sum(len(items) for items in channel_items.values())
    lines = [f"YouTube 新品日报 ({run_date.isoformat()})"]

    if total_items == 0:
        lines.append("本次未发现新增游戏条目。")
        return "\n".join(lines)

    lines.append(
        f"本次扫描窗口为 {window_start_date.isoformat()} 至 {window_end_date.isoformat()}，"
        f"共发现 {total_items} 个此前未在历史日报中输出过的新游戏条目，按频道整理如下："
    )
    lines.append("")

    channel_names = list(channel_items.keys())
    for index, channel_name in enumerate(channel_names):
        items = channel_items[channel_name]
        lines.append(f"{channel_name} (新增 {len(items)} 个)")
        for item in items:
            lines.append(f"- {item['game_name']}: {item['store_url']}")
        if index != len(channel_names) - 1:
            lines.append("")

    return "\n".join(lines)


def write_daily_report(output_dir: Path, target_date: date, report_text: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"youtube_new_games_{target_date.isoformat()}.txt"
    report_path.write_text(report_text, encoding="utf-8")
    return report_path


def build_dedupe_key(row: Mapping[str, str]) -> str:
    if row["package_id"]:
        return f"pkg:{row['package_id'].lower()}"
    if row["apple_app_id"]:
        return f"ios:{row['apple_app_id']}"
    if row.get("normalized_store_url"):
        return f"name_url:{row['normalized_game_name']}:{row['normalized_store_url']}"
    return f"name:{row['normalized_game_name']}"


def collect_current_report_rows(
    window_games: Iterable[Mapping[str, str]],
    historical_output_keys: set[str],
) -> list[dict]:
    grouped_by_channel: dict[str, list[dict]] = defaultdict(list)
    for row in window_games:
        row_dict = dict(row)
        if not is_reportable_row(row_dict):
            continue
        grouped_by_channel[row_dict["channel_name"]].append(row_dict)

    report_rows: list[dict] = []
    seen_current_keys: set[str] = set()
    for channel_name in sorted(grouped_by_channel):
        for row in select_report_rows(grouped_by_channel[channel_name]):
            output_key = build_dedupe_key(row)
            if output_key in historical_output_keys or output_key in seen_current_keys:
                continue
            seen_current_keys.add(output_key)
            row["output_dedupe_key"] = output_key
            report_rows.append(row)
    return report_rows


def collect_legacy_report_rows(
    target_games: Iterable[Mapping[str, str]],
    previous_games: Iterable[Mapping[str, str]],
) -> list[dict]:
    previous_keys = {build_dedupe_key(dict(row)) for row in previous_games if is_reportable_row(dict(row))}
    grouped_targets: dict[str, list[dict]] = defaultdict(list)

    for row in target_games:
        row_dict = dict(row)
        if not is_reportable_row(row_dict):
            continue
        grouped_targets[row_dict["channel_name"]].append(row_dict)

    report_rows: list[dict] = []
    seen_current_keys: set[str] = set()
    for channel_name in sorted(grouped_targets):
        for row in select_report_rows(grouped_targets[channel_name]):
            output_key = build_dedupe_key(row)
            if output_key in previous_keys or output_key in seen_current_keys:
                continue
            seen_current_keys.add(output_key)
            row["output_dedupe_key"] = output_key
            report_rows.append(row)
    return report_rows


def is_reportable_row(row: Mapping[str, str]) -> bool:
    if not row.get("store_url"):
        return False
    if row.get("confidence") not in REPORTABLE_CONFIDENCE:
        return False
    if row.get("link_type") == "rejected":
        return False
    return True


def build_channel_items(report_rows: Iterable[Mapping[str, str]]) -> "OrderedDict[str, list[Mapping[str, str]]]":
    channel_items: "OrderedDict[str, list[Mapping[str, str]]]" = OrderedDict()
    for row in report_rows:
        channel_items.setdefault(row["channel_name"], []).append(row)
    return channel_items


def select_report_rows(rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[build_dedupe_key(row)].append(row)

    selected_by_key: list[dict] = []
    for candidates in grouped.values():
        selected_by_key.append(min(candidates, key=report_sort_key))

    grouped_by_name: dict[str, list[dict]] = defaultdict(list)
    for row in selected_by_key:
        grouped_by_name[row["normalized_game_name"] or build_dedupe_key(row)].append(row)

    selected: list[dict] = []
    for candidates in grouped_by_name.values():
        selected.append(min(candidates, key=report_sort_key))

    return sorted(selected, key=report_sort_key)


def report_sort_key(row: Mapping[str, str]) -> tuple[str, int, str, str]:
    return (
        row["report_date"],
        PLATFORM_PRIORITY.get(row["platform"], 99),
        row["game_name"],
        row["store_url"],
    )
