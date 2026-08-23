# LifePlanner Modul-Host-Vertrag v2

## Prozessgrenze

Ein Fachmodul läuft in einem eigenen Betriebssystemprozess. Der LifePlanner-Core importiert keine UI-, Datenbank- oder Fachlogik des Moduls.

Die in `module.json` deklarierten `permissions` sind ein **Vertrauens- und Informationsvertrag**, keine Betriebssystem-Sandbox. Ein Modulprozess läuft mit den Rechten des angemeldeten Benutzers. Die LifePlanner-Oberfläche darf diese Angaben deshalb nicht als technisch erzwungene Isolation darstellen.

## Manifest-Versionen

- `lifeplanner.module.v1` bleibt lesbar, damit bereits installierte Module weiter funktionieren.
- `lifeplanner.module.v2` ist für neue Releases vorgesehen und benötigt zusätzlich `requires_host`.
- `requires_host` wird beim Installieren **und vor jedem Modulstart** gegen die aktuelle LifePlanner-Version geprüft. Ein späteres Host-Update kann damit ein inzwischen inkompatibles Modul nicht still weiter starten.
- **Die Obergrenze gehört an das Manifest-Schema, nicht an die Nebenversion des Hosts.** Alle Module deklarierten einmal `<0.6`; der Sprung des Hosts von 0.5.15 auf 0.6.0 hat damit die gesamte Suite entkoppelt, obwohl sich am Vertrag nichts geändert hatte — installierte Module starteten nicht mehr, neue liessen sich nicht installieren. Eine echte Vertragsänderung heisst v3 (oder Host 1.0), und erst dann wandert die Grenze.

Beispiel:

```json
{
  "schema": "lifeplanner.module.v2",
  "id": "freizeitmanager",
  "version": "0.1.10",
  "requires_host": ">=0.5.15,<1.0"
}
```

## Verbindliche Umgebungsvariablen

- `LIFEPLANNER_PROFILE_ID`: aktives Profil
- `LIFEPLANNER_BRIDGE_DIR`: gemeinsamer prüfbarer Austauschordner des Profils
- `LIFEPLANNER_HOST_VERSION`: Version des Hosts
- `LIFEPLANNER_MODULE_DATA_DIR`: Datenordner des gestarteten Moduls
- `LIFEPLANNER_CENTRAL_UPDATER=1`: der Host verwaltet Updates zentral

Modulspezifisch:

- BudgetManager: `BUDGETMANAGER_DATA_DIR`
- FPM: `FPM_DATA_DIR`
- FreizeitManager: `FREIZEITMANAGER_DATA_DIR`

## Datenhoheit

- Jedes Modul liest und schreibt ausschließlich seine eigene Fachdatenbank.
- Kein Modul öffnet die SQLite-Datenbank eines anderen Moduls.
- Austausch erfolgt über versionierte JSON-/JSONL-Verträge im Bridge-Ordner.
- Schreibvorschläge werden vom Zielmodul validiert; finanzielle oder andere besonders schützenswerte Änderungen werden nicht still übernommen.
- Der Host konsumiert nur die für ihn deklarierten Ergebnisse und Zusammenfassungen, nicht interne Notizen oder Rohdaten.

## Deklarative Bridge-Verträge

`lifeplanner.module.v2` kann seine Datei-Schnittstellen unter `bridge.publishes` und `bridge.subscribes` deklarieren. Der Host muss dadurch keine Fachdateinamen neuer Module hart codieren.

Beispiel:

```json
{
  "bridge": {
    "publishes": [
      {
        "name": "FreizeitManager Fokus → LifePlanner",
        "file": "freizeitmanager_to_lifeplanner.jsonl",
        "schemas": ["freizeitmanager.focus.v1"]
      }
    ],
    "subscribes": []
  }
}
```

Dateipfade müssen relativ und ohne `..` sein. Das Manifest beschreibt nur erlaubte Verträge; die Fachanwendung bleibt für Validierung und Datenhoheit verantwortlich.

## Events

Core und Module schreiben lokale Events nach `events/events.jsonl`. Das verbindliche Schema `lifeplanner.event.v1` besitzt exakt diese Felder:

- `event_id`: eindeutige UUID
- `schema`: `lifeplanner.event.v1`
- `event_type`: Ereignisname, z. B. `module.started` oder `freizeit.interaction.logged`
- `source`: Quelle des Ereignisses
- `occurred_at`: UTC-Zeitpunkt
- `profile_id`: aktives Profil
- `payload`: versionierbarer Objekt-Payload

Mehrere Prozesse verwenden denselben Event-Lock. Ein Writer schreibt die vollständige Zeile, flush't und `fsync`'t sie vor dem Freigeben des Locks. Ein Leser setzt seinen Offset nicht hinter eine unvollständige letzte Zeile.

## Abwärtskompatibilität

Alle Host-Overrides bleiben optional. Ohne Host-Variablen laufen BudgetManager, FPM und FreizeitManager weiterhin standalone mit ihren eigenen Datenpfaden. Alte `lifeplanner.module.v1`-Manifeste bleiben lesbar; v2-Funktionen werden erst mit einem v2-Manifest aktiviert.
