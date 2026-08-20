import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_lock_matches_separate_module_builds():
    lock = json.loads((ROOT / "dependencies/modules.lock.json").read_text(encoding="utf-8"))
    modules = {item["id"]: item for item in lock["modules"]}
    assert modules["budgetmanager"]["runtime_directory"] == "BudgetManager"
    assert modules["budgetmanager"]["build_spec"] == "BudgetManager.spec"
    assert modules["fpm"]["runtime_directory"] == "FountainPenManager"
    assert modules["fpm"]["build_spec"] == "FPM.spec"


def test_windows_release_pipeline_stages_all_three_apps_from_separate_repos():
    build = (ROOT / "tools/build_release.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    installer = (ROOT / "installer/LifePlanner.iss").read_text(encoding="utf-8")

    assert "LifePlanner.spec" in build
    assert "resolve_module_sources" in build
    assert "windows-latest" in workflow
    assert "Checkout BudgetManager repository" in workflow
    assert "Checkout FPM repository" in workflow
    assert "v1.0.0" in workflow
    assert "--allow-unsigned" in workflow
    assert "First release must stay explicitly unsigned" in workflow
    assert "LifePlanner_0.5.3_Windows_Portable.zip" in workflow
    publish_line = next(line for line in workflow.splitlines() if "gh release upload" in line)
    assert "LifePlanner_0.5.3_Windows_Setup.exe" in publish_line
    assert "LifePlanner_0.5.3_Windows_Setup" in installer
    assert "PrivilegesRequired=lowest" in installer


def test_windows_installer_queries_separate_repositories_and_requires_one_module() -> None:
    installer = (ROOT / "installer/LifePlanner.iss").read_text(encoding="utf-8")
    build = (ROOT / "tools/build_release.py").read_text(encoding="utf-8")
    assert "LifePlannerInstallerBootstrap.exe" in installer
    assert "catalog --sources" in installer
    assert "install --catalog" in installer
    assert "CheckedModuleCount < 1" in installer
    assert "Mindestens ein Programm" in installer
    assert "Excludes: \"modules\\*" in installer
    assert "_write_installer_sources" in build
    assert "LifePlannerInstallerBootstrap.spec" in build


def test_module_manager_is_connected_to_shell() -> None:
    main_window = (ROOT / "lifeplanner_core/ui/main_window.py").read_text(encoding="utf-8")
    manager = (ROOT / "lifeplanner_core/ui/module_manager_page.py").read_text(encoding="utf-8")
    assert "ModuleManagerPage" in main_window
    assert "Modulpaket installieren" in manager
    assert "Modul deinstallieren" in manager
    assert "Profildaten" in manager
    assert "Unsigniertes Modulpaket" in manager
    assert "QMessageBox.StandardButton.Cancel" in manager
