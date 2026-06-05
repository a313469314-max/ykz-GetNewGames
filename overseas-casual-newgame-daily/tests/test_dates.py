from datetime import datetime
from zoneinfo import ZoneInfo

from src.dates import dataeye_date_labels, default_scan_dates, default_stat_date


def test_default_stat_date_uses_shanghai_yesterday() -> None:
    now = datetime(2026, 6, 4, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert default_stat_date(now).isoformat() == "2026-06-03"


def test_dataeye_date_labels_include_common_formats() -> None:
    labels = dataeye_date_labels("2026-06-02")
    assert "2026-06-02" in labels
    assert "06-02" in labels
    assert "6月2日" in labels


def test_default_scan_dates_use_previous_three_days() -> None:
    days = default_scan_dates("2026-06-04")
    assert [day.isoformat() for day in days] == ["2026-06-01", "2026-06-02", "2026-06-03"]
