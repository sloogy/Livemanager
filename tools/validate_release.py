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
    # check=False: der Aufrufer sammelt die Rueckgabewerte und entscheidet
    # selbst, welcher Fehlschlag den Lauf beendet.
    return subprocess.run(command, cwd=cwd, check=False).returncode


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
                "tools/generate_icons.py",
                "lifeplanner_core/installer_catalog.py",
                "lifeplanner_core/installer_bootstrap.py",
            ],
        ),
        (ROOT, [sys.executable, "tools/build_module_package.py", "--help"]),
        (ROOT, [sys.executable, "tools/build_release.py", "--help"]),
        (ROOT, [sys.executable, "tools/build_linux_release.py", "--help"]),
        (ROOT, [sys.executable, "tools/prepare_dev_modules.py", "--help"]),
        (ROOT, [sys.executable, "installer_bootstrap.py", "--help"]),
        # Ohne --select: die Auswahl steht in ruff.toml, begruendet und
        # gemeinsam mit dem lokalen Lauf. Vorher pruefte das Gate nur die
        # Syntax-Klasse, waehrend lokal die globale Konfiguration des
        # Entwicklerrechners galt - beide sagten damit Verschiedenes.
        (ROOT, [sys.executable, "-m", "ruff", "check", "."]),
        # Typpruefung seit Loop 57. Der Host startet Prozesse, installiert
        # Module und prueft Signaturen - dort faellt ein Typfehler nicht
        # als falsche Anzeige auf, sondern als abgebrochener Update-Lauf.
        # Lokal bitte ueber tools/gepinnte_werkzeuge.py aufrufen: ohne
        # PySide6 in der Umgebung sind alle Qt-Typen Any, und der Lauf waere
        # gruen und wertlos.
        (ROOT, [sys.executable, "-m", "mypy", "lifeplanner_core"]),
        (ROOT, [sys.executable, "tools/exception_audit.py"]),
        (ROOT, [sys.executable, "-m", "pytest", "-q", "tests"]),
    ]


def module_checks() -> list[tuple[Path, list[str]]]:
    """Per-module LifePlanner contract checks, driven by the lock file.

    Entries are curated per module because each repository names its own
    contract tests. Missing files are skipped so that a module can join
    before it ships every check.
    """
    compile_targets = {
        "budgetmanager": [
            "model/lifeplanner_import_service.py",
            "views/lifeplanner_import_dialog.py",
            "views/main_window.py",
        ],
        "fpm": [
            "logic/budget_export_service.py",
            "ui/settings_widget.py",
        ],
        "freizeitmanager": [
            "tools/build_lifeplanner_module.py",
        ],
    }
    test_targets = {
        "budgetmanager": [
            "tests/test_lifeplanner_import_inbox.py",
            "tests/test_lifeplanner_host_contract.py",
            "tests/test_lifeplanner_module_release.py",
        ],
        "fpm": [
            "tests/test_budgetmanager_bridge_service.py",
            "tests/test_collection_health_service.py",
            "tests/test_lifeplanner_host_contract.py",
            "tests/test_lifeplanner_module_release.py",
        ],
        "freizeitmanager": [
            "tests/test_packaging.py",
        ],
    }

    sources = resolve_module_sources(require_all=True)
    checks: list[tuple[Path, list[str]]] = []
    for module_id, resolved in sources.items():
        root = resolved.path
        present = [name for name in compile_targets.get(module_id, []) if (root / name).is_file()]
        if present:
            checks.append((root, [sys.executable, "-m", "compileall", "-q", *present]))
        tests = [name for name in test_targets.get(module_id, []) if (root / name).is_file()]
        if tests:
            checks.append((root, [sys.executable, "-m", "pytest", "-q", *tests]))
    return checks
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
