from __future__ import annotations

import sys
from pathlib import Path

from lifeplanner_core.installer_catalog import default_module_sources
from lifeplanner_core.repositories import (
    BUDGETMANAGER_REPOSITORY,
    CORE_LATEST_MANIFEST_URL,
    CORE_REPOSITORY,
    FPM_REPOSITORY,
)
from lifeplanner_core.settings import SettingsStore


def test_official_repository_registry() -> None:
    assert CORE_REPOSITORY == "sloogy/Livemanager"
    assert BUDGETMANAGER_REPOSITORY == "sloogy/Budgetmanager"
    assert FPM_REPOSITORY == "sloogy/FPM"
    sources = {item.module_id: item for item in default_module_sources()}
    assert sources["budgetmanager"].repository == BUDGETMANAGER_REPOSITORY
    assert sources["fpm"].repository == FPM_REPOSITORY
    suffix = "Windows_x86_64" if sys.platform.startswith("win") else "Linux_x86_64"
    assert suffix in sources["budgetmanager"].asset_pattern
    assert suffix in sources["fpm"].asset_pattern


def test_core_updater_defaults_to_livemanager(tmp_path: Path) -> None:
    settings = SettingsStore(tmp_path / "settings.json")
    assert settings.get("updates")["manifest_url"] == CORE_LATEST_MANIFEST_URL
    assert "/sloogy/Livemanager/releases/latest/download/" in CORE_LATEST_MANIFEST_URL


def test_source_launchers_are_single_root_and_do_not_prepare_dev_modules() -> None:
    root = Path(__file__).resolve().parents[1]
    linux = (root / "start-linux.sh").read_text(encoding="utf-8")
    windows = (root / "start-windows.bat").read_text(encoding="utf-8")
    assert "LIFEPLANNER_PORTABLE=1" in linux
    assert 'LIFEPLANNER_DATA_DIR="$PWD/data"' in linux
    assert "prepare_dev_modules.py" not in linux
    assert "LIFEPLANNER_PORTABLE=1" in windows
    assert "LIFEPLANNER_DATA_DIR=%CD%\\data" in windows
    assert "prepare_dev_modules.py" not in windows


def test_windows_installer_source_is_marked_single_root() -> None:
    root = Path(__file__).resolve().parents[1]
    build = (root / "tools" / "build_release.py").read_text(encoding="utf-8")
    assert '(installer_source / "portable.flag").write_text' in build
