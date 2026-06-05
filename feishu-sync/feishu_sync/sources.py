from __future__ import annotations

import json
import re
import sqlite3
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


REPORTABLE_CONFIDENCE = {"high", "medium"}


@dataclass(frozen=True)
class SourceData:
    raw_rows: list[dict[str, Any]]
    detail_rows: list[dict[str, Any]]
    overview_rows: list[dict[str, Any]]
    report_path: Path | None = None


@dataclass(frozen=True)
class SourceSpec:
    name: str
    raw_table: str
    raw_date_field: str
    loader: Callable[[Path, str, str], SourceData]


def normalize_game_name(name: str) -> str:
    lowered = (name or "").casefold()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", lowered)


def normalize_store_url(url: str) -> str:
    return (url or "").strip().split("#", 1)[0]


def build_dedupe_key(
    *,
    package_id: str = "",
    apple_app_id: str = "",
    dataeye_product_id: str = "",
    store_url: str = "",
    normalized_game_name: str = "",
    platform: str = "",
) -> str:
    if package_id:
        return f"pkg:{package_id.lower()}"
    if apple_app_id:
        return f"ios:{apple_app_id}"
    if dataeye_product_id:
        return f"dataeye:{dataeye_product_id}"
    if store_url:
        return f"url:{normalize_store_url(store_url).lower()}"
    return f"name_platform:{normalized_game_name}:{platform}"


def build_section_overview_row(
    *,
    report_date: str,
    section_name: str,
    source: str,
    display_order: int,
    products: list[dict[str, Any]],
    meta_fields: tuple[str, ...],
    import_batch_id: str,
) -> dict[str, Any]:
    product_count = len(products)
    card_title = f"{section_name} · {product_count} 款"
    return {
        "卡片标题": card_title,
        "报告日期": report_date,
        "栏目": section_name,
        "展示顺序": display_order,
        "产品数量": product_count,
        "产品列表": format_compact_product_list(products, meta_fields),
        "展示备注": "完整链接和跟进字段见 03_新游戏明细",
        "明细说明": f"在 03_新游戏明细 中筛选：报告日期={report_date}，来源={source}",
        "来源": source,
        "去重Key": f"overview:{report_date}:{source}",
        "importBatchId": import_batch_id,
        "写入时间": datetime.now().isoformat(timespec="seconds"),
    }


def format_compact_product_list(products: list[dict[str, Any]], meta_fields: tuple[str, ...]) -> str:
    if not products:
        return "无新增"

    lines: list[str] = []
    for index, product in enumerate(products, start=1):
        name = str(product.get("游戏名称", "")).strip() or "未命名产品"
        meta = [str(product.get(field, "")).strip() for field in meta_fields]
        meta_text = " | ".join(value for value in meta if value)
        lines.append(f"{index:02d}. {name}" + (f" | {meta_text}" if meta_text else ""))
    return "\n".join(lines)


def load_dataeye(root_dir: Path, report_date: str, import_batch_id: str) -> SourceData:
    rows = load_dataeye_json(root_dir, report_date)
    raw_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []
    overview_rows: list[dict[str, Any]] = []

    for row in rows:
        product_id = str(row.get("productId", "")).strip()
        platform = str(row.get("platformName", "")).strip()
        product_name = str(row.get("productName", "")).strip()
        company_name = str(row.get("companyName", "")).strip()
        dedupe_key = build_dedupe_key(
            dataeye_product_id=product_id,
            normalized_game_name=normalize_game_name(product_name),
            platform=platform,
        )
        raw_rows.append(
            {
                "productName": product_name,
                "statDate": row.get("statDate", report_date),
                "productId": product_id,
                "platformName": platform,
                "type": str(row.get("type", "")),
                "companyName": company_name,
                "productIcon": str(row.get("productIcon", "")),
                "stableProductIcon": str(row.get("stableProductIcon", "")),
                "detailUrl": str(row.get("detailUrl", "")),
                "fetchedAt": str(row.get("fetchedAt", "")),
                "dedupeKey": dedupe_key,
                "importBatchId": import_batch_id,
            }
        )
        detail_rows.append(
            {
                "卡片标题": product_name,
                "游戏名称": product_name,
                "报告日期": report_date,
                "来源": "DataEye",
                "来源渠道": platform,
                "平台": platform,
                "厂商名": company_name,
                "商店链接": "",
                "DataEye详情链接": str(row.get("detailUrl", "")),
                "YouTube视频链接": "",
                "包名": "",
                "Apple App ID": "",
                "DataEye产品ID": product_id,
                "置信度": "high",
                "去重Key": dedupe_key,
                "关注级别": "待判断",
                "跟进状态": "未看",
                "备注": "",
                "importBatchId": import_batch_id,
                "写入时间": datetime.now().isoformat(timespec="seconds"),
            }
        )

    overview_rows.append(
        build_section_overview_row(
            report_date=report_date,
            section_name="国内 DataEye 新品",
            source="DataEye",
            display_order=10,
            products=detail_rows,
            meta_fields=("厂商名", "平台"),
            import_batch_id=import_batch_id,
        )
    )
    report_path = root_dir / "adx" / "output" / f"dataeye_new_games_company_{report_date}.txt"
    return SourceData(
        raw_rows=raw_rows,
        detail_rows=detail_rows,
        overview_rows=overview_rows,
        report_path=report_path if report_path.exists() else None,
    )


