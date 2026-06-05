from __future__ import annotations

from datetime import date, datetime, time, timezone, timedelta


SHANGHAI_TZ = timezone(timedelta(hours=8))


def date_to_millis(value: str | date | datetime | None) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return int(value.timestamp() * 1000)
    if isinstance(value, date):
        parsed = value
    else:
        parsed = date.fromisoformat(str(value)[:10])
    dt = datetime.combine(parsed, time.min, tzinfo=SHANGHAI_TZ)
    return int(dt.timestamp() * 1000)


def datetime_to_millis(value: str | datetime | None) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value)
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return date_to_millis(text[:10])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=SHANGHAI_TZ)
    return int(dt.timestamp() * 1000)


def millis_to_date_string(value: object) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=SHANGHAI_TZ).date().isoformat()
    text = str(value)
    if text.isdigit():
        return datetime.fromtimestamp(int(text) / 1000, tz=SHANGHAI_TZ).date().isoformat()
    return text[:10]


def feishu_text_value(value: object) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(value)


def clean_record_fields(fields: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in fields.items() if value is not None}
