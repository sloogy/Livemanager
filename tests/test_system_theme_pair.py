"""Was "Systemvorgabe" bedeutet - und was eine neue Installation mitbringt.

Warum es diesen Test gibt: Die Auflösung von "system" haengt an drei Stellen
zusammen - der Erkennung hell/dunkel, dem gespeicherten Paar und dem Katalog.
Faellt eine davon aus, startet LifePlanner einfach im Standardprofil, ohne dass
jemand einen Fehler sieht. Und ein Update darf bestehenden Installationen ihr
Erscheinungsbild nicht umstellen.
"""
from __future__ import annotations

import json

from lifeplanner_core.settings import INITIAL_DARK_THEME, INITIAL_LIGHT_THEME, SettingsStore
from lifeplanner_core.theme import SYSTEM_THEME, ThemeCatalog


def test_neue_installation_bekommt_das_auslieferungspaar(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    assert store.system_theme_pair == (INITIAL_LIGHT_THEME, INITIAL_DARK_THEME)
    # Und es steht auch auf der Platte, nicht nur im Speicher.
    saved = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert saved["system_theme_light"] == INITIAL_LIGHT_THEME


def test_bestehende_installation_behaelt_das_standardpaar(tmp_path):
    """Ein Update soll niemandem die Farben umstellen."""
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"schema": 1, "theme": SYSTEM_THEME}), encoding="utf-8")
    store = SettingsStore(path)
    assert store.system_theme_pair == ("Standard - Hell", "Standard - Dunkel")


def test_systemvorgabe_loest_auf_das_paar_auf(tmp_path):
    catalog = ThemeCatalog()
    store = SettingsStore(tmp_path / "settings.json")
    pair = store.system_theme_pair
    assert catalog.resolve(SYSTEM_THEME, False, pair).name == INITIAL_LIGHT_THEME
    assert catalog.resolve(SYSTEM_THEME, True, pair).name == INITIAL_DARK_THEME


def test_ohne_paar_bleibt_es_beim_standard():
    """Alte Aufrufe ohne system_pair duerfen sich nicht anders verhalten."""
    catalog = ThemeCatalog()
    assert catalog.resolve(SYSTEM_THEME, False).name == "Standard - Hell"
    assert catalog.resolve(SYSTEM_THEME, True).name == "Standard - Dunkel"


def test_unbekanntes_paar_faellt_auf_den_standard_zurueck(tmp_path):
    """Ein geloeschtes Profil darf nicht in einer farblosen Oberflaeche enden."""
    catalog = ThemeCatalog()
    profile = catalog.resolve(SYSTEM_THEME, False, ("Gibt Es Nicht", "Auch Nicht"))
    assert profile.name == "Standard - Hell"


def test_das_auslieferungspaar_ist_mitgeliefert():
    catalog = ThemeCatalog()
    for name in (INITIAL_LIGHT_THEME, INITIAL_DARK_THEME):
        assert catalog.get(name) is not None, name
