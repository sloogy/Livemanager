# LifePlanner 0.3.0 – Release-Validierung

## Ergebnis

**Source-/Integrationsstatus: PASS**

Der zentrale Updater ist in der Source-Version implementiert und die plattformunabhängige Kernlogik wurde ausgeführt. Ein echter Windows-PyInstaller-/Inno-Setup-Lauf ist weiterhin nur auf einem Windows-Runner möglich und wird durch die enthaltene GitHub-Actions-Pipeline abgedeckt.

## Ausgeführte Prüfungen

### LifePlanner-Core

- vollständige Python-Compileall-Prüfung
- Modul-Discovery über `main.py --list-modules`
- 23 Coretests erfolgreich
- Manifest-Schema und SemVer
- Ed25519-Signaturprüfung
- Plattformasset-Auswahl
- sichere ZIP-Extraktion und ZipSlip-Abwehr
- lokaler End-to-End-Check und Staging
- Host-Abhängigkeitsblockade
- Core-/Modul-Dateitausch
- Schutz von `portable.flag` und Datenpfaden
- automatischer Rollback bei späterem Operationsfehler
- statische Windows-Paketierungsprüfung
- zentraler Host-Vertrag für BudgetManager und FPM

### Bestehende Module

- 7 BudgetManager-LifePlanner-Integrationsprüfungen erfolgreich
- 10 FPM-Bridge-/Hostprüfungen erfolgreich
- 16 zusätzliche BudgetManager-Updater-, Restore-, Prozess- und GUI-Vertragsprüfungen erfolgreich
- 30 FPM-Standalone-Updater-, Enterprise- und Hostprüfungen erfolgreich

### Externer Helfer

- echter CLI-End-to-End-Test mit gestageter Modulkomponente
- Dateitausch erfolgreich
- Neustart im Test deaktiviert
- Importprüfung: keine neuen Qt-, Requests- oder Kryptographieimporte im Helferpfad

### Releasepipeline

- GitHub-Actions-YAML erfolgreich geparst
- externer `LifePlannerUpdater` im Build enthalten
- Komponentenarchive für Core und dynamisch alle gebauten Module
- signiertes `lifeplanner-latest.json`
- Veröffentlichung der Updateassets am GitHub-Tag
- Portable- und Inno-Setup-Paketnamen konsistent auf 0.3.0

## Nicht ausführbar in dieser Umgebung

### Echter Qt-UI-Smoke-Test

PySide6 ist in der verwendeten Prüfungsumgebung nicht installiert. Deshalb konnte kein interaktiver/offscreen `QApplication`-Start durchgeführt werden. Sämtliche neuen und geänderten UI-Dateien wurden jedoch erfolgreich kompiliert und die UI-Verkabelung wird zusätzlich statisch geprüft.

### Windows-Binärtest

Nicht lokal ausgeführt:

- PyInstaller-Build von `LifePlanner.exe`
- PyInstaller-Build von `LifePlannerUpdater.exe`
- Austausch real gesperrter Windows-EXE-/DLL-Dateien
- Inno-Setup-Kompilierung
- GitHub-Release-Publishing

Diese Schritte müssen auf `windows-latest` mit gesetzten Update-Schlüssel-Secrets laufen.

## Sicherheitsbewertung

Remote-Updates sind fail-closed:

- kein Public Key → Abbruch
- keine Signatur → Abbruch
- ungültige Signatur → Abbruch
- kein HTTPS → Abbruch
- falsche Größe oder SHA-256 → Abbruch
- unsicheres ZIP → Abbruch
- falsche Komponenten-ID/-Version → Abbruch
- inkompatibler Host → Abbruch
- fehlerhafter Dateitausch → automatischer Rollback

Lokale oder unsignierte Tests erfordern zwei ausdrücklich gesetzte Entwicklungsvariablen und sind standardmäßig deaktiviert.

## Releaseentscheidung

Die Source-Version ist für den nächsten Windows-CI-Build freigegeben. Ein öffentliches Release sollte erst erfolgen, wenn der Windows-Workflow mit echten Ed25519-Secrets erfolgreich durchgelaufen ist und die erzeugte Portable-Version sowie der Installer auf einem Windows-System gestartet und einmal über den zentralen Updater aktualisiert wurden.