def load_dataeye_json(root_dir: Path, report_date: str) -> list[dict[str, Any]]:
    candidates = (
        root_dir / "adx" / "data" / "daily-new-games-company" / f"{report_date}.json",
        root_dir / "adx" / "data" / "daily-new-games" / f"{report_date}.json",
    )
    for path in candidates:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))

    git_path = f"adx/data/daily-new-games/{report_date}.json"
    try:
        raw = subprocess.check_output(
            ["git", "-C", str(root_dir), "show", f"HEAD:{git_path}"],
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise FileNotFoundError(f"DataEye JSON not found for {report_date}") from exc

    return json.loads(raw.decode("utf-8"))


def load_youtube(root_dir: Path, report_date: str, import_batch_id: str) -> SourceData:
    db_path = root_dir / "youtube-newgame-daily" / "data" / "youtube_newgame.db"
    if not db_path.exists():
        raise FileNotFoundError(f"YouTube database not found: {db_path}")

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        run = connection.execute(
            """
            SELECT id, run_date, target_date, report_path
            FROM report_runs
            WHERE target_date = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (report_date,),
        ).fetchone()

        if run:
            source_rows = list(
                connection.execute(
                    """
                    SELECT
                        source_report_date AS report_date,
                        channel_name,
                        game_name,
                        normalized_game_name,
                        store_url,
                        package_id,
                        apple_app_id,
                        platform,
                        video_id,
                        output_dedupe_key AS dedupe_key
                    FROM report_output_items
                    WHERE run_date = ?
                    ORDER BY source_report_date, channel_name, id
                    """,
                    (run["run_date"],),
                )
            )
            report_path = Path(run["report_path"]) if run["report_path"] else None
        else:
            source_rows = list(
                connection.execute(
                    """
                    SELECT
                        report_date,
                        channel_name,
                        game_name,
                        normalized_game_name,
                        store_url,
                        package_id,
                        apple_app_id,
                        platform,
                        video_id,
                        '' AS dedupe_key
                    FROM games
                    WHERE report_date = ?
                        AND store_url != ''
                        AND confidence IN ('high', 'medium')
                        AND link_type != 'rejected'
                    ORDER BY channel_name, id
                    """,
                    (report_date,),
                )
            )
            report_path = root_dir / "youtube-newgame-daily" / "output" / f"youtube_new_games_{report_date}.txt"

        raw_rows: list[dict[str, Any]] = []
        detail_rows: list[dict[str, Any]] = []
        overview_rows: list[dict[str, Any]] = []
        for row in source_rows:
            row_dict = dict(row)
            game_name = str(row_dict.get("game_name", "")).strip()
            platform = str(row_dict.get("platform", "")).strip()
            store_url = str(row_dict.get("store_url", "")).strip()
            package_id = str(row_dict.get("package_id", "")).strip()
            apple_app_id = str(row_dict.get("apple_app_id", "")).strip()
            normalized_name = str(row_dict.get("normalized_game_name", "")) or normalize_game_name(game_name)
            dedupe_key = str(row_dict.get("dedupe_key", "")).strip() or build_dedupe_key(
                package_id=package_id,
                apple_app_id=apple_app_id,
                store_url=store_url,
                normalized_game_name=normalized_name,
                platform=platform,
            )
            video_id = str(row_dict.get("video_id", "")).strip()
            video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
            raw_rows.append(
                load_youtube_raw_row(
                    connection,
                    row_dict,
                    dedupe_key,
                    import_batch_id,
                    video_url,
                    report_date,
                )
            )
            detail_rows.append(
                {
                    "卡片标题": game_name,
                    "游戏名称": game_name,
                    "报告日期": report_date,
                    "来源": "YouTube",
                    "来源渠道": str(row_dict.get("channel_name", "")),
                    "平台": platform,
                    "厂商名": "",
                    "商店链接": store_url,
                    "DataEye详情链接": "",
                    "YouTube视频链接": video_url,
                    "包名": package_id,
                    "Apple App ID": apple_app_id,
                    "DataEye产品ID": "",
                    "置信度": "high",
                    "去重Key": dedupe_key,
                    "关注级别": "待判断",
                    "跟进状态": "未看",
                    "备注": "",
                    "importBatchId": import_batch_id,
                    "写入时间": datetime.now().isoformat(timespec="seconds"),
                }
            )

        overview_rows.append(
            build_section_overview_row(
                report_date=report_date,
                section_name="YouTube 新游线索",
                source="YouTube",
                display_order=20,
                products=detail_rows,
                meta_fields=("来源渠道", "平台"),
                import_batch_id=import_batch_id,
            )
        )
        resolved_report_path = resolve_report_path(root_dir, report_path)
        return SourceData(
            raw_rows=raw_rows,
            detail_rows=detail_rows,
            overview_rows=overview_rows,
            report_path=resolved_report_path,
        )
    finally:
        connection.close()


def load_youtube_raw_row(
    connection: sqlite3.Connection,
    row: dict[str, Any],
    dedupe_key: str,
    import_batch_id: str,
    video_url: str,
    report_date: str,
) -> dict[str, Any]:
    video_id = str(row.get("video_id", "")).strip()
    game_row = connection.execute(
        """
        SELECT
            video_title,
            link_type,
            confidence,
            reject_reason,
            normalized_store_url
        FROM games
        WHERE video_id = ? AND store_url = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (video_id, row.get("store_url", "")),
    ).fetchone()
    game_data = dict(game_row) if game_row else {}
    return {
        "game_name": str(row.get("game_name", "")),
        "report_date": report_date,
        "channel_name": str(row.get("channel_name", "")),
        "video_id": video_id,
        "video_title": str(game_data.get("video_title", "")),
        "video_url": video_url,
        "store_url": str(row.get("store_url", "")),
        "package_id": str(row.get("package_id", "")),
        "apple_app_id": str(row.get("apple_app_id", "")),
        "platform": str(row.get("platform", "")),
        "link_type": str(game_data.get("link_type", "")),
        "confidence": str(game_data.get("confidence", "")),
        "reject_reason": str(game_data.get("reject_reason", "")),
        "normalized_game_name": str(row.get("normalized_game_name", "")),
        "normalized_store_url": str(game_data.get("normalized_store_url", "")),
        "dedupeKey": dedupe_key,
        "importBatchId": import_batch_id,
    }


def resolve_report_path(root_dir: Path, report_path: Path | None) -> Path | None:
    if report_path is None:
        return None
    if report_path.is_absolute():
        return report_path if report_path.exists() else None
    for base in [root_dir / "youtube-newgame-daily", root_dir]:
        candidate = base / report_path
        if candidate.exists():
            return candidate
    return report_path


SOURCE_REGISTRY: tuple[SourceSpec, ...] = (
    SourceSpec(
        name="DataEye",
        raw_table="04_DataEye源数据",
        raw_date_field="statDate",
        loader=load_dataeye,
    ),
    SourceSpec(
        name="YouTube",
        raw_table="05_YouTube源数据",
        raw_date_field="report_date",
        loader=load_youtube,
    ),
)
