import json
from pathlib import Path

from lifeplanner_core.plugin_loader import discover_modules


def _write_manifest(root: Path, module_id: str, version: str, env_name: str) -> None:
    module = root / module_id
    module.mkdir(parents=True)
    (module / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (module / "module.json").write_text(
        json.dumps(
            {
                "schema": "lifeplanner.module.v1",
                "id": module_id,
                "name": module_id,
                "version": version,
                "source_entry": "main.py",
                "permissions": ["own_data_read", "own_data_write"],
                "environment": {env_name: "{module_data_dir}"},
            }
        ),
        encoding="utf-8",
    )


def test_discovers_installed_modules_without_vendored_sources(tmp_path):
    root = tmp_path / "modules"
    _write_manifest(root, "budgetmanager", "2.2.49", "BUDGETMANAGER_DATA_DIR")
    _write_manifest(root, "fpm", "0.3.04", "FPM_DATA_DIR")
    result = discover_modules(root)
    assert result.errors == ()
    assert [m.module_id for m in result.modules] == ["budgetmanager", "fpm"]
    assert all(m.source_entry == "main.py" for m in result.modules)
