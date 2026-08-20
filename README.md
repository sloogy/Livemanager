# LifePlanner 0.5.7 – Multi-Repository-Plattform mit GitHub-Modulinstaller

LifePlanner ist der modulare Desktop-Host. **BudgetManager und FPM bleiben vollständig eigenständige Git-Repositories** mit eigener Versionshistorie, eigenen Issues, Tests, Releases und Standalone-Builds.

Der LifePlanner-Core enthält keinen eingecheckten Quellcode dieser beiden Anwendungen. Er verwaltet nur:

- Modulverträge und Datenpfade
- Starten und Beenden getrennter Modulprozesse
- zentralen Updater und Modul-Installer
- Bridge, Event-Bus, Backups und Profile
- eine versionierte Abhängigkeits-Lockdatei
- die gemeinsame Windows-Release-Orchestrierung

## Offizielle Repositories

- LifePlanner Core: `https://github.com/sloogy/Livemanager`
- BudgetManager: `https://github.com/sloogy/Budgetmanager`
- FPM: `https://github.com/sloogy/FPM`

LifePlanner enthält keine Modulquellen. Im normalen Betrieb werden BudgetManager und FPM über die Seite **Module** direkt aus ihren freigegebenen GitHub-Releases bezogen. Der Source-/Portable-Betrieb verwendet standardmäßig einen einzigen lokalen Stamm: `data/`, `modules/` und `.venv/` liegen unter dem LifePlanner-Ordner. Es werden keine LifePlanner-Profildaten in `~/.local/share`, `~/.config` oder separaten Modul-Home-Verzeichnissen angelegt.


## Empfohlene Git-Struktur

```text
GitHub-Repositories:
├── LifePlanner/                 # dieses Repository, nur Core
├── Budgetmanager/               # https://github.com/sloogy/Budgetmanager
└── FPM/                         # https://github.com/sloogy/FPM
```

Lokal können die drei Repositories als Geschwisterordner liegen:

```text
Projekte/
├── LifePlanner/
├── BudgetManager/
└── FPM/
```

LifePlanner erwartet standardmäßig genau diese Geschwisterstruktur. Andere Pfade können über Umgebungsvariablen oder eine lokale, nicht eingecheckte JSON-Datei konfiguriert werden.

## Lokale Entwicklung

### Automatisch

Unter Windows:

```text
start-windows.bat
```

Unter Fedora/Linux:

```bash
./start-linux.sh
```

Die Starter rufen `tools/prepare_dev_modules.py --best-effort` auf. Das Werkzeug erstellt lediglich lokale Symlinks, Windows-Junctions oder notfalls ignorierte Entwicklungskopien unter `modules/`. Diese Einbindungen werden durch `.gitignore` niemals in das LifePlanner-Repository aufgenommen.

### Quellen explizit angeben

```bash
python tools/prepare_dev_modules.py \
  --budgetmanager-source ../Budgetmanager \
  --fpm-source ../FPM
```

Oder lokal `dependencies/module-sources.local.json` anlegen:

```json
{
  "budgetmanager": "D:/Projekte/BudgetManager",
  "fpm": "D:/Projekte/FPM"
}
```

Vorlage: `dependencies/module-sources.example.json`.

Alternativ:

```text
LIFEPLANNER_BUDGETMANAGER_SOURCE
LIFEPLANNER_FPM_SOURCE
```

## Versionierung

`dependencies/modules.lock.json` definiert die für einen LifePlanner-Release erwarteten Modulversionen und Buildpfade. Änderungen am BudgetManager oder FPM werden **im jeweiligen Modulrepository** committet und veröffentlicht. Erst danach wird im LifePlanner-Repository die gewünschte Modulversion beziehungsweise der Git-Ref aktualisiert.

Ein LifePlanner-Commit enthält daher keine Kopie eines Modulcommits. Die Releasepipeline erzeugt zusätzlich `module-source-provenance.json` mit den tatsächlich verwendeten Git-Commit-Hashes und Tags.

## GitHub-Actions-Konfiguration

Die Windows-Pipeline checkt drei Repositories getrennt aus. Standardmäßig erwartet sie:

```text
sloogy/Livemanager
sloogy/Budgetmanager
sloogy/FPM
```

Abweichende Namen werden als Repository-Variablen gesetzt:

