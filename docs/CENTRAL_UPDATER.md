# Zentraler LifePlanner-Updater – technischer Vertrag

## Ziel

Der LifePlanner-Core ist die einzige Update-Oberfläche, sobald ein Modul durch den Host gestartet wurde. BudgetManager und FPM bleiben standalone updatefähig, erhalten vom Host jedoch `LIFEPLANNER_CENTRAL_UPDATER=1` und verweisen dann auf den zentralen Update-Bereich.

## Manifest

Schema: `lifeplanner.update.v1`

```json
{
  "schema": "lifeplanner.update.v1",
  "channel": "stable",
  "generated_at": "2026-07-30T12:00:00+00:00",
  "components": {
    "lifeplanner.core": {
      "id": "lifeplanner.core",
      "name": "LifePlanner Core",
      "version": "0.4.0",
      "kind": "core",
      "requires_host": "",
      "assets": {
        "windows-x86_64": {
          "url": "https://…/LifePlanner_Core_0.4.0_Windows_x86_64.zip",
          "sha256": "<64 hex>",
          "size": 123456,
          "type": "component-zip"
        }
      }
    }
  }
}
```

Erlaubte Komponententypen:

- `core`
- `module`

Erlaubter Asset-Typ:

- `component-zip`

Die Auswahl erfolgt zuerst über den genauen Schlüssel wie `windows-x86_64`, danach über den Familien-Fallback `windows` oder `linux`.

## Signatur

Neben `lifeplanner-latest.json` liegt die detached Ed25519-Signatur:

```text
lifeplanner-latest.json.sig
```

Die Signatur ist Base64-kodiert und wird gegen den beim Build eingebetteten öffentlichen Schlüssel geprüft. Fehlender Schlüssel, fehlende Signatur oder eine ungültige Signatur führen bei Remote-Updates immer zum Abbruch.

Der private Schlüssel existiert ausschließlich als geschütztes Release-Secret.

Der bewusste erste Release besitzt noch keinen Vertrauensanker und wird deshalb mit `--allow-unsigned` gebaut. Seine Manifeste und Komponenten dienen als manuell herunterladbare Releaseartefakte; der automatische Remote-Updater akzeptiert sie absichtlich nicht. Unsignierte `.lpmodule` werden ausschließlich über die lokale Modulverwaltung mit manueller Vertrauensbestätigung installiert.

## Komponentenarchiv

Jedes ZIP besitzt exakt diese logische Struktur:

```text
component.json
component.json.sig   # bei signierten Releasepaketen; fehlt im ausdrücklichen Erst-Release-Modus
payload/
└── …
```

`component.json`:

```json
{
  "schema": "lifeplanner.component.v1",
  "id": "fpm",
  "name": "FPM – Fountain Pen Manager",
  "version": "0.3.05",
  "kind": "module",
  "requires_host": ">=0.4.0",
  "platforms": ["windows-x86_64"],
  "payload_sha256": "<64 hex>"
}
```

Für Module muss `payload/module.json` vorhanden sein. ID und Version müssen mit Manifest und Komponentenmetadaten übereinstimmen. Releasepakete werden als `.lpmodule` veröffentlicht. Die optionale `component.json.sig` bindet über `payload_sha256` den vollständigen Modulinhalt und erlaubt auch eine sichere lokale Installation außerhalb des Online-Katalogs.

Ein Core-Asset darf folgende Pfade nicht enthalten:

- `modules`
- `data`
- `profiles`
- `updates`
- `.venv`
- `portable.flag`
- `installation.json`

Dadurch kann ein Core-Update weder Modulstände noch Nutzerdaten überschreiben.

## Sicherheitsprüfungen

1. Manifest nur über HTTPS; lokale Dateien nur bei explizitem Entwicklungsflag.
2. Ed25519-Signatur des Manifests.
3. Manifest-Schema und SemVer-Prüfung.
4. Plattformasset und Host-Abhängigkeit.
5. Exakte Downloadgröße.
6. SHA-256 des Downloads.
7. ZipSlip-, absoluter-Pfad- und Symlink-Schutz.
8. Eintrags- und Größenlimits beim Entpacken.
9. Komponentenmetadaten und Modulmanifest.
10. SHA-256 des entpackten Dateibaums vor und unmittelbar beim Anwenden.
11. Zielpfade müssen innerhalb des App-Roots liegen.

## Windows-Ablauf

1. LifePlanner lädt und staged die Komponenten im beschreibbaren Datenordner.
2. Der Host beendet BudgetManager, FPM und alle weiteren gestarteten Module.
3. Ein Update-Plan wird atomar geschrieben.
4. `LifePlannerUpdater.exe` wird in den Datenordner kopiert und dort gestartet.
5. LifePlanner beendet sich.
6. Der Helfer wartet auf das Ende des Host-Prozesses.
7. Alle Profile werden als ZIP gesichert.
8. Die bisherigen Programmkomponenten werden separat gesichert.
9. Neue Dateien werden auf dasselbe Dateisystem wie das Ziel kopiert.
10. Alt und Neu werden per Rename getauscht.
11. Bei einem Fehler werden alle zuvor geänderten Komponenten rückwärts wiederhergestellt.
12. LifePlanner startet neu und liest `updates/last_result.json`.

Der Helfer läuft außerhalb des Installationsordners. Dadurch kann er auch `LifePlannerUpdater.exe`, `LifePlanner.exe` und `_internal` ersetzen, ohne sich selbst zu sperren.

## Update-Plan

Schema: `lifeplanner.update-plan.v1`

Der Plan enthält ausschließlich absolute, vor dem Anwenden erneut validierte Pfade, die zu aktualisierenden Komponenten, Dateibaum-Hashes, die zu wartenden Prozess-IDs und den Neustartbefehl.

## Kompatibilität

Module können über `requires_host` einen PEP-440-Specifier angeben, zum Beispiel:

```json
"requires_host": ">=0.4.0,<0.5"
```

Wird das benötigte Core-Update nicht ausgewählt, verweigert der Updater die Vorbereitung. Das verhindert die Installation eines Moduls gegen einen inkompatiblen Host.

## Neue Module

Der Release-Builder liest nach dem Windows-Build alle Ordner unter `dist/LifePlanner/modules`, die ein gültiges `module.json` enthalten. Für jedes gefundene Modul wird automatisch ein Komponentenarchiv und Manifest-Eintrag erstellt.

Damit benötigt ein neues Modul im zentralen Updater keine fest codierte UI-Erweiterung. Erforderlich bleiben:

- gültiges `module.json`
- Einbindung des Modul-Builds in das Gesamtbundle oder Bau eines `.lpmodule`-Pakets
- passende Versionsnummer und `requires_host`
- Tests für den Host-Vertrag

Ein nicht installiertes Modul im signierten Manifest wird in der Oberfläche als **Zur Installation verfügbar** angezeigt.

## Fehler- und Rollbackstatus

`updates/last_result.json` enthält:

- Erfolg oder Fehler
- aktualisierte IDs und Versionen
- Profil-Backups
- Programm-Rollbackarchive
- Fehlermeldung und Rollbackfehler

Nach einem Fehler wird die bisherige Version neu gestartet und zeigt den zurückgerollten Zustand im Update-Bereich an.
