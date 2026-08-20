from __future__ import annotations

import json
from pathlib import Path

import pytest

from lifeplanner_core.updater.apply_plan import apply_plan, tree_sha256


def _operation(component_id: str, kind: str, payload: Path, target_rel: str, version: str = "1.0.0") -> dict:
    return {
        "component_id": component_id,
        "name": component_id,
        "version": version,
        "kind": kind,
        "payload_dir": str(payload),
        "tree_sha256": tree_sha256(payload),
        "target_rel": target_rel,
    }


def test_apply_core_and_module_preserves_data(tmp_path: Path) -> None:
    app = tmp_path / "app"
    updates = tmp_path / "data" / "updates"
    app.mkdir(parents=True)
    updates.mkdir(parents=True)
    (app / "main.py").write_text("old core")
    (app / "portable.flag").write_text("portable")
    module = app / "modules" / "fpm"
    module.mkdir(parents=True)
    (module / "module.json").write_text("old module")

    core_payload = updates / "staging/core/payload"
    fpm_payload = updates / "staging/fpm/payload"
    core_payload.mkdir(parents=True)
    fpm_payload.mkdir(parents=True)
    (core_payload / "main.py").write_text("new core")
    (fpm_payload / "module.json").write_text("new module")

    plan = {
        "schema": "lifeplanner.update-plan.v1",
        "app_root": str(app),
        "update_root": str(updates),
        "wait_pids": [],
        "restart_command": [],
        "backup_profiles": False,
        "operations": [
            _operation("lifeplanner.core", "core", core_payload, ".", "0.3.0"),
            _operation("fpm", "module", fpm_payload, "modules/fpm", "0.3.5"),
        ],
    }
    plan_path = updates / "plan.json"
    plan_path.write_text(json.dumps(plan))
    result = apply_plan(plan_path)
    assert result["success"] is True
    assert (app / "main.py").read_text() == "new core"
    assert (module / "module.json").read_text() == "new module"
    assert (app / "portable.flag").read_text() == "portable"
    assert (updates / "last_result.json").is_file()


def test_apply_rolls_back_previous_component_on_later_failure(tmp_path: Path) -> None:
    app = tmp_path / "app"
    updates = tmp_path / "data" / "updates"
    old = app / "modules" / "fpm"
    old.mkdir(parents=True)
    updates.mkdir(parents=True)
    (old / "value.txt").write_text("old")
    first = updates / "staging/fpm/payload"
    second = updates / "staging/bad/payload"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (first / "value.txt").write_text("new")
    (second / "main.py").write_text("new core")
    bad_operation = _operation("lifeplanner.core", "core", second, ".", "0.3.0")
    bad_operation["tree_sha256"] = "0" * 64
    plan = {
        "schema": "lifeplanner.update-plan.v1",
        "app_root": str(app),
        "update_root": str(updates),
        "wait_pids": [],
        "restart_command": [],
        "backup_profiles": False,
        "operations": [
            _operation("fpm", "module", first, "modules/fpm", "0.3.5"),
            bad_operation,
        ],
    }
    plan_path = updates / "plan.json"
    plan_path.write_text(json.dumps(plan))
    with pytest.raises(Exception):
        apply_plan(plan_path)
    assert (old / "value.txt").read_text() == "old"
    result = json.loads((updates / "last_result.json").read_text())
    assert result["success"] is False


def test_remove_module_preserves_profile_data_and_creates_rollback(tmp_path: Path) -> None:
    app = tmp_path / "app"
    updates = tmp_path / "data" / "updates"
    module = app / "modules" / "demo"
    profile_data = tmp_path / "data" / "profiles" / "default" / "modules" / "demo"
    module.mkdir(parents=True)
    profile_data.mkdir(parents=True)
    updates.mkdir(parents=True)
    (module / "module.json").write_text("installed")
    (profile_data / "database.sqlite").write_text("user data")
    plan = {
        "schema": "lifeplanner.update-plan.v1",
        "app_root": str(app),
        "update_root": str(updates),
        "wait_pids": [],
        "restart_command": [],
        "backup_profiles": True,
        "operations": [
            {
                "action": "remove",
                "component_id": "demo",
                "name": "Demo",
                "version": "1.0.0",
                "kind": "module",
                "target_rel": "modules/demo",
            }
        ],
    }
    plan_path = updates / "remove-plan.json"
    plan_path.write_text(json.dumps(plan))
    result = apply_plan(plan_path)
    assert result["success"] is True
    assert not module.exists()
    assert (profile_data / "database.sqlite").read_text() == "user data"
    assert result["components"][0]["action"] == "remove"
    assert result["program_backups"]
    assert result["profile_backups"]
