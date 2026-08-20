# LifePlanner 0.4.1 – Implementierungsbericht

## Umgesetzte Änderung

BudgetManager und FPM wurden vollständig aus dem LifePlanner-Quellbaum entfernt. Das LifePlanner-Repository enthält nur noch Corecode, Modulverträge, Installer-/Updaterlogik und Buildorchestrierung.

## Neue Komponenten

- `dependencies/modules.lock.json`
- `dependencies/module-sources.example.json`
- `tools/module_sources.py`
- `tools/prepare_dev_modules.py`
- Multi-Repository-GitHub-Workflow
- Build-Provenienzdatei für Modulcommits
- getrennte Core- und Modulvalidierung

## Lokales Verhalten

LifePlanner sucht Modulquellen nicht als eingecheckte Unterordner. Die Entwicklungseinbindung wird beim Start bestmöglich vorbereitet. Fehlen externe Repositories, startet der Core ohne Module; installierte `.lpmodule`-Pakete funktionieren weiterhin.

## Releaseverhalten

Die Windows-Pipeline checkt drei Repositories aus. BudgetManager und FPM werden in ihren eigenen Arbeitsverzeichnissen gebaut. Der LifePlanner-Installer übernimmt ausschließlich deren gebaute Binärverzeichnisse und `module.json`.

## Sicherheits- und Reproduzierbarkeitsverbesserung

- falsche Modul-ID wird abgelehnt
- falsche Modulversion wird abgelehnt
- CI-Builds mit uncommitteten Änderungen werden abgelehnt
- exakte Git-Commits und Refs werden dokumentiert
- LifePlanner-Git kann keine versehentliche Kopie der Modulquellen aufnehmen
