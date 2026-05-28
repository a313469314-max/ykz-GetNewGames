from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app_models import DateWindow


def build_date_window(timezone_name: str, now: datetime | None = None) -> DateWindow:
    tz = ZoneInfo(timezone_name)
    local_now = now.astimezone(tz) if now else datetime.now(tz)
    run_date = local_now.date()
    target_date = run_date - timedelta(days=1)
    previous_date = run_date - timedelta(days=3)

    previous_start_local = datetime.combine(previous_date, time.min, tzinfo=tz)
    target_end_local = datetime.combine(target_date + timedelta(days=1), time.min, tzinfo=tz)

    return DateWindow(
        run_date=run_date,
        previous_date=previous_date,
        target_date=target_date,
        previous_start_local=previous_start_local,
        target_end_local=target_end_local,
        previous_start_utc=previous_start_local.astimezone(timezone.utc),
        target_end_utc=target_end_local.astimezone(timezone.utc),
    )


def to_local_date(value: datetime, timezone_name: str) -> date:
    return value.astimezone(ZoneInfo(timezone_name)).date()
