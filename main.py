from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lifeplanner_core import APP_NAME, APP_VERSION
from lifeplanner_core.diagnostics import build_diagnostics
from lifeplanner_core.plugin_loader import discover_modules
from lifeplanner_core.settings import SettingsStore


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LifePlanner modularer Desktop-Host")
    parser.add_argument("--diagnostics", action="store_true", help="Diagnose als JSON ausgeben")
    parser.add_argument("--diagnostics-file", type=Path, help="Diagnose als JSON in eine Datei schreiben")
    parser.add_argument("--list-modules", action="store_true", help="Gefundene Module ausgeben")
    parser.add_argument("--install-module", type=Path, help="Ein .lpmodule-Paket öffnen und prüfen")
    parser.add_argument("module_package", nargs="?", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.diagnostics or args.diagnostics_file is not None:
        payload = json.dumps(build_diagnostics(), ensure_ascii=False, indent=2)
        if args.diagnostics_file is not None:
            target = args.diagnostics_file.expanduser().resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(payload + "\n", encoding="utf-8")
        if args.diagnostics:
            print(payload)
        return 0
    result = discover_modules()
    if args.list_modules:
        for module in result.modules:
            print(f"{module.module_id}\t{module.version}\t{module.name}")
        for error in result.errors:
            print(f"ERROR\t{error}", file=sys.stderr)
        return 0 if result.modules else 1
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        from lifeplanner_core.ui.main_window import MainWindow
    except ModuleNotFoundError as exc:
        print(
            "PySide6 fehlt. Installiere zuerst die Abhängigkeiten mit "
            "'python -m pip install -r requirements.txt'.\n"
            f"Technisches Detail: {exc}",
            file=sys.stderr,
        )
        return 2
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("LifePlanner")

    # Nur eine Instanz je Datenordner. Zwei Hosts wuerden dieselben Module
    # starten und in denselben Brueckenordner schreiben - die Module haetten
    # dann zwei Eltern, und beim Update wuerde einer dem anderen die Dateien
    # unter den Fuessen wegziehen.
    from lifeplanner_core.paths import data_root
    from lifeplanner_core.single_instance import SingleInstanceGuard

    guard = SingleInstanceGuard(
        data_root() / "lifeplanner.instance.lock", app_id="LifePlanner"
    )
    frei, grund = guard.acquire()
    if not frei:
        QMessageBox.information(None, APP_NAME, grund)
        return 0
    app.aboutToQuit.connect(guard.release)

    settings = SettingsStore()
    package = args.install_module or args.module_package
    if package is not None and package.suffix.lower() not in {".lpmodule", ".zip"}:
        print(f"Kein unterstütztes Modulpaket: {package}", file=sys.stderr)
        return 3
    window = MainWindow(result, settings, module_package=package)
    window.show()
    if result.errors:
        QMessageBox.warning(window, "Einige Module wurden übersprungen", "\n".join(result.errors))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
