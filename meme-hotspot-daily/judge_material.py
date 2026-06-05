from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


TIMEZONE_NAME = "Asia/Shanghai"
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ITEMS_DIR = DATA_DIR / "items"
JUDGED_DIR = DATA_DIR / "judged"
OUTPUT_DIR = BASE_DIR / "output"

SUPPORTED_SOURCES = {"douyin", "bilibili"}
VERDICTS = {"pass", "reject", "review"}
RISK_LEVELS = {"low", "medium", "high"}
CSV_FIELDS = [
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
    "materialVerdict",
    "materialReason",
    "materialTags",
    "riskLevel",
]


@dataclass(frozen=True)
class LlmConfig:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: int


class ConfigError(RuntimeError):
    pass


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_llm_config() -> LlmConfig:
    load_env_file(BASE_DIR / ".env")
    missing = [
        key
        for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")
        if not os.environ.get(key)
    ]
    if missing:
        raise ConfigError(
            "缺少 LLM 配置："
            + ", ".join(missing)
            + "。请在环境变量或 meme-hotspot-daily/.env 中填写。"
        )

    timeout_raw = os.environ.get("LLM_TIMEOUT_SECONDS", "60")
    try:
        timeout_seconds = int(timeout_raw)
    except ValueError as exc:
        raise ConfigError("LLM_TIMEOUT_SECONDS 必须是整数。") from exc

    return LlmConfig(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model=os.environ["LLM_MODEL"],
        timeout_seconds=timeout_seconds,
    )


def chat_completions_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Judge whether collected hotspots are usable for game ad material inspiration."
    )
    parser.add_argument(
        "--date",
        help="Snapshot date in YYYY-MM-DD. Defaults to today in Asia/Shanghai.",
    )
    parser.add_argument(
        "--sources",
        default="douyin,bilibili",
        help="Comma-separated sources: douyin,bilibili.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of items judged in one LLM call. Defaults to 10.",
    )
    return parser.parse_args()


def parse_run_date(value: str | None) -> date:
    if value:
        return datetime.strptime(value, "%Y-%m-%d").date()
    return datetime.now(ZoneInfo(TIMEZONE_NAME)).date()


def source_items_path(run_date: date, source: str) -> Path:
    return ITEMS_DIR / run_date.isoformat() / f"{source}_items.json"


def load_source_items(run_date: date, source: str) -> list[dict[str, Any]]:
    path = source_items_path(run_date, source)
    if not path.exists():
        raise FileNotFoundError(f"找不到采集结果：{path}")
    data = read_json(path)
    if not isinstance(data, list):
        raise ValueError(f"采集结果不是列表：{path}")
    return [item for item in data if isinstance(item, dict)]


def shorten(value: Any, limit: int) -> str:
    text = "" if value is None else str(value).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def compact_item_for_prompt(batch_index: int, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": batch_index,
        "source": item.get("source"),
        "board": item.get("board"),
        "rank": item.get("rank"),
        "title": shorten(item.get("title"), 140),
        "desc": shorten(item.get("desc"), 260),
        "author": shorten(item.get("author"), 80),
        "hot": item.get("hot"),
        "url": shorten(item.get("url"), 220),
    }


