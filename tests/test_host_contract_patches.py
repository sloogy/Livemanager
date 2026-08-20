import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_module_sources_are_not_vendored_into_lifeplanner_git():
    modules = ROOT / "modules"
    forbidden = [path for path in modules.iterdir() if path.is_dir()]
    assert forbidden == []
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/modules/*" in gitignore
    assert "!/modules/README.md" in gitignore


def test_lock_declares_separate_budgetmanager_and_fpm_sources():
    lock = json.loads((ROOT / "dependencies/modules.lock.json").read_text(encoding="utf-8"))
    modules = {item["id"]: item for item in lock["modules"]}
    assert modules["budgetmanager"]["source_environment"] == "LIFEPLANNER_BUDGETMANAGER_SOURCE"
    assert modules["fpm"]["source_environment"] == "LIFEPLANNER_FPM_SOURCE"
    assert modules["budgetmanager"]["default_repository"] == "sloogy/Budgetmanager"
    assert modules["fpm"]["default_repository"] == "sloogy/FPM"
