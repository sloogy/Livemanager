from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from lifeplanner_core.manifest import ModuleManifest
from lifeplanner_core.plugin_loader import PluginLoadResult
from lifeplanner_core.updater.manifest import platform_key
from lifeplanner_core.updater.service import UpdateService, UpdateServiceError


def _write_component(path: Path, *, component_id: str, version: str, kind: str, payload_files: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "component.json",
            json.dumps({"schema": "lifeplanner.component.v1", "id": component_id, "version": version, "kind": kind}),
        )
        for name, content in payload_files.items():
            archive.writestr("payload/" + name, content)


def test_local_end_to_end_check_and_stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LIFEPLANNER_ALLOW_LOCAL_UPDATES", "1")
    monkeypatch.setenv("LIFEPLANNER_ALLOW_UNSIGNED_UPDATES", "1")
    archive = tmp_path / "fpm.zip"
    module_json = {
        "schema": "lifeplanner.module.v1",
        "id": "fpm",
        "name": "FPM",
        "version": "0.3.05",
        "description": "test",
        "source_entry": "main.py",
        "permissions": ["own_data_read"],
    }
    _write_component(
        archive,
        component_id="fpm",
        version="0.3.05",
        kind="module",
        payload_files={"module.json": json.dumps(module_json), "main.py": "print('ok')"},
    )
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest = {
        "schema": "lifeplanner.update.v1",
        "channel": "stable",
        "generated_at": "2026-07-30T12:00:00+00:00",
        "components": {
            "fpm": {
                "id": "fpm",
                "name": "FPM",
                "version": "0.3.05",
                "kind": "module",
                "requires_host": ">=0.3.0",
                "assets": {
                    platform_key(): {
                        "url": str(archive),
                        "sha256": digest,
                        "size": archive.stat().st_size,
                        "type": "component-zip",
                    }
                },
            }
        },
    }
    manifest_path = tmp_path / "latest.json"
    manifest_path.write_text(json.dumps(manifest))
    current = ModuleManifest(
        module_id="fpm",
        name="FPM",
        version="0.3.04",
        description="",
        source_entry="main.py",
        module_dir=tmp_path,
    )
    service = UpdateService(PluginLoadResult((current,), ()))
    result = service.check(str(manifest_path))
    assert result.available[0].component_id == "fpm"
    staged = service.stage(result.manifest, ["fpm"])
    assert (staged[0].payload_dir / "module.json").is_file()


def test_module_requiring_unselected_core_is_blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "data"))
    from lifeplanner_core.updater.manifest import parse_manifest

    raw = {
        "schema": "lifeplanner.update.v1",
        "channel": "stable",
        "generated_at": "",
        "components": {
            "fpm": {
                "id": "fpm",
                "name": "FPM",
                "version": "1.0.0",
                "kind": "module",
                "requires_host": ">=9.0",
                "assets": {platform_key(): {"url": "https://example.org/x.zip", "sha256": "a" * 64, "size": 1, "type": "component-zip"}},
            }
        },
    }
    service = UpdateService(PluginLoadResult((), ()))
    with pytest.raises(UpdateServiceError):
        service.stage(parse_manifest(raw), ["fpm"])
