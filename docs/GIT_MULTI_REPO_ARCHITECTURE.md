# Git-Multi-Repository-Architektur

## Ziel

LifePlanner, BudgetManager und FPM werden als drei eigenständige Produkte entwickelt. Der LifePlanner-Core darf keine fremde Fachlogik besitzen und keine vollständigen Quellbäume der Module einchecken.

## Verantwortlichkeiten

### LifePlanner-Repository

- Core-Oberfläche
- Modul- und Prozessverwaltung
- Modulinstaller
- zentraler Updater
- Profile, Bridge, Event-Bus und Backups
- gemeinsame Release-Orchestrierung
- Kompatibilitäts- und Versions-Lockdatei

### BudgetManager-Repository

- komplette Budgetfachlogik
- eigene Datenbankmigrationen
- Import-Inbox für LifePlanner-Verträge
- eigener Standalone-Updater
- eigene Tests, Releases und Dokumentation

### FPM-Repository

- komplette Füller-Sammlungslogik
- eigene Datenbankmigrationen
- Budgetexport-Bridge
- eigener Standalone-Updater
- eigene Tests, Releases und Dokumentation

## Keine Git-Submodule als Zwang

Die Architektur verwendet bewusst keine fest eingecheckten Git-Submodule. Dadurch bleiben normale Clone-, Branch- und Pull-Request-Abläufe einfach. Die Buildpipeline checkt die Modulrepositories separat aus und pinnt sie über Repository-Variablen und Refs.

Git-Submodule können lokal verwendet werden, sind aber nicht Bestandteil des verbindlichen LifePlanner-Repositoryzustands.

## Abhängigkeits-Lock

`dependencies/modules.lock.json` enthält:

- Modul-ID
- erwartete Modulversion
- Standardrepository und Git-Ref
- Pfad zum PyInstaller-Spec
- erwartete Buildausgabe
- Runtime-Verzeichnis

Der Build bricht ab, wenn `module.json` nicht zur gelockten ID oder Version passt.

## Entwicklungsmodus

`tools/prepare_dev_modules.py` erzeugt unter `modules/<id>` nur lokale Einbindungen. Dieser Ordner ist in `.gitignore` ausgeschlossen. Die bevorzugte Reihenfolge zur Quellenauflösung ist:

1. expliziter CLI-Pfad
2. modulspezifische Umgebungsvariable
3. `dependencies/module-sources.local.json`
4. Standard-Geschwisterordner

## Releaseablauf

1. BudgetManager und FPM separat testen und taggen.
2. Im LifePlanner-Repository Lockdatei beziehungsweise Workflow-Refs aktualisieren.
3. LifePlanner-Tag erstellen.
4. GitHub Actions checkt alle drei Repositories getrennt aus.
5. Jede Modulquelle wird gegen `module.json` und Lockdatei geprüft.
6. Module werden in ihren eigenen Arbeitsverzeichnissen gebaut.
7. Nur die fertigen Binärartefakte werden in Installer, Portable-Paket und `.lpmodule` übernommen.
8. `module-source-provenance.json` protokolliert die exakten Git-Commits.

## Updateverhalten

Der zentrale Updater installiert Binärpakete. Er verändert niemals die Git-Repositories oder Entwicklerquellen. Standalone-Updater der Module bleiben außerhalb des LifePlanner-Hosts funktionsfähig.

## Branch- und Releaseempfehlung

- `main`: releasefähiger Stand
- Featurebranches je Repository
- Semantische Tags je Produkt
- LifePlanner taggt nur den Core, beispielsweise `lifeplanner-v0.4.1`
- BudgetManager taggt unabhängig, beispielsweise `v2.2.49`
- FPM taggt unabhängig, beispielsweise `v0.3.04`

Ein Modulupdate erfordert nicht automatisch einen neuen LifePlanner-Core. Der zentrale Online-Katalog kann neue `.lpmodule`-Versionen unabhängig bereitstellen, sofern `requires_host` erfüllt ist.
