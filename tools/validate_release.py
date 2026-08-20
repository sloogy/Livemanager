from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.module_sources import ModuleSourceError, resolve_module_sources


def run(command: list[str], *, cwd: Path = ROOT) -> int:
    print("+", " ".join(command))
    return subprocess.run(command, cwd=cwd).returncode


def core_checks() -> list[tuple[Path, list[str]]]:
    return [
        (
            ROOT,
            [
                sys.executable,
                "-m",
                "compileall",
                "-q",
                "lifeplanner_core",
                "main.py",
                "update_helper.py",
                "installer_bootstrap.py",
                "tools/build_release.py",
                "tools/build_linux_release.py",
                "tools/build_module_package.py",
                "tools/module_sources.py",
                "tools/prepare_dev_modules.py",
                "lifeplanner_core/installer_catalog.py",
                "lifeplanner_core/installer_bootstrap.py",
            ],
        ),
        (ROOT, [sys.executable, "tools/build_module_package.py", "--help"]),
        (ROOT, [sys.executable, "tools/build_release.py", "--help"]),
        (ROOT, [sys.executable, "tools/build_linux_release.py", "--help"]),
        (ROOT, [sys.executable, "tools/prepare_dev_modules.py", "--help"]),
        (ROOT, [sys.executable, "installer_bootstrap.py", "--help"]),
        (ROOT, [sys.executable, "-m", "pytest", "-q", "tests"]),
    ]


def module_checks() -> list[tuple[Path, list[str]]]:
    sources = resolve_module_sources(require_all=True)
    budget = sources["budgetmanager"].path
    fpm = sources["fpm"].path
    return [
        (
            budget,
            [
                sys.executable,
                "-m",
                "compileall",
                "-q",
                "model/lifeplanner_import_service.py",
                "views/lifeplanner_import_dialog.py",
                "views/main_window.py",
            ],
        ),
        (
            budget,
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/test_lifeplanner_import_inbox.py",
                "tests/test_lifeplanner_host_contract.py",
                "tests/test_lifeplanner_module_release.py",
            ],
        ),
        (
            fpm,
            [
                sys.executable,
                "-m",
                "compileall",
                "-q",
                "logic/budget_export_service.py",
                "ui/settings_widget.py",
            ],
        ),
        (
            fpm,
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/test_budgetmanager_bridge_service.py",
                "tests/test_collection_health_service.py",
                "tests/test_lifeplanner_host_contract.py",
                "tests/test_lifeplanner_module_release.py",
            ],
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validiert LifePlanner Core und optional die getrennten Modul-Repositories.")
    parser.add_argument(
        "--with-modules",
        action="store_true",
        help="Prüft zusätzlich die extern konfigurierten BudgetManager- und FPM-Repositories.",
    )
    args = parser.parse_args()

    module_dirs = [path for path in (ROOT / "modules").iterdir() if path.is_dir()]
    if module_dirs:
        print("FEHLER: Modulquellcode wurde in das LifePlanner-Repository eingebettet:")
        for path in module_dirs:
            print(" -", path)
        return 2

    checks = core_checks()
    if args.with_modules:
        try:
            checks.extend(module_checks())
        except ModuleSourceError as exc:
            print(f"FEHLER: {exc}")
            return 2

    for cwd, command in checks:
        result = run(command, cwd=cwd)
        if result:
            return result
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
