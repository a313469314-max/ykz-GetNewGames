from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


DEFAULT_TIMEZONE = ZoneInfo("Asia/Shanghai")


def today_in_timezone(now: datetime | None = None, tz: ZoneInfo = DEFAULT_TIMEZONE) -> date:
    if now is None:
        return datetime.now(tz).date()
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    return now.astimezone(tz).date()


def default_stat_date(now: datetime | None = None, tz: ZoneInfo = DEFAULT_TIMEZONE) -> date:
    return today_in_timezone(now, tz) - timedelta(days=1)


def default_report_date(now: datetime | None = None, tz: ZoneInfo = DEFAULT_TIMEZONE) -> date:
    return today_in_timezone(now, tz)


def parse_date(value: str | date | datetime | None) -> date:
    if value is None:
        return default_stat_date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def date_range(start: str | date | datetime, end: str | date | datetime) -> list[date]:
    start_day = parse_date(start)
    end_day = parse_date(end)
    if end_day < start_day:
        raise ValueError(f"End date {end_day} is before start date {start_day}.")
    days: list[date] = []
    current = start_day
    while current <= end_day:
        days.append(current)
        current += timedelta(days=1)
    return days


def default_scan_dates(
    report_date: str | date | datetime | None = None,
    lookback_days: int = 3,
) -> list[date]:
    if lookback_days < 1:
        raise ValueError("lookback_days must be at least 1.")
    report_day = parse_date(report_date) if report_date is not None else default_report_date()
    return date_range(report_day - timedelta(days=lookback_days), report_day - timedelta(days=1))


def format_date(value: str | date | datetime | None) -> str:
    return parse_date(value).isoformat()


def dataeye_date_labels(value: str | date | datetime) -> list[str]:
    day = parse_date(value)
    return [
        day.isoformat(),
        f"{day.year}/{day.month}/{day.day}",
        f"{day.month}/{day.day}",
        f"{day.month:02d}-{day.day:02d}",
        f"{day.month}-{day.day}",
        f"{day.month}月{day.day}日",
        f"{day.month:02d}月{day.day:02d}日",
    ]
