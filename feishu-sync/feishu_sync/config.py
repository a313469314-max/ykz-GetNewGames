from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SYNC_DIR = ROOT_DIR / "feishu-sync"
ENV_PATH = SYNC_DIR / ".env"


@dataclass(frozen=True)
class Config:
    app_id: str
    app_secret: str
    bitable_app_token: str
    webhook: str
    root_dir: Path


def load_dotenv(path: Path = ENV_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_config() -> Config:
    env = load_dotenv()
    config = Config(
        app_id=env.get("FEISHU_APP_ID", ""),
        app_secret=env.get("FEISHU_APP_SECRET", ""),
        bitable_app_token=env.get("FEISHU_BITABLE_APP_TOKEN", ""),
        webhook=env.get("FEISHU_WEBHOOK", ""),
        root_dir=ROOT_DIR,
    )
    missing = [
        name
        for name, value in [
            ("FEISHU_APP_ID", config.app_id),
            ("FEISHU_APP_SECRET", config.app_secret),
            ("FEISHU_BITABLE_APP_TOKEN", config.bitable_app_token),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing required config: {', '.join(missing)}")
    return config
