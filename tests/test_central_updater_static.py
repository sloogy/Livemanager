from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_packaging_contains_external_updater() -> None:
    build = (ROOT / "tools/build_release.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "LifePlannerUpdater.spec" in build
    assert "LifePlannerUpdater.exe" in build
    assert "lifeplanner-latest.json.sig" in workflow
    # Der Erst-Release ging bewusst unsigniert heraus. Seither prueft der
    # Updater fail-closed: ein Release ohne Signatur waere fuer jede
    # installierte Fassung tot.
    assert "--allow-unsigned" not in workflow
    assert "LIFEPLANNER_UPDATE_PRIVATE_KEY_B64" in workflow


def test_modules_receive_central_updater_contract_without_source_merge() -> None:
    manager = (ROOT / "lifeplanner_core/process_manager.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert 'LIFEPLANNER_CENTRAL_UPDATER", "1"' in manager
    assert "Checkout BudgetManager repository" in workflow
    assert "Checkout FPM repository" in workflow
    assert "module-sources/budgetmanager" in workflow
    assert "module-sources/fpm" in workflow
