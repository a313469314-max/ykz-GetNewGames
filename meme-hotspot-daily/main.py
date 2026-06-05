from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


TIMEZONE_NAME = "Asia/Shanghai"
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
ITEMS_DIR = DATA_DIR / "items"
OUTPUT_DIR = BASE_DIR / "output"

DEFAULT_BILI_TYPES = ["0", "119", "160", "5", "1", "4"]
BILI_TYPE_NAMES = {
    "0": "全站",
    "1": "动画",
    "3": "音乐",
    "4": "游戏",
    "5": "娱乐",
    "119": "鬼畜",
    "129": "舞蹈",
    "155": "时尚",
    "160": "生活",
    "168": "国创相关",
    "181": "影视",
    "188": "科技",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}


@dataclass
class HotspotItem:
    source: str
    board: str
    rank: int
    id: str
    title: str
    desc: str | None
    author: str | None
    hot: int | float | None
    timestamp: int | None
    url: str
    mobileUrl: str
    cover: str | None
    capturedAt: str


def fetch_json(url: str, *, referer: str | None = None, timeout: int = 20) -> dict[str, Any]:
    headers = dict(HEADERS)
    if referer:
        headers["Referer"] = referer
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        body = response.read()
    return json.loads(body.decode("utf-8"))


def ensure_dirs(run_date: date) -> tuple[Path, Path, Path]:
    raw_date_dir = RAW_DIR / run_date.isoformat()
    items_date_dir = ITEMS_DIR / run_date.isoformat()
    output_date_dir = OUTPUT_DIR / run_date.isoformat()
    raw_date_dir.mkdir(parents=True, exist_ok=True)
    items_date_dir.mkdir(parents=True, exist_ok=True)
    output_date_dir.mkdir(parents=True, exist_ok=True)
    return raw_date_dir, items_date_dir, output_date_dir


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def first_cover(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, dict):
        urls = value.get("url_list")
        if isinstance(urls, list) and urls:
            return str(urls[0])
        if isinstance(urls, str) and urls.strip():
            return urls.split()[0]
    return None


def fetch_douyin(raw_dir: Path, captured_at: str) -> list[HotspotItem]:
    query = {
        "device_platform": "webapp",
        "aid": "6383",
        "channel": "channel_pc_web",
        "detail_list": "1",
    }
    url = f"https://www.douyin.com/aweme/v1/web/hot/search/list/?{urlencode(query)}"
    payload = fetch_json(url, referer="https://www.douyin.com/hot")
    write_json(raw_dir / "douyin" / "hot.json", payload)

    word_list = payload.get("data", {}).get("word_list", []) or []
    items: list[HotspotItem] = []
    for index, item in enumerate(word_list, start=1):
        sentence_id = str(item.get("sentence_id") or "")
        rank = int(item.get("position") or index)
        items.append(
            HotspotItem(
                source="douyin",
                board="抖音热榜",
                rank=rank,
                id=sentence_id,
                title=str(item.get("word") or "").strip(),
                desc=None,
                author=None,
                hot=item.get("hot_value"),
                timestamp=item.get("event_time"),
                url=f"https://www.douyin.com/hot/{sentence_id}",
                mobileUrl=f"https://www.douyin.com/hot/{sentence_id}",
                cover=first_cover(item.get("word_cover")),
                capturedAt=captured_at,
            )
        )
    return items


def fetch_bilibili_board(bili_type: str, raw_dir: Path, captured_at: str) -> list[HotspotItem]:
    payload = fetch_bilibili_payload(bili_type)
    write_json(raw_dir / "bilibili" / f"{bili_type}.json", payload)

    board_name = BILI_TYPE_NAMES.get(bili_type, bili_type)
    videos = payload.get("data", {}).get("list", []) or []
    items: list[HotspotItem] = []
    for index, item in enumerate(videos, start=1):
        bvid = str(item.get("bvid") or "")
        owner = item.get("owner") or {}
        stat = item.get("stat") or {}
        author = owner.get("name") if isinstance(owner, dict) else item.get("author")
        hot = stat.get("view") if isinstance(stat, dict) else None
        if hot is None:
            hot = item.get("play") or item.get("video_review")
        cover = item.get("pic")
        if isinstance(cover, str):
            cover = cover.replace("http:", "https:")
        items.append(
            HotspotItem(
                source="bilibili",
                board=f"B站{board_name}榜",
                rank=index,
                id=bvid,
                title=str(item.get("title") or "").strip(),
                desc=str(item.get("desc") or "").strip() or None,
                author=author,
                hot=hot,
                timestamp=item.get("pubdate"),
                url=item.get("short_link_v2") or f"https://www.bilibili.com/video/{bvid}",
                mobileUrl=f"https://m.bilibili.com/video/{bvid}",
                cover=cover,
                capturedAt=captured_at,
            )
        )
    return items


