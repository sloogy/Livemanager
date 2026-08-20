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
