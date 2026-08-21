import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_multi_repo_lock_pins_integrated_module_versions():
    lock = json.loads((ROOT / "dependencies/modules.lock.json").read_text(encoding="utf-8"))
    modules = {item["id"]: item for item in lock["modules"]}
    # Die Lockdatei ist die Quelle - ein Test, der ihre Versionen nachschreibt,
    # muss bei jedem Release angefasst werden. Geprueft wird stattdessen, dass
    # jedes Modul festgenagelt ist und Version und Ref zusammenpassen.
    for modul in modules.values():
        assert re.fullmatch(r"\d+\.\d+\.\d+", modul["version"]), modul["id"]
        assert modul["default_ref"] == f"v{modul['version']}", modul["id"]
    assert modules["budgetmanager"]["build_spec"] == "BudgetManager.spec"
    assert modules["fpm"]["build_spec"] == "FPM.spec"


def test_external_contracts_are_part_of_release_validation():
    validation = (ROOT / "tools/validate_release.py").read_text(encoding="utf-8")
    assert "test_lifeplanner_import_inbox.py" in validation
    assert "test_budgetmanager_bridge_service.py" in validation
    assert "--with-modules" in validation
