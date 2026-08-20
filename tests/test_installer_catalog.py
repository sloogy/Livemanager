from __future__ import annotations

import json
from pathlib import Path

import pytest

from lifeplanner_core.installer_catalog import (
    InstallerCatalogError,
    ModuleSource,
    load_module_sources,
    query_module_release,
    read_catalog_ini,
    write_catalog_ini,
)


class _Response:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _Session:
    def __init__(self, payload):
        self.payload = payload
        self.requested = []

    def get(self, url, headers, timeout):
        self.requested.append((url, headers, timeout))
        return _Response(self.payload)


def test_load_sources_requires_real_repository_and_unique_id(tmp_path: Path) -> None:
    source = tmp_path / "sources.json"
    source.write_text(
        json.dumps(
            {
                "schema": "lifeplanner.installer-sources.v1",
                "modules": [
                    {
                        "id": "budgetmanager",
                        "name": "BudgetManager",
                        "repository": "example/BudgetManager",
                        "asset_pattern": r"budgetmanager_(?P<version>.+)_Windows_x86_64\.lpmodule",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    loaded = load_module_sources(source)
    assert loaded[0].repository == "example/BudgetManager"

    source.write_text(
        json.dumps(
            {
                "schema": "lifeplanner.installer-sources.v1",
                "modules": [
                    {
                        "id": "bad/id",
                        "name": "Bad",
                        "repository": "example/Bad",
                        "asset_pattern": ".*",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(InstallerCatalogError, match="Modul-ID"):
        load_module_sources(source)


def test_repository_query_finds_latest_release_that_contains_module_asset() -> None:
    source = ModuleSource(
        module_id="budgetmanager",
        name="BudgetManager",
        repository="example/BudgetManager",
        asset_pattern=r"budgetmanager_(?P<version>[0-9.]+)_Windows_x86_64\.lpmodule",
    )
    session = _Session(
        [
            {
                "tag_name": "v2.2.50",
                "draft": False,
                "prerelease": False,
                "assets": [{"name": "BudgetManager_Setup.exe", "size": 100, "browser_download_url": "https://github.com/x/y"}],
            },
            {
                "tag_name": "v2.2.49",
                "draft": False,
                "prerelease": False,
                "body": "Stabile LifePlanner-Ausgabe",
                "assets": [
                    {
                        "name": "budgetmanager_2.2.49_Windows_x86_64.lpmodule",
                        "size": 1234,
                        "browser_download_url": "https://github.com/example/BudgetManager/releases/download/v2.2.49/budgetmanager_2.2.49_Windows_x86_64.lpmodule",
                    }
                ],
            },
        ]
    )
    release = query_module_release(source, session=session)
    assert release.available is True
    assert release.version == "2.2.49"
    assert release.asset_size == 1234
    assert session.requested[0][0].endswith("/releases?per_page=20")


def test_catalog_ini_roundtrip(tmp_path: Path) -> None:
    source = ModuleSource(
        module_id="fpm",
        name="FPM",
        repository="example/FPM",
        asset_pattern=r"fpm_(?P<version>[0-9.]+)_Windows_x86_64\.lpmodule",
    )
    session = _Session(
        [
            {
                "tag_name": "v0.3.04",
                "draft": False,
                "prerelease": False,
                "assets": [
                    {
                        "name": "fpm_0.3.04_Windows_x86_64.lpmodule",
                        "size": 99,
                        "browser_download_url": "https://github.com/example/FPM/releases/download/v0.3.04/fpm_0.3.04_Windows_x86_64.lpmodule",
                    }
                ],
            }
        ]
    )
    release = query_module_release(source, session=session)
    target = write_catalog_ini([release], tmp_path / "catalog.ini")
    restored = read_catalog_ini(target)
    assert restored == (release,)


def test_installer_enforces_one_program_and_uses_github_catalog() -> None:
    root = Path(__file__).resolve().parents[1]
    installer = (root / "installer" / "LifePlanner.iss").read_text(encoding="utf-8")
    build = (root / "tools" / "build_release.py").read_text(encoding="utf-8")
    bootstrap = (root / "lifeplanner_core" / "installer_bootstrap.py").read_text(encoding="utf-8")
    assert "Mindestens ein Programm" in installer
    assert "CheckedModuleCount < 1" in installer
    assert "catalog --sources" in installer
    assert "install --catalog" in installer
    assert "Excludes: \"modules\\*" in installer
    assert "_write_installer_sources" in build
    assert "LifePlannerInstallerBootstrap.spec" in build
    assert "if not info.signed" in bootstrap
    assert "Remote-Modul" in bootstrap and "wird abgelehnt" in bootstrap


def test_bootstrap_installs_selected_signed_module_transactionally(tmp_path: Path, monkeypatch) -> None:
    import base64
    import shutil
    from argparse import Namespace

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption, PublicFormat

    import lifeplanner_core.installer_bootstrap as bootstrap
    from lifeplanner_core.installer_catalog import ModuleRelease
    from lifeplanner_core.updater.package_builder import build_component_package

    private = Ed25519PrivateKey.generate()
    private_raw = private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    public_raw = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    private_b64 = base64.b64encode(private_raw).decode("ascii")
    monkeypatch.setenv("LIFEPLANNER_UPDATE_PUBLIC_KEY_B64", base64.b64encode(public_raw).decode("ascii"))
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "data"))

    app = tmp_path / "app"
    (app / "modules").mkdir(parents=True)
    payload = tmp_path / "payload"
    (payload / "Demo").mkdir(parents=True)
    (payload / "module.json").write_text(
        json.dumps(
            {
                "schema": "lifeplanner.module.v1",
                "id": "demo",
                "name": "Demo",
                "version": "1.0.0",
                "description": "Demo",
                "windows_executable": "Demo/Demo.exe",
                "source_entry": "main.py",
                "permissions": ["own_data_read"],
            }
        ),
        encoding="utf-8",
    )
    (payload / "Demo" / "Demo.exe").write_bytes(b"MZ-demo")
    (payload / "main.py").write_text("print('demo')\n", encoding="utf-8")
    package = build_component_package(
        payload=payload,
        component_id="demo",
        name="Demo",
        version="1.0.0",
        kind="module",
        output=tmp_path / "demo.lpmodule",
        requires_host=">=0.5.0",
        platforms=(),
        private_key_b64=private_b64,
    )
    catalog = write_catalog_ini(
        [
            ModuleRelease(
                module_id="demo",
                name="Demo",
                repository="example/Demo",
                available=True,
                version="1.0.0",
                asset_name="demo.lpmodule",
                asset_url="https://github.com/example/Demo/releases/download/v1.0.0/demo.lpmodule",
                asset_size=package.stat().st_size,
            )
        ],
        tmp_path / "catalog.ini",
    )

    def fake_download(url: str, destination: Path, expected_size: int, timeout: int = 120) -> Path:
        assert expected_size == package.stat().st_size
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(package, destination)
        return destination

    monkeypatch.setattr(bootstrap, "_download", fake_download)
    result = bootstrap.command_install(
        Namespace(catalog=catalog, selected="demo", app_root=app, cache=tmp_path / "cache")
    )
    assert result == 0
    assert (app / "modules" / "demo" / "module.json").is_file()
    assert (app / "modules" / "demo" / "Demo" / "Demo.exe").is_file()


def test_bootstrap_writes_readable_failure_result(tmp_path: Path) -> None:
    from lifeplanner_core.installer_bootstrap import _write_result

    target = tmp_path / "result.ini"
    _write_result(target, success=False, message="Download\nfehlgeschlagen")
    text = target.read_text(encoding="utf-8")
    assert "success = 0" in text
    assert "message = Download fehlgeschlagen" in text


def test_generated_installer_sources_use_separate_repository_variables() -> None:
    root = Path(__file__).resolve().parents[1]
    build = (root / "tools" / "build_release.py").read_text(encoding="utf-8")
    lock = json.loads((root / "dependencies" / "modules.lock.json").read_text(encoding="utf-8"))
    assert {item["repository_variable"] for item in lock["modules"]} == {
        "BUDGETMANAGER_REPOSITORY",
        "FPM_REPOSITORY",
    }
    assert '"BUDGETMANAGER_REPOSITORY"' in build
    assert '"FPM_REPOSITORY"' in build
    assert "github.repository_owner" not in build  # GitHub expression belongs only in the workflow.