def build_batch_messages(source: str, batch: list[dict[str, Any]]) -> list[dict[str, str]]:
    compact_items = [
        compact_item_for_prompt(index, item)
        for index, item in enumerate(batch, start=1)
    ]
    system = (
        "你是游戏买量素材热点筛选助手。你的任务不是判断内容是否属于游戏新闻，"
        "而是判断抖音热点或 B 站爆款视频是否适合被改编成游戏广告素材借势。"
        "只做可用性判断，不输出脚本，不输出创意方案。"
    )
    user = (
        "请逐条判断下面的条目是否适合做游戏广告素材借势。\n\n"
        "判断口径：\n"
        "- pass：有明确可迁移的视频模板、情绪梗、视觉形式、反差结构、挑战形式，且商业素材风险低。\n"
        "- reject：纯新闻、具体游戏宣发、政治/灾难/刑案/严重负面舆情、难以游戏化改编。\n"
        "- review：信息不足、可能可用但风险或语义不清。\n\n"
        "特别注意：\n"
        "- 抖音热榜经常只有短标题，可以基于标题做谨慎推断。\n"
        "- 目标是素材可用性，不是是否提到游戏。\n"
        "- 具体游戏皮肤、赛事、版本、宣发热点通常应 reject。\n"
        "- 明显社会负面、敏感新闻、灾难、刑案、政治争议应 reject，riskLevel 通常 high。\n"
        "- 有清晰表达模板、生活类反差、鬼畜/洗脑句式、挑战玩法、视觉形式的内容可 pass。\n"
        "- review 只用于确实信息不足或风险不清，不要把所有短标题都判成 review。\n\n"
        "字段要求：\n"
        "- materialVerdict 只能是 pass / reject / review。\n"
        "- materialReason 必须是一句中文短理由。\n"
        "- materialTags 输出 0 到 5 个中文标签，只写梗/情绪/表达模板类型。\n"
        "- riskLevel 只能是 low / medium / high。\n"
        "- 必须保留输入里的 index，且每个输入 index 都要返回一条结果。\n\n"
        "只返回 JSON，不要 Markdown，不要解释。返回格式：\n"
        "{"
        '"results":['
        "{"
        '"index":1,'
        '"materialVerdict":"pass|reject|review",'
        '"materialReason":"一句中文理由",'
        '"materialTags":["标签"],'
        '"riskLevel":"low|medium|high"'
        "}"
        "]"
        "}\n\n"
        f"来源：{source}\n"
        "待判断条目：\n"
        f"{json.dumps(compact_items, ensure_ascii=False)}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def call_llm(config: LlmConfig, messages: list[dict[str, str]]) -> dict[str, Any]:
    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": 0,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        chat_completions_url(config.base_url),
        data=body,
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "meme-hotspot-daily/1.0",
        },
        method="POST",
    )
    with urlopen(request, timeout=config.timeout_seconds) as response:
        response_body = response.read().decode("utf-8")
    response_data = json.loads(response_body)
    content = response_data["choices"][0]["message"]["content"]
    return parse_model_json(content)


def strip_code_fence(content: str) -> str:
    text = content.strip()
    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
        if text.lower().startswith("json\n"):
            text = text[5:].strip()
    return text


def parse_model_json(content: str) -> dict[str, Any]:
    text = strip_code_fence(content)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("模型返回不是 JSON 对象。")
    return data


def normalize_judgment(raw: dict[str, Any]) -> dict[str, Any]:
    verdict = str(raw.get("materialVerdict") or "review").strip().lower()
    if verdict not in VERDICTS:
        verdict = "review"

    risk_level = str(raw.get("riskLevel") or "medium").strip().lower()
    if risk_level not in RISK_LEVELS:
        risk_level = "medium"

    reason = str(raw.get("materialReason") or "模型未给出明确理由。").strip()
    tags_raw = raw.get("materialTags") or []
    if isinstance(tags_raw, str):
        tag_text = tags_raw
        for separator in ("；", "、", "|", "/", "\n"):
            tag_text = tag_text.replace(separator, ",")
        tags = [part.strip() for part in tag_text.split(",") if part.strip()]
    elif isinstance(tags_raw, list):
        tags = [str(tag).strip() for tag in tags_raw if str(tag).strip()]
    else:
        tags = []

    return {
        "materialVerdict": verdict,
        "materialReason": reason,
        "materialTags": tags[:5],
        "riskLevel": risk_level,
    }


def review_judgment(reason: str) -> dict[str, Any]:
    return {
        "materialVerdict": "review",
        "materialReason": reason,
        "materialTags": [],
        "riskLevel": "medium",
    }


def http_error_message(exc: HTTPError) -> str:
    return f"HTTP {exc.code} {exc.reason}".strip()


def batch_failure_judgments(batch: list[dict[str, Any]], reason: str) -> list[dict[str, Any]]:
    return [review_judgment(reason) for _ in batch]


def normalize_batch_results(
    raw: dict[str, Any],
    batch_size: int,
) -> list[dict[str, Any]]:
    results_raw = raw.get("results")
    if not isinstance(results_raw, list):
        raise ValueError("模型返回缺少 results 列表。")

    by_index: dict[int, dict[str, Any]] = {}
    for result in results_raw:
        if not isinstance(result, dict):
            continue
        try:
            index = int(result.get("index"))
        except (TypeError, ValueError):
            continue
        if 1 <= index <= batch_size and index not in by_index:
            by_index[index] = normalize_judgment(result)

    normalized: list[dict[str, Any]] = []
    for index in range(1, batch_size + 1):
        normalized.append(
            by_index.get(
                index,
                review_judgment("模型批量结果缺失，需人工复核。"),
            )
        )
    return normalized


