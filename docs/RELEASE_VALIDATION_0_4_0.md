# LifePlanner 0.4.0 – Release-Validierung

## Geprüfter Umfang

- LifePlanner Core 0.4.0
- BudgetManager 2.2.49
- FPM 0.3.04
- lokaler `.lpmodule`-Installer
- zentraler Online-Modulkatalog
- Moduldeinstallation
- externer Update-/Installationshelfer
- Windows-Setup-Komponentenauswahl
- `.lpmodule`-Dateizuordnung
- Modulpaket-Buildwerkzeug

## Erfolgreiche Prüfungen

### Core und Installer

- vollständige Python-Kompilierung von Core, UI, Helfer und Buildwerkzeugen
- Modul-Discovery mit BudgetManager und FPM
- CLI-Smoke-Test des Modulpaket-Builders
- 30 LifePlanner-Core-, Update-, Paket- und Installer-Tests

Enthaltene Spezialfälle:

- gültiges signiertes Paket
- manipuliertes signiertes Payload
- unsigniertes Entwicklungspaket
- Host-Versionsanforderung
- Frozen-Host lehnt Source-only-Paket ab
- Installations-Staging-Hash
- Pfad- und ZIP-Sicherheitsprüfungen
- Modulinstallation und Ersatz bestehender Version
- Moduldeinstallation bei erhaltenen Profildaten
- Programm- und Profilrollbackarchive
- Rollback einer vorherigen Komponente bei späterem Fehler
- optionaler Windows-Installer für BudgetManager/FPM
- Verbindung der Module-Seite mit dem LifePlanner-Shell

### Bestehende Integrationen

- 7 BudgetManager-LifePlanner-Import-/Hosttests
- 10 FPM-Bridge-, Collection-Health- und Hosttests

### Zusätzliche Regressionen

- 24 BudgetManager-Updater-, Restore-, Integritäts- und Multiuser-Regressionstests
- 57 FPM-Updater-, Enterprise-, Host- und Windows-Packaging-Regressionstests

Gesamtzahl der gezielt ausgeführten Pytest-Prüfungen: **128**.

## Echter Paket-Smoke-Test

`tools/build_module_package.py` wurde gegen das vorhandene FPM-Modul ausgeführt. Das erzeugte `.lpmodule` ließ sich anschließend mit dem neuen Installer-Service entpacken und als kompatibles Source-Modul erkennen. Das Testpaket war bewusst unsigniert und wurde korrekt entsprechend markiert.

## Sicherheitsbefund

Bestanden:

- Ed25519-Signaturprüfung
- kryptografisch gebundener Payload-Dateibaum
- Ablehnung manipulierter Payloads
- SHA-256-Prüfung unmittelbar vor Planerstellung und Anwendung
- ZIP-Traversal- und Symlink-Schutz
- sichere relative Modulziele
- Core kann nicht über den Deinstallationsweg entfernt werden
- Profildaten werden nicht mit dem Modulprogramm gelöscht
- Deinstallation und Installation sind rollbackfähig
- unsignierte Pakete besitzen kein stilles Installationsverfahren

## Nicht in dieser Umgebung ausführbar

- realer PyInstaller-Build auf Windows
- Kompilierung des Inno-Setup-Skripts durch `ISCC.exe`
- interaktiver Qt-GUI-Smoke-Test, da PySide6 in der Prüfungsumgebung nicht installiert ist
- Start der erzeugten Windows-EXE und Prüfung der Registry-Dateizuordnung auf einem echten Windows-System

Die GitHub-Actions-Pipeline verwendet `windows-latest` und enthält die dafür vorgesehenen Build-, Test-, PyInstaller- und Inno-Setup-Schritte.
