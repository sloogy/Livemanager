# LifePlanner Modul-Host-Vertrag v1

## Prozessgrenze

Ein Fachmodul läuft in einem eigenen Betriebssystemprozess. Der LifePlanner-Core importiert keine UI-, Datenbank- oder Fachlogik des Moduls.

## Verbindliche Umgebungsvariablen

- `LIFEPLANNER_PROFILE_ID`: aktives Profil
- `LIFEPLANNER_BRIDGE_DIR`: gemeinsamer prüfbarer Austauschordner des Profils
- `LIFEPLANNER_HOST_VERSION`: Version des Hosts

Modulspezifisch:

- BudgetManager: `BUDGETMANAGER_DATA_DIR`
- FPM: `FPM_DATA_DIR`

## Datenhoheit

- Jedes Modul darf seine eigene Datenbank lesen und schreiben.
- Kein Modul darf eine fremde SQLite-Datenbank öffnen.
- Austausch erfolgt über versionierte JSON-/JSONL-Verträge.
- Schreibvorschläge müssen vor der Übernahme vom Zielmodul validiert und bei finanziellen oder gesundheitlichen Daten vom Benutzer bestätigt werden.

## Lebenszyklus-Events

Der Core schreibt lokale Events nach `events/events.jsonl`:

- `module.started`
- `module.stopped`

Schema: `lifeplanner.event.v1`.

## Abwärtskompatibilität

Alle Host-Overrides sind optional. Werden sie nicht gesetzt, starten BudgetManager und FPM weiterhin mit ihren bisherigen Standalone-Pfaden.
