# LifePlanner 0.1.0 - Implementierungsbericht

## Ausgangslage

Das Architekturhandbuch fordert Offline First, Privacy First, Windows und Fedora, eigenständige Module, getrennte Datenbanken, Service-Contracts und einen Event-Bus. BudgetManager und FPM sind bereits umfangreiche PySide6-Anwendungen mit eigener Initialisierung und eigenem Releaseprozess.

## Architekturentscheidung ADR-001

BudgetManager und FPM werden im ersten stabilen Schritt nicht als Widgets in denselben Python-Prozess importiert. Stattdessen startet der LifePlanner-Core jedes Modul als eigenen Prozess. Gründe:

1. Eine `QApplication` darf pro Prozess nur einmal existieren.
2. Beide Projekte verwenden gleichnamige Top-Level-Module wie `main.py` und `app_info.py`.
3. Datenbank-, Settings-, Updater- und Single-Instance-Logik bleiben dadurch unverändert beherrschbar.
4. Abstürze eines Fachmoduls reißen den LifePlanner-Core nicht mit.
5. Die eigenständige Startbarkeit und getrennte Releasefähigkeit bleiben erhalten.

## Host-Verträge

- BudgetManager erhält `BUDGETMANAGER_DATA_DIR`.
- FPM erhält `FPM_DATA_DIR`.
- Beide erhalten `LIFEPLANNER_BRIDGE_DIR`, `LIFEPLANNER_PROFILE_ID` und `LIFEPLANNER_HOST_VERSION`.
- Die Modulmanifeste deklarieren Einstiegspunkt, Version und Berechtigungen.

## Windows-Konzept

Der Release besteht aus drei PyInstaller-Onedir-Anwendungen:

- `LifePlanner.exe`
- `modules/budgetmanager/BudgetManager/BudgetManager.exe`
- `modules/fpm/FountainPenManager/FountainPenManager.exe`

Der Core startet die beiden Modulprogramme ohne Shell und übergibt ausschließlich definierte Umgebungsvariablen. Eine GitHub Action baut Portable ZIP und Inno-Setup-Installer auf einem echten Windows Runner.

## Sicherheitsgrenzen

- Keine direkten SQL-Zugriffe zwischen Modulen.
- Eigene Datenordner je Modul und Profil.
- JSONL-Bridge ist nachvollziehbar und manuell prüfbar.
- Ollama ist standardmäßig deaktiviert und auf lokale Endpunkte beschränkt.
- Backup wird atomar erzeugt, als ZIP getestet und mit SHA-256 begleitet.

## Bekannte Lücke

FPM besitzt bereits einen Exportvertrag `budgetmanager.import.v1`. BudgetManager 2.2.49 enthält noch keinen passenden nativen Review-Importer. Die LifePlanner-Oberfläche zeigt daher aktuell Status und Dateipfad, nimmt aber noch keine Buchungen automatisch an. Automatisches ungeprüftes Schreiben wäre ausdrücklich gegen das Architekturprinzip.

## Nächste Entwicklungsstufe 0.2.0

1. BudgetManager Review-Inbox für `budgetmanager.import.v1` mit Duplikatschutz.
2. Bestätigungs- und Ablehnungsstatus im Bridge-Contract.
3. Gemeinsames Dashboard nur über Read-Model-Snapshots.
4. Profile in der Oberfläche erstellen und wechseln.
5. Signierte Modulmanifeste und Update-Koordination.
