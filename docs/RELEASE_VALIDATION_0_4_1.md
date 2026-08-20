# LifePlanner 0.4.1 – Release-Validierung

## Prüfumfang

- vollständige Core-Syntaxprüfung
- Core-Pytest-Suite
- Lockdatei-Schema und Versionsprüfung
- Nachweis, dass `modules/` keinen eingecheckten Modulquellbaum enthält
- lokale Quellenauflösung und Manifestprüfung
- separate BudgetManager-LifePlanner-Vertragstests
- separate FPM-LifePlanner-Vertragstests
- statische Prüfung der Multi-Repository-Windows-Pipeline
- Installer- und Updaterregressionen
- reales Git-Ignore-Verhalten mit verknüpften externen Repositories

## Erfolgreiche Prüfungen

- 32 LifePlanner-Core-, Installer-, Updater- und Multi-Repository-Tests
- 7 BudgetManager-LifePlanner-Import-/Hosttests im separaten BudgetManager-Quellbaum
- 10 FPM-Bridge-/Hosttests im separaten FPM-Quellbaum
- insgesamt 49 gezielt ausgeführte Pytest-Prüfungen
- vollständige Kompilierung der geänderten Core- und Vertragsdateien
- GitHub-Actions-YAML erfolgreich geparst
- lokale Symlink-Einbindung von BudgetManager und FPM erfolgreich
- `git status` blieb nach der Einbindung vollständig sauber
- LifePlanner erkannte und listete beide externen Module korrekt

## Git-Trennungsnachweis

Für den Test wurde ein frisches LifePlanner-Git-Repository initialisiert. Anschließend wurden BudgetManager und FPM über `tools/prepare_dev_modules.py` als externe Symlinks eingebunden. Weder `modules/budgetmanager` noch `modules/fpm` erschienen als Änderungen oder unversionierte Dateien in Git.

## Nicht in der Linux-Umgebung möglich

- echter PyInstaller-Windows-Build
- Inno-Setup-Kompilierung
- tatsächlicher GitHub-Checkout privater Repositories
- Start der erzeugten Windows-EXE

Diese Schritte sind im enthaltenen `windows-latest`-Workflow vorgesehen.
