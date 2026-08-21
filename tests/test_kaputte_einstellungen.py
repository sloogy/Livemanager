"""Eine unlesbare Einstellungsdatei wird gerettet, nicht ueberschrieben.

Bisher galten bei kaputtem JSON stillschweigend die Standardwerte - und beim
naechsten Speichern war die Datei endgueltig weg, samt allem was darin stand.
Oft ist nur ein Zeichen falsch und sie liesse sich von Hand retten; dafuer
muss sie aber noch da sein.

Alle betroffenen Programme der Suite fuehren diesen Test unter demselben Namen.
"""

from __future__ import annotations

import json

import pytest

from lifeplanner_core.settings import SettingsStore


@pytest.mark.parametrize(
    "inhalt,beschreibung",
    [
        ("{nicht json", "abgeschnittenes JSON"),
        ("", "leere Datei"),
        ("[1, 2, 3]", "Liste statt Objekt"),
        ("42", "nackte Zahl"),
        ('{"theme": "dracula"', "fehlende Klammer"),
    ],
)
def test_eine_kaputte_datei_wird_beiseitegelegt(tmp_path, inhalt, beschreibung):
    pfad = tmp_path / "settings.json"
    pfad.write_text(inhalt, encoding="utf-8")

    store = SettingsStore(pfad)

    # Das Programm laeuft weiter, mit Standardwerten.
    assert store.theme == "system", beschreibung
    # Und der alte Inhalt ist noch da.
    gerettet = list(tmp_path.glob("settings.json.kaputt-*"))
    assert len(gerettet) == 1, beschreibung
    assert gerettet[0].read_text(encoding="utf-8") == inhalt


def test_eine_gueltige_datei_bleibt_unangetastet(tmp_path):
    pfad = tmp_path / "settings.json"
    pfad.write_text(json.dumps({"theme": "Dracula - Dunkel"}), encoding="utf-8")

    store = SettingsStore(pfad)

    assert store.theme == "Dracula - Dunkel"
    assert not list(tmp_path.glob("settings.json.kaputt-*"))


def test_eine_fehlende_datei_ist_kein_fehler(tmp_path):
    """Der erste Start - da gibt es noch nichts zu retten."""
    store = SettingsStore(tmp_path / "settings.json")
    assert store.theme == "system"
    assert not list(tmp_path.glob("*.kaputt-*"))


def test_die_geretteten_dateien_ueberschreiben_sich_nicht(tmp_path):
    """Zweimal hintereinander kaputt: beide Staende bleiben erhalten."""
    import time

    pfad = tmp_path / "settings.json"
    for inhalt in ("{erster", "{zweiter"):
        pfad.write_text(inhalt, encoding="utf-8")
        SettingsStore(pfad)
        time.sleep(1.05)  # der Zeitstempel loest auf Sekunden auf
    gerettet = sorted(p.read_text(encoding="utf-8") for p in tmp_path.glob("*.kaputt-*"))
    assert gerettet == ["{erster", "{zweiter"]
