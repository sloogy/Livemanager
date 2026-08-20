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


def test_lock_has_independent_sources_per_module():
    specs = {spec.module_id: spec for spec in load_lock()}
    assert set(specs) == {"budgetmanager", "fpm", "freizeitmanager"}
    # Every module must be resolvable and overridable on its own.
    for field in ("source_environment", "repository_variable", "ref_variable", "default_sibling"):
        values = [getattr(spec, field) for spec in specs.values()]
        assert all(values), f"{field} fehlt bei mindestens einem Modul"
        assert len(set(values)) == len(values), f"{field} ist nicht eindeutig"
    assert specs["budgetmanager"].default_repository == "sloogy/Budgetmanager"
    assert specs["fpm"].default_repository == "sloogy/FPM"
    assert specs["freizeitmanager"].default_repository == "sloogy/Kontaktmanager"
    assert specs["budgetmanager"].version == "2.2.63"
    assert specs["fpm"].version == "1.0.3"
    assert specs["freizeitmanager"].version == "0.1.1"


def test_source_validation_checks_id_and_version(tmp_path):
    spec = {item.module_id: item for item in load_lock()}["budgetmanager"]
    source = _make_source(tmp_path, module_id="budgetmanager", version="2.2.63", spec_name="BudgetManager.spec")
    resolved = validate_module_source(spec, source)
    assert resolved.path == source.resolve()

    (source / "module.json").write_text(
        json.dumps({"id": "budgetmanager", "version": "9.9.9"}), encoding="utf-8"
    )
    with pytest.raises(ModuleSourceError, match="passt nicht zur Lockdatei"):
        validate_module_source(spec, source)


def test_build_tools_and_workflow_cover_every_locked_module():
    """Ein neues Modul in der Lockdatei muss ueberall mitgebaut werden.

    Die Buildskripte hatten budgetmanager/fpm frueher fest verdrahtet; ein
    drittes Modul waere lautlos aus Release und Installer gefallen.
    """
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/release.yml").read_text(encoding="utf-8")
    specs = load_lock()
    assert len(specs) >= 3

    for spec in specs:
        assert spec.source_environment in workflow, f"{spec.module_id}: Quelle fehlt im Workflow"
        assert spec.default_repository in workflow, f"{spec.module_id}: Repository fehlt im Workflow"
        assert f"--{spec.module_id}-source" in workflow, f"{spec.module_id}: Buildaufruf fehlt"

    for name in ("tools/build_release.py", "tools/build_linux_release.py"):
        text = (root / name).read_text(encoding="utf-8")
        for spec in specs:
            assert spec.module_id not in text, f"{name} verdrahtet {spec.module_id} fest"
