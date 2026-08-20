import json
import os
from pathlib import Path

from lifeplanner_core.plugin_loader import discover_modules
from lifeplanner_core.process_manager import ModuleProcessManager


def _module(root: Path, module_id: str, variable: str) -> None:
    path = root / module_id
    path.mkdir(parents=True)
    (path / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (path / "module.json").write_text(
        json.dumps(
            {
                "schema": "lifeplanner.module.v1",
                "id": module_id,
                "name": module_id,
                "version": "1.0.0",
                "source_entry": "main.py",
                "permissions": ["own_data_read", "own_data_write", "bridge_read"],
                "environment": {
                    variable: "{module_data_dir}",
                    "LIFEPLANNER_BRIDGE_DIR": "{bridge_dir}",
                },
            }
        ),
        encoding="utf-8",
    )


def test_module_environment_is_profile_scoped(monkeypatch, tmp_path):
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "data"))
    root = tmp_path / "modules"
    _module(root, "budgetmanager", "BUDGETMANAGER_DATA_DIR")
    _module(root, "fpm", "FPM_DATA_DIR")
    modules = {m.module_id: m for m in discover_modules(root).modules}
    manager = ModuleProcessManager()
    budget_env = manager.build_environment(modules["budgetmanager"], "default", {})
    fpm_env = manager.build_environment(modules["fpm"], "default", {})
    assert budget_env["BUDGETMANAGER_DATA_DIR"].endswith(os.path.join("modules", "budgetmanager"))
    assert fpm_env["FPM_DATA_DIR"].endswith(os.path.join("modules", "fpm"))
    assert budget_env["LIFEPLANNER_BRIDGE_DIR"] == fpm_env["LIFEPLANNER_BRIDGE_DIR"]


def _binary_module(root: Path, module_id: str, runtime_dir: str) -> Path:
    path = root / module_id
    (path / runtime_dir).mkdir(parents=True)
    binary = path / runtime_dir / module_id
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(0o755)
    (path / "module.json").write_text(
        json.dumps(
            {
                "schema": "lifeplanner.module.v1",
                "id": module_id,
                "name": module_id,
                "version": "1.0.0",
                "source_entry": "main.py",
                "linux_executable": f"{runtime_dir}/{module_id}",
                "windows_executable": f"{runtime_dir}/{module_id}.exe",
                "permissions": ["own_data_read"],
            }
        ),
        encoding="utf-8",
    )
    return binary


def test_installed_binary_module_starts_without_source_entry(monkeypatch, tmp_path):
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "data"))
    root = tmp_path / "modules"
    binary = _binary_module(root, "budgetmanager", "BudgetManager")
    if os.name == "nt":
        binary = binary.with_suffix(".exe")
        binary.write_text("", encoding="utf-8")
    manifest = {m.module_id: m for m in discover_modules(root).modules}["budgetmanager"]
    assert not (manifest.module_dir / manifest.source_entry).exists()
    # Der Host läuft hier aus der Quelle, das Modul liegt als gebautes Paket vor.
    assert ModuleProcessManager().build_command(manifest) == [str(binary.resolve())]
