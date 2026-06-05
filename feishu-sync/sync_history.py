from __future__ import annotations

import re
import sqlite3
import subprocess
import sys
from pathlib import Path

from feishu_sync.config import ROOT_DIR


DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def main() -> int:
    dates = sorted(discover_dataeye_dates(ROOT_DIR) | discover_youtube_dates(ROOT_DIR))
    if not dates:
        print("no historical dates found")
        return 0

    print("historical dates:")
    for date in dates:
        print(f"- {date}")

    for date in dates:
        print(f"\n== sync {date} ==")
        result = subprocess.run(
            [
                sys.executable,
                "sync_all.py",
                "--date",
                date,
                "--allow-missing-sources",
            ],
            cwd=Path(__file__).resolve().parent,
            check=False,
        )
        if result.returncode != 0:
            return result.returncode
    return 0


def discover_dataeye_dates(root_dir: Path) -> set[str]:
    dates: set[str] = set()
    for folder in (
        root_dir / "adx" / "data" / "daily-new-games-company",
        root_dir / "adx" / "data" / "daily-new-games",
    ):
        if folder.exists():
            dates.update(path.stem for path in folder.glob("*.json") if DATE_RE.fullmatch(path.stem))

    try:
        raw = subprocess.check_output(
            ["git", "-C", str(root_dir), "ls-tree", "-r", "--name-only", "HEAD", "--", "adx/data/daily-new-games"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return dates

    for line in raw.splitlines():
        path = Path(line)
        if path.suffix == ".json" and DATE_RE.fullmatch(path.stem):
            dates.add(path.stem)
    return dates


def discover_youtube_dates(root_dir: Path) -> set[str]:
    db_path = root_dir / "youtube-newgame-daily" / "data" / "youtube_newgame.db"
    if not db_path.exists():
        return set()

    dates: set[str] = set()
    connection = sqlite3.connect(db_path)
    try:
        for table, column in (("report_runs", "target_date"), ("games", "report_date")):
            try:
                rows = connection.execute(f"SELECT DISTINCT {column} FROM {table} WHERE {column} != ''")
            except sqlite3.Error:
                continue
            dates.update(str(row[0]) for row in rows if DATE_RE.fullmatch(str(row[0])))
    finally:
        connection.close()
    return dates


if __name__ == "__main__":
    raise SystemExit(main())
