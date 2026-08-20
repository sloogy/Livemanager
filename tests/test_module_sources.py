import json
from pathlib import Path

import pytest

from tools.module_sources import ModuleSourceError, load_lock, validate_module_source


def _make_source(tmp_path: Path, *, module_id: str, version: str, spec_name: str) -> Path:
    root = tmp_path / module_id
    root.mkdir()
    (root / spec_name).write_text("# spec\n", encoding="utf-8")
    (root / "module.json").write_text(
        json.dumps(
            {
                "schema": "lifeplanner.module.v1",
                "id": module_id,
                "name": module_id,
                "version": version,
                "source_entry": "main.py",
            }
        ),
        encoding="utf-8",
    )
    return root


def test_lock_has_two_independent_sources():
    specs = {spec.module_id: spec for spec in load_lock()}
    assert set(specs) == {"budgetmanager", "fpm"}
    assert specs["budgetmanager"].source_environment != specs["fpm"].source_environment
    assert specs["budgetmanager"].default_repository == "sloogy/Budgetmanager"
    assert specs["fpm"].default_repository == "sloogy/FPM"
    assert specs["budgetmanager"].version == "2.2.62"
    assert specs["fpm"].version == "1.0.0"


def test_source_validation_checks_id_and_version(tmp_path):
    spec = {item.module_id: item for item in load_lock()}["budgetmanager"]
    source = _make_source(tmp_path, module_id="budgetmanager", version="2.2.62", spec_name="BudgetManager.spec")
    resolved = validate_module_source(spec, source)
    assert resolved.path == source.resolve()

    (source / "module.json").write_text(
        json.dumps({"id": "budgetmanager", "version": "9.9.9"}), encoding="utf-8"
    )
    with pytest.raises(ModuleSourceError, match="passt nicht zur Lockdatei"):
        validate_module_source(spec, source)
