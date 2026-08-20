# LifePlanner Modul-Installer – technischer Vertrag v1

## Ziel

Module sollen unabhängig vom LifePlanner-Core geliefert, installiert, aktualisiert und entfernt werden können. Ein Modul behält seine eigene Datenbank, Fachlogik, Tests und Releaseversion. Der Installer verändert keine Moduldatenbank direkt.


## Sicherheitsgrenze

Ein LifePlanner-Modul ist ausführbarer Code. In Version 0.4.0 läuft es als getrennter Prozess, aber mit den normalen Rechten des angemeldeten Benutzerkontos. Die Berechtigungen in `module.json` sind LifePlanner-Vertragsdeklarationen und noch keine Betriebssystem-Sandbox. Eine gültige Signatur bestätigt Herkunft und Unverändertheit, nicht die inhaltliche Harmlosigkeit. Daher dürfen nur Module vertrauenswürdiger Herausgeber installiert werden.

## Paketformat

Dateiendung: `.lpmodule`

Technisch ist das Paket ein ZIP mit folgender Struktur:

```text
component.json
component.json.sig        optional, für Releases empfohlen
payload/
├── module.json
└── ... Modulprogramm ...
```

### component.json

```json
{
  "schema": "lifeplanner.component.v1",
  "id": "fpm",
  "name": "FPM – Fountain Pen Manager",
  "version": "0.3.04",
  "kind": "module",
  "requires_host": ">=0.4.0",
  "description": "Füller- und Tintensammlung",
  "platforms": ["windows-x86_64"],
  "payload_sha256": "<64 hex>",
  "created_at": "2026-07-30T15:00:00+00:00"
}
```

`payload_sha256` ist der deterministisch berechnete SHA-256 des entpackten Dateibaums. Der Hash berücksichtigt relative Pfade, Dateigrößen und Dateiinhalte.

### Signatur

`component.json.sig` ist eine detached, Base64-kodierte Ed25519-Signatur über die exakten UTF-8-Bytes von `component.json`.

Weil `component.json` den `payload_sha256` enthält, bindet die Signatur den vollständigen Modulinhalt. Ein signiertes Paket ohne `payload_sha256` wird abgelehnt.

Der Installer verwendet denselben eingebetteten öffentlichen Vertrauensanker wie der zentrale Updater.

## Prüfablauf

1. Datei muss `.lpmodule` oder `.zip` sein.
2. Maximale Archivgröße: 1 GiB.
3. Sichere Extraktion ohne absolute Pfade, `..`, Symlinks oder ZipSlip.
4. Maximale entpackte Größe und maximale Anzahl Einträge.
5. Prüfung von `component.json` und Schema.
6. `kind` muss `module` sein.
7. Prüfung von ID und SemVer/PEP-440-Version.
8. Prüfung von `payload/module.json`.
9. ID und Version müssen in beiden Manifesten identisch sein.
10. Nur bekannte LifePlanner-Berechtigungen sind zulässig.
11. Prüfung von `payload_sha256`.
12. Falls vorhanden: Ed25519-Signaturprüfung.
13. Prüfung von `requires_host` gegen den installierten Core.
14. Prüfung der Plattformliste.
15. Prüfung, ob eine passende EXE oder `source_entry` vorhanden ist.
16. Erneute Payload-Hashprüfung unmittelbar vor dem Update-Plan.

## Unsignierte Pakete

Unsignierte Pakete sind für lokale Entwicklung erlaubt. Die Oberfläche zeigt eine eigenständige Warnung und verwendet standardmäßig **Abbrechen**. Der Benutzer muss die Herkunft ausdrücklich bestätigen.

Remote-Kataloge bleiben davon unberührt: Das zentrale Manifest muss im Produktivbetrieb signiert sein und bindet den SHA-256 des vollständigen Paketdownloads.

## Installation und Aktualisierung

Nach Bestätigung entsteht eine Operation mit:

```json
{
  "action": "replace",
  "kind": "module",
  "component_id": "fpm",
  "payload_dir": ".../updates/module-installer/inspection/.../payload",
  "tree_sha256": "...",
  "target_rel": "modules/fpm"
}
```

Der externe Helfer:

1. wartet auf den beendeten LifePlanner-Prozess,
2. sichert alle Profile,
3. sichert die bisherige Modulversion,
4. kopiert den neuen Payload auf dasselbe Dateisystem,
5. tauscht den Modulordner per Rename aus,
6. rollt bei Fehlern automatisch zurück,
7. startet LifePlanner neu.

Neuinstallation und Downgrade verwenden denselben transaktionalen Weg. Ein Downgrade benötigt eine zusätzliche Bestätigung, weil die erhaltenen Profildaten möglicherweise ein neueres Schema besitzen.

## Deinstallation

Eine Deinstallation erzeugt:

```json
{
  "action": "remove",
  "kind": "module",
  "component_id": "fpm",
  "target_rel": "modules/fpm"
}
```

Entfernt wird ausschließlich der Programmordner. Profildaten unter:

```text
profiles/<profil>/modules/<modul-id>/
```

bleiben erhalten. Vor dem Entfernen entstehen Profil- und Programmbackups. Auch die Deinstallation ist transaktional und rollbackfähig.

## Windows-Dateizuordnung

Der Inno-Setup-Installer registriert `.lpmodule` pro Benutzer unter `HKCU\Software\Classes`. Der Öffnen-Befehl lautet sinngemäß:

```text
LifePlanner.exe --install-module "%1"
```

LifePlanner öffnet daraufhin die Module-Seite und startet die normale Sicherheitsprüfung. Ein Doppelklick umgeht keine Bestätigung.

## Optionaler Windows-Setup

Der Hauptinstaller besitzt Inno-Setup-Komponenten:

- `core` – immer installiert
- `modules\budgetmanager` – optional
- `modules\fpm` – optional

Damit kann ein Benutzer zunächst nur den Core installieren und alle Module später über `.lpmodule` oder den signierten Online-Katalog ergänzen.

## Modulpaket bauen

```bash
python tools/build_module_package.py modules/mein-modul \
  --output release/mein-modul_1.0.0.lpmodule \
  --requires-host ">=0.4.0,<1.0" \
  --platform windows-x86_64
```

Releasepakete sollten immer mit `LIFEPLANNER_UPDATE_PRIVATE_KEY_B64` signiert werden.

## Git-Quelltrennung ab LifePlanner 0.4.1

Installierte `.lpmodule`-Pakete und im Windows-Installer enthaltene Modulbinärdateien sind Releaseartefakte. Der Quellcode von BudgetManager und FPM wird nicht mehr im LifePlanner-Repository geführt. Die Pakete werden aus getrennt ausgecheckten, versionierten Modulrepositories gebaut.
