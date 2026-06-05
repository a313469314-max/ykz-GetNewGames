from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from src.dataeye_auth import load_settings


def test_default_storage_state_uses_repo_root(tmp_path: Path) -> None:
    project_root = tmp_path / "overseas-casual-newgame-daily"
    project_root.mkdir()
    env = {"DATAEYE_EMAIL": "user@example.com", "DATAEYE_PASSWORD": "password"}

    with patch.dict(os.environ, env, clear=True):
        settings = load_settings(project_root)

    assert settings.storage_state == tmp_path / ".auth" / "dataeye-state.json"
    assert settings.legacy_storage_states == (project_root / ".auth" / "dataeye-state.json",)


def test_credentials_are_optional_when_reusing_storage_state(tmp_path: Path) -> None:
    project_root = tmp_path / "overseas-casual-newgame-daily"
    project_root.mkdir()

    with patch.dict(os.environ, {}, clear=True):
        settings = load_settings(project_root)

    assert settings.email == ""
    assert settings.password == ""
    assert settings.storage_state == tmp_path / ".auth" / "dataeye-state.json"


def test_configured_relative_storage_state_stays_project_relative(tmp_path: Path) -> None:
    project_root = tmp_path / "overseas-casual-newgame-daily"
    project_root.mkdir()
    env = {
        "DATAEYE_EMAIL": "user@example.com",
        "DATAEYE_PASSWORD": "password",
        "DATAEYE_STORAGE_STATE": "../.auth/custom-state.json",
    }

    with patch.dict(os.environ, env, clear=True):
        settings = load_settings(project_root)

    assert settings.storage_state == tmp_path / ".auth" / "custom-state.json"


def test_legacy_project_local_storage_state_env_uses_shared_target(tmp_path: Path) -> None:
    project_root = tmp_path / "overseas-casual-newgame-daily"
    project_root.mkdir()
    env = {
        "DATAEYE_EMAIL": "user@example.com",
        "DATAEYE_PASSWORD": "password",
        "DATAEYE_STORAGE_STATE": ".auth/dataeye-state.json",
    }

    with patch.dict(os.environ, env, clear=True):
        settings = load_settings(project_root)

    assert settings.storage_state == tmp_path / ".auth" / "dataeye-state.json"
    assert settings.legacy_storage_states == (project_root / ".auth" / "dataeye-state.json",)