def judge_batch(
    config: LlmConfig,
    source: str,
    batch: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    try:
        raw = call_llm(config, build_batch_messages(source, batch))
        return normalize_batch_results(raw, len(batch))
    except HTTPError as exc:
        return batch_failure_judgments(
            batch,
            f"模型批量判断失败，需人工复核：{http_error_message(exc)}",
        )
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        return batch_failure_judgments(
            batch,
            f"模型批量判断失败，需人工复核：{exc}",
        )


def iter_batches(
    items: list[dict[str, Any]],
    batch_size: int,
) -> list[tuple[int, list[dict[str, Any]]]]:
    return [
        (start, items[start : start + batch_size])
        for start in range(0, len(items), batch_size)
    ]


def count_verdicts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        verdict: sum(1 for row in rows if row.get("materialVerdict") == verdict)
        for verdict in ("pass", "reject", "review")
    }


def judge_source(
    run_date: date,
    source: str,
    config: LlmConfig,
    batch_size: int,
) -> tuple[int, Path, dict[str, Path], dict[str, int]]:
    items = load_source_items(run_date, source)
    judged: list[dict[str, Any]] = []
    batches = iter_batches(items, batch_size)
    total_batches = len(batches)

    for batch_number, (start, batch) in enumerate(batches, start=1):
        judgments = judge_batch(config, source, batch)
        for item, judgment in zip(batch, judgments):
            judged.append({**item, **judgment})

        batch_counts = count_verdicts(judgments)
        done = start + len(batch)
        print(
            f"{source} batch {batch_number}/{total_batches} "
            f"items {done}/{len(items)} "
            f"pass={batch_counts['pass']} "
            f"reject={batch_counts['reject']} "
            f"review={batch_counts['review']}",
            flush=True,
        )

    judged_path = JUDGED_DIR / run_date.isoformat() / f"{source}_judged.json"
    write_json(judged_path, judged)

    output_paths = write_verdict_csvs(run_date, source, judged)
    return len(judged), judged_path, output_paths, count_verdicts(judged)


def write_verdict_csvs(
    run_date: date,
    source: str,
    judged: list[dict[str, Any]],
) -> dict[str, Path]:
    output_dir = OUTPUT_DIR / run_date.isoformat()
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix_by_verdict = {
        "pass": "passed",
        "reject": "rejected",
        "review": "review",
    }
    paths: dict[str, Path] = {}
    for verdict, suffix in suffix_by_verdict.items():
        rows = [row for row in judged if row.get("materialVerdict") == verdict]
        path = output_dir / f"{source}_{suffix}.csv"
        paths[verdict] = path
        write_csv(path, rows)
    return paths


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            csv_row = dict(row)
            tags = csv_row.get("materialTags")
            if isinstance(tags, list):
                csv_row["materialTags"] = ";".join(str(tag) for tag in tags)
            writer.writerow(csv_row)


def parse_sources(value: str) -> list[str]:
    sources = [source.strip().lower() for source in value.split(",") if source.strip()]
    invalid_sources = [source for source in sources if source not in SUPPORTED_SOURCES]
    if invalid_sources:
        raise ConfigError(f"不支持的来源：{', '.join(invalid_sources)}")
    return sources


def main() -> int:
    args = parse_args()
    if args.batch_size < 1:
        print("--batch-size 必须大于 0。", file=sys.stderr)
        return 1

    try:
        run_date = parse_run_date(args.date)
        sources = parse_sources(args.sources)
        config = load_llm_config()
    except (ConfigError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    processed = 0
    for source in sources:
        try:
            count, judged_path, output_paths, counts = judge_source(
                run_date,
                source,
                config,
                args.batch_size,
            )
        except (FileNotFoundError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            continue

        processed += count
        print(f"{source}.judged={count}")
        print(
            f"{source}.counts="
            f"pass:{counts['pass']},reject:{counts['reject']},review:{counts['review']}"
        )
        print(f"{source}.json={judged_path}")
        for verdict, path in output_paths.items():
            print(f"{source}.{verdict}.csv={path}")

    if processed == 0:
        print("没有处理任何条目。请先运行 main.py 采集数据。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
