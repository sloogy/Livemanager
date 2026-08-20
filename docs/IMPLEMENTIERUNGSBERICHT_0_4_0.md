# LifePlanner 0.4.0 – Implementierungsbericht Modul-Installer

## Ausgangslage

LifePlanner 0.3.0 konnte Core und bekannte Module über ein gemeinsames signiertes Manifest aktualisieren. Noch nicht vorhanden waren ein eigenständiger lokaler Modul-Installer, eine sichere Deinstallation, ein installierbares Moduldateiformat und eine Modulauswahl im Windows-Setup.

## Umgesetzte Architektur

### Modulverwaltung im Host

Der LifePlanner besitzt nun eine eigene Navigationsseite **Module**. Sie zeigt alle gültig erkannten Module mit Name, Version, ID, Prozessstatus und dem Vorhandensein von Profildaten.

Mögliche Aktionen:

- lokales `.lpmodule` oder Komponenten-ZIP prüfen und installieren
- vorhandenes Modul aktualisieren oder neu installieren
- bewusster Downgrade mit zusätzlicher Warnung
- Programm- und Profildatenordner öffnen
- Modulprogramm transaktional deinstallieren
- zum signierten Online-Katalog wechseln

### Paketformat `.lpmodule`

Das Format ist ZIP-kompatibel und verwendet den bestehenden Komponentenvertrag:

```text
component.json
component.json.sig
payload/module.json
payload/...
```

`component.json` enthält zusätzlich:

- `requires_host`
- Zielplattformen
- Beschreibung
- SHA-256 des vollständigen Payload-Dateibaums
- Erstellungszeitpunkt

Die optionale Ed25519-Signatur signiert die exakten Metadatenbytes. Da darin der Payload-Hash enthalten ist, ist der gesamte Paketinhalt kryptografisch gebunden.

### Lokale Sicherheitsprüfung

Vor einer Installation werden geprüft:

- Dateiendung und Größenlimit
- sichere ZIP-Pfade und Symlink-Verbot
- Komponenten- und Modulmanifest-Schema
- Modul-ID und Version
- bekannte LifePlanner-Berechtigungen
- Cross-Check zwischen `component.json` und `module.json`
- Plattformkompatibilität
- `requires_host` gegen LifePlanner 0.4.0
- passende gebaute Programmdatei bei Frozen/Windows
- Python-Startdatei im Source-Betrieb
- Payload-SHA-256
- optionale Ed25519-Signatur

Unsignierte lokale Pakete bleiben für die Entwicklung möglich, benötigen aber eine gesonderte Bestätigung mit Standardaktion **Abbrechen**.

### Sicherheitsgrenze transparent gemacht

Module laufen als getrennte Prozesse, aber in 0.4.0 noch mit den normalen Rechten des angemeldeten Benutzerkontos. Die Manifestberechtigungen sind Vertragsdeklarationen, keine Betriebssystem-Sandbox. Die Oberfläche weist deshalb ausdrücklich darauf hin, dass auch ein gültig signiertes Paket nur von einem vertrauenswürdigen Herausgeber installiert werden darf.

### Installation, Update und Deinstallation

Der bestehende externe Update-Helfer unterstützt nun zwei Aktionen:

- `replace` – Modul installieren, neu installieren, aktualisieren oder downgraden
- `remove` – Modulprogramm entfernen

Vor jeder Aktion werden alle Profile sowie die bisherige Programmkomponente gesichert. Die neue Version wird auf dasselbe Dateisystem kopiert und anschließend per Rename ausgetauscht. Bei einem Fehler werden bereits ausgeführte Änderungen rückwärts zurückgerollt.

Eine Deinstallation entfernt nur:

```text
<LifePlanner>/modules/<modul-id>/
```

Profildaten unter `profiles/<profil>/modules/<modul-id>` bleiben erhalten.

### Windows-Integration

Der Inno-Setup-Installer besitzt nun auswählbare Komponenten:

- LifePlanner Core – fest
- BudgetManager 2.2.49 – optional
- FPM 0.3.04 – optional

Installationsarten:

- vollständig
- nur Core
- benutzerdefiniert

Zusätzlich registriert der Installer `.lpmodule` pro Benutzer. Ein Doppelklick startet:

```text
LifePlanner.exe --install-module <paket>
```

Das Paket öffnet sich nicht ungeprüft, sondern durchläuft dieselbe Vorschau und Sicherheitsprüfung wie eine manuelle Auswahl.

### Releasepipeline

Der Windows-Release-Builder veröffentlicht Module nicht mehr nur als allgemeines Komponenten-ZIP, sondern als direkt installierbare Dateien:

```text
budgetmanager_2.2.49_Windows_x86_64.lpmodule
fpm_0.3.04_Windows_x86_64.lpmodule
```

Das zentrale signierte Manifest verweist auf dieselben Pakete. Damit dienen die Dateien sowohl dem zentralen Online-Installer als auch der manuellen lokalen Installation.

Für externe Modulentwickler wurde ergänzt:

```text
tools/build_module_package.py
```

## Kompatibilität

- BudgetManager bleibt auf 2.2.49.
- FPM bleibt auf 0.3.04.
- Beide Module bleiben standalone startfähig.
- Der zentrale Updater bleibt vollständig erhalten.
- Bestehende `lifeplanner.update-plan.v1`-Pläne ohne `action` werden weiterhin als `replace` behandelt.
- Windows und Fedora/Source verwenden denselben Paketprüfcode.

## Bewusst noch offen

- Es wurde in der Linux-Prüfumgebung keine echte Windows-EXE und kein Inno-Setup ausgeführt.
- Eine Betriebssystem-Sandbox für Drittmodule ist noch nicht umgesetzt.
- Automatische Löschung von Profildaten bei Deinstallation ist aus Sicherheitsgründen nicht Bestandteil von 0.4.0.
- Linux-Binärpakete müssen auf einem Linux-Release-Runner gebaut werden; Source-Module funktionieren im Source-Betrieb.
