from __future__ import annotations

import json
from pathlib import Path

import requests

from src.dataeye_api import cookies_from_storage_state


def test_cookies_from_storage_state_preserves_domains_for_same_cookie_name(tmp_path: Path) -> None:
    storage_state_path = tmp_path / "state.json"
    storage_state_path.write_text(
        json.dumps(
            {
                "cookies": [
                    {"name": "SESSION", "value": "domestic", "domain": "adxray.dataeye.com", "path": "/"},
                    {"name": "SESSION", "value": "overseas", "domain": "oversea-v2.dataeye.com", "path": "/"},
                    {"name": "tokenglobal", "value": "shared", "domain": ".dataeye.com", "path": "/"},
                ]
            }
        ),
        encoding="utf-8",
    )

    session = requests.Session()
    session.cookies.update(cookies_from_storage_state(storage_state_path))
    prepared = session.prepare_request(requests.Request("GET", "https://oversea-v2.dataeye.com/api/product"))
    cookie_header = prepared.headers["Cookie"]

    assert "SESSION=overseas" in cookie_header
    assert "SESSION=domestic" not in cookie_header
    assert "tokenglobal=shared" in cookie_header
