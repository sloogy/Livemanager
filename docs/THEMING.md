# Zentrale Designprofile

LifePlanner steuert die Optik von Host und Modulen an einer Stelle: **Darstellung**
in der Seitenleiste. Ein Häkchen hält alle Programme auf demselben Profil, sonst
lässt sich je Modul ein eigenes wählen.

## Profile

Die Profile liegen als JSON unter `lifeplanner_core/themes/` und verwenden
dasselbe Schema wie die Profile des BudgetManagers (`views/profiles/`). Sie sind
namens- und wertgleich, damit „überall dasselbe Theme" wirklich dieselben Farben
bedeutet und nicht nur denselben Namen.

Pflichtfelder je Profil:

```json
{
  "name": "Standard - Hell",
  "modus": "hell",
  "schriftgroesse": 10,
  "hintergrund_app": "#ffffff",
  "text": "#111111",
  "akzent": "#2f80ed"
}
```

`modus` ist `hell` oder `dunkel`, `schriftgroesse` liegt zwischen 6 und 30, alle
Werte mit führendem `#` müssen sechsstellige Hexfarben sein. Ein Profil, das
diese Prüfung nicht besteht, wird übersprungen und auf der Seite Darstellung als
Fehler angezeigt — es ersetzt niemals stillschweigend die Optik.

Der Sondername `system` bedeutet: heller oder dunkler Standard je nach
Systempalette.

## Austauschformat

Es gibt genau ein Themeformat im Ökosystem: `lifeplanner.theme.v1`. Der
FreizeitManager hatte es bereits festgelegt; Host und alle übrigen Module
verwenden es unverändert weiter, statt ein zweites daneben zu stellen.

```json
{
  "schema": "lifeplanner.theme.v1",
  "name": "Mitternacht - Violett",
  "modus": "dunkel",
  "schriftgroesse": 10,
  "farben": { "hintergrund_app": "#0d0d12", "akzent": "#7150f0" },
  "gesetzt_von": "lifeplanner",
  "modul_version": "0.5.4",
  "profil": "default",
  "geaendert_am": "2026-08-20T10:00:00+00:00"
}
```

`farben` enthält alle Hexwerte des Profils, damit ein Modul ein Theme auch dann
darstellen kann, wenn es das Profil selbst nicht mitliefert.

## Weitergabe an Module

Module sind eigenständige Prozesse. Der Host greift nicht in sie hinein, sondern
legt das Profil ab und nennt es beim Start. Es gibt zwei Ablageorte:

| Ort | Inhalt | Wann geschrieben |
| --- | --- | --- |
| `$LIFEPLANNER_BRIDGE_DIR/shared_theme.json` | gemeinsames Theme aller Module | nur wenn „für alle Module" aktiv ist |
| `$LIFEPLANNER_THEME_FILE` (`<Profil>/theme/<modul-id>.json`) | das für **dieses** Modul gültige Profil | bei jeder Änderung |

Der gemeinsame Eintrag wird bewusst nur bei gesetztem Häkchen geschrieben: ein
ungefragt veröffentlichtes Theme würde die abweichende Wahl einzelner Module
überstimmen. Wer je Modul unterschiedliche Designs einstellt, wird über
`LIFEPLANNER_THEME_FILE` bedient.

Zusätzlich steht der Profilname in `LIFEPLANNER_THEME`.

Ein Modul bindet das so an:

```python
import json, os

def lifeplanner_theme():
    """Vom Host vorgegebenes Theme oder None im Standalone-Betrieb."""
    path = os.environ.get("LIFEPLANNER_THEME_FILE", "").strip()
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("schema") != "lifeplanner.theme.v1":
        return None
    return data if str(data.get("name", "")).strip() else None
```

Ist die Variable nicht gesetzt, bleibt das Modul bei seiner eigenen Einstellung.
Der Standalone-Betrieb ändert sich dadurch nicht.

## Stand der Module

| Modul | Status |
| --- | --- |
| FreizeitManager | liest `shared_theme.json` bereits; keine Änderung nötig |
| BudgetManager | liest das Hostprofil beim Start, lokale Wahl bleibt für Standalone erhalten |
| FPM | liest das Hostprofil beim Start |

## Wirksamkeit

Der Host wechselt das Design sofort. Ein bereits laufender Modulprozess behält
seines bis zum nächsten Start; die Seite Darstellung weist darauf hin und nennt
die betroffenen Module.