def fetch_bilibili_payload(bili_type: str) -> dict[str, Any]:
    query = {"rid": bili_type, "type": "all"}
    modern_url = f"https://api.bilibili.com/x/web-interface/ranking/v2?{urlencode(query)}"
    modern_payload = fetch_json(modern_url, referer="https://www.bilibili.com/ranking/all")
    modern_list = modern_payload.get("data", {}).get("list", []) or []
    if modern_payload.get("code") == 0 and modern_list:
        modern_payload["_crawlerEndpoint"] = "ranking_v2"
        return modern_payload

    legacy_url = f"https://api.bilibili.com/x/web-interface/ranking?{urlencode(query)}"
    legacy_payload = fetch_json(legacy_url, referer="https://www.bilibili.com/ranking/all")
    legacy_payload["_crawlerEndpoint"] = "ranking_legacy"
    return legacy_payload


def fetch_bilibili(types: list[str], raw_dir: Path, captured_at: str) -> list[HotspotItem]:
    items: list[HotspotItem] = []
    for index, bili_type in enumerate(types):
        if index:
            time.sleep(0.8)
        items.extend(fetch_bilibili_board(bili_type, raw_dir, captured_at))
    return items


def write_source_items(
    source_key: str,
    source_title: str,
    items: list[HotspotItem],
    items_dir: Path,
    output_dir: Path,
) -> tuple[Path, Path, Path]:
    rows = [asdict(item) for item in items]
    json_path = items_dir / f"{source_key}_items.json"
    csv_path = output_dir / f"{source_key}_items.csv"
    txt_path = output_dir / f"{source_key}_items.txt"

    write_json(json_path, rows)

    fieldnames = [
        "source",
        "board",
        "rank",
        "id",
        "title",
        "desc",
        "author",
        "hot",
        "timestamp",
        "url",
        "mobileUrl",
        "cover",
        "capturedAt",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        f"{source_title}采集",
        f"总条目：{len(items)}",
        "",
    ]
    current_board = None
    for item in items:
        if item.board != current_board:
            current_board = item.board
            lines.extend(["", f"## {current_board}"])
        hot_text = f" | hot={item.hot}" if item.hot is not None else ""
        lines.append(f"{item.rank}. {item.title}{hot_text}")
        lines.append(f"   {item.url}")
    txt_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return json_path, csv_path, txt_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Douyin hotspots and Bilibili viral videos.")
    parser.add_argument("--date", help="Snapshot date in YYYY-MM-DD. Defaults to today in Asia/Shanghai.")
    parser.add_argument(
        "--sources",
        default="douyin,bilibili",
        help="Comma-separated sources: douyin,bilibili.",
    )
    parser.add_argument(
        "--bili-types",
        default=",".join(DEFAULT_BILI_TYPES),
        help="Comma-separated Bilibili ranking type IDs.",
    )
    return parser.parse_args()


def parse_run_date(value: str | None) -> date:
    if value:
        return datetime.strptime(value, "%Y-%m-%d").date()
    return datetime.now(ZoneInfo(TIMEZONE_NAME)).date()


def main() -> int:
    args = parse_args()
    run_date = parse_run_date(args.date)
    captured_at = datetime.now(ZoneInfo(TIMEZONE_NAME)).isoformat(timespec="seconds")
    raw_dir, items_dir, output_dir = ensure_dirs(run_date)

    sources = {source.strip().lower() for source in args.sources.split(",") if source.strip()}
    bili_types = [value.strip() for value in args.bili_types.split(",") if value.strip()]

    outputs: list[tuple[str, int, Path, Path, Path]] = []
    if "douyin" in sources:
        douyin_items = fetch_douyin(raw_dir, captured_at)
        outputs.append(
            (
                "douyin",
                len(douyin_items),
                *write_source_items("douyin", "抖音热榜", douyin_items, items_dir, output_dir),
            )
        )
    if "bilibili" in sources:
        bilibili_items = fetch_bilibili(bili_types, raw_dir, captured_at)
        outputs.append(
            (
                "bilibili",
                len(bilibili_items),
                *write_source_items("bilibili", "B站爆款视频", bilibili_items, items_dir, output_dir),
            )
        )

    print(f"date={run_date.isoformat()}")
    for source, count, json_path, csv_path, txt_path in outputs:
        print(f"{source}.items={count}")
        print(f"{source}.json={json_path}")
        print(f"{source}.csv={csv_path}")
        print(f"{source}.txt={txt_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
