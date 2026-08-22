import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from tools.module_sources import (
    ModuleSourceError,
    github_env_lines,
    load_lock,
    validate_module_source,
)


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
    # Keine festen Versionen mehr: Die Lockdatei ist die Quelle, und ein Test,
    # der sie nachschreibt, muss bei jedem Release angefasst werden - dabei
    # blieben die Versionen zuletzt fuenf Staende lang stehen. Geprueft wird,
    # dass jedes Modul eine SemVer-Version und ein dazu passendes Ref traegt.
    for spec in specs.values():
        assert re.fullmatch(r"\d+\.\d+\.\d+", spec.version), spec.version
        assert spec.default_ref == f"v{spec.version}", spec.module_id


def test_source_validation_checks_id_and_version(tmp_path):
    spec = {item.module_id: item for item in load_lock()}["budgetmanager"]
    source = _make_source(tmp_path, module_id="budgetmanager", version=spec.version, spec_name="BudgetManager.spec")
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
        # Repository und Ref stehen nur in der Lockdatei; der Workflow verweist
        # darauf. Ein neues Modul faellt trotzdem auf, weil sein Verweis fehlt.
        assert f"env.LOCK_{spec.repository_variable}" in workflow, (
            f"{spec.module_id}: Repository fehlt im Workflow"
        )
        assert f"env.LOCK_{spec.ref_variable}" in workflow, (
            f"{spec.module_id}: Ref fehlt im Workflow"
        )
        assert f"--{spec.module_id}-source" in workflow, f"{spec.module_id}: Buildaufruf fehlt"

    for name in ("tools/build_release.py", "tools/build_linux_release.py"):
        text = (root / name).read_text(encoding="utf-8")
        for spec in specs:
            assert spec.module_id not in text, f"{name} verdrahtet {spec.module_id} fest"


def test_workflow_carries_no_version_literal():
    """Die Workflow-Datei traegt keine Version - weder Host noch Modul.

    Sie stand frueher in ``sync_version.py`` unter den versionstragenden
    Dateien. Zwei Dinge gingen daran kaputt: Der Release-Token darf
    Workflow-Dateien nur mit dem Recht "workflows" schreiben, und die Ersetzung
    lief ueber die Versionsreihe des Hosts - ein LifePlanner 1.1.x haette das
    FPM-Ref ``v1.1.0`` mitgezogen.
    """
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/release.yml").read_text(encoding="utf-8")
    treffer = re.findall(r"(?<![\w.])v?\d+\.\d+\.\d+(?![\w.])", workflow)
    assert not treffer, f"Version steht wieder fest im Workflow: {treffer}"

    sync = (root / "tools/sync_version.py").read_text(encoding="utf-8")
    assert ".github/workflows/release.yml" not in sync.split("VERSION_BEARING")[1].split(")")[0]


def test_github_env_lines_reject_line_breaks():
    """Ein Zeilenumbruch im Lockwert wuerde eine zweite Variable definieren."""
    spec = load_lock()[0]
    kaputt = replace(spec, default_ref="v1.0.0\nGITHUB_TOKEN=geklaut")
    with pytest.raises(ModuleSourceError, match="Zeilenumbruch"):
        github_env_lines((kaputt,))

    zeilen = github_env_lines()
    assert all(zeile.count("=") >= 1 and "\n" not in zeile for zeile in zeilen)
    assert f"LOCK_{spec.ref_variable}={spec.default_ref}" in zeilen