```text
BUDGETMANAGER_REPOSITORY = sloogy/Budgetmanager
FPM_REPOSITORY           = sloogy/FPM
BUDGETMANAGER_REF        = v2.2.63
FPM_REF                  = v1.0.3
```

Für den zentralen Build aus privaten Modulrepositories wird ein Fine-grained PAT als Secret benötigt:

```text
LIFEPLANNER_MODULES_TOKEN
```

Der Token benötigt nur Leserechte auf BudgetManager und FPM. Der später an Endbenutzer verteilte Online-Installer sollte dagegen öffentliche Modul-Releases abfragen; er enthält keinen GitHub-Zugriffstoken.

Signierte spätere Releases verwenden:

```text
LIFEPLANNER_UPDATE_PRIVATE_KEY_B64
LIFEPLANNER_UPDATE_PUBLIC_KEY_B64
```

## Windows-Release

Ein Tag wie `lifeplanner-v0.5.7` baut aus den drei getrennten Checkouts:

- `LifePlanner_0.5.7_Windows_Portable.zip`
- `LifePlanner_Core_0.5.7_Windows_x86_64.zip`
- `budgetmanager_2.2.63_Windows_x86_64.lpmodule`
- `fpm_1.0.3_Windows_x86_64.lpmodule`
- `freizeitmanager_0.1.1_Windows_x86_64.lpmodule`
- `LifePlanner_0.5.7_Windows_Setup.exe`
- `lifeplanner-latest.json`
- `module-source-provenance.json`

Der bewusste erste Release wird mit `--allow-unsigned` gebaut. Dieser Schalter muss ausdrücklich gesetzt sein; ein fehlender Schlüssel allein aktiviert den Modus nicht. Die erzeugten `.lpmodule` enthalten weiterhin den vollständigen Payload-SHA-256 und alle Struktur-, Versions- und Plattformmetadaten, aber keine `component.json.sig`.

Der Windows-Setup wird mitveröffentlicht. Er ist in diesem Release ebenfalls unsigniert, weshalb Windows SmartScreen beim Start warnt. Sein automatischer GitHub-Bootstrap akzeptiert aus Sicherheitsgründen weiterhin nur signierte Remote-Pakete; die einzelnen unsignierten `.lpmodule` lassen sich stattdessen lokal mit manueller Vertrauensbestätigung installieren. Das Portable-Paket bleibt die Alternative ohne Installation.

Der Windows-Installer enthält **keine eingebetteten BudgetManager- oder FPM-Binärdateien mehr**. Beim Öffnen der Seite „Programme auswählen“ fragt er die konfigurierten GitHub-Repositories ab, zeigt verfügbare `.lpmodule`-Releases an und lädt nur die ausgewählten Programme herunter. Mindestens ein Programm ist Pflicht.

Der erste Release veröffentlicht die gebauten Modulpakete zusammen mit LifePlanner:

```text
LifePlanner Release → budgetmanager_<Version>_Windows_x86_64.lpmodule
LifePlanner Release → fpm_<Version>_Windows_x86_64.lpmodule
```

Diese ausdrücklich unsignierten Erst-Release-Pakete werden lokal über die LifePlanner-Modulverwaltung installiert. LifePlanner zeigt Herkunft, Hash, Berechtigungen und Kompatibilität an und verlangt eine manuelle Vertrauensbestätigung mit **Abbrechen** als Standard. Der automatische GitHub-Bootstrap und Remote-Updates bleiben signaturpflichtig.

## Validierung

Nur Core:

```bash
python tools/validate_release.py
```

Core plus separat konfigurierte Modulrepositories:

```bash
python tools/validate_release.py --with-modules
```

## Weitere Dokumentation

- `docs/GIT_MULTI_REPO_ARCHITECTURE.md`
- `docs/MODULE_INSTALLER.md`
- `docs/CENTRAL_UPDATER.md`
- `docs/GITHUB_INSTALLER_BOOTSTRAP.md`

### Fedora/Linux-Release

Der gemeinsame Workflow `.github/workflows/release.yml` baut ein portables `tar.gz`/ZIP mit
LifePlanner, BudgetManager und FPM sowie ausdrücklich unsignierte `linux-x86_64`-Komponenten
für den ersten Release. Lokale Linux-Modulpakete können nach manueller Vertrauensbestätigung
in der Modulverwaltung als `.lpmodule` installiert werden.
