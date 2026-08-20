import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_multi_repo_lock_pins_integrated_module_versions():
    lock = json.loads((ROOT / "dependencies/modules.lock.json").read_text(encoding="utf-8"))
    modules = {item["id"]: item for item in lock["modules"]}
    assert modules["budgetmanager"]["version"] == "2.2.63"
    assert modules["fpm"]["version"] == "1.0.2"
    assert modules["budgetmanager"]["build_spec"] == "BudgetManager.spec"
    assert modules["fpm"]["build_spec"] == "FPM.spec"


def test_external_contracts_are_part_of_release_validation():
    validation = (ROOT / "tools/validate_release.py").read_text(encoding="utf-8")
    assert "test_lifeplanner_import_inbox.py" in validation
    assert "test_budgetmanager_bridge_service.py" in validation
    assert "--with-modules" in validation
