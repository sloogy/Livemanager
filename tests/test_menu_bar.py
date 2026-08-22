"""Die Menueleiste des Hauptfensters (Loop 33).

Mit dem LifePlanner hat jetzt jedes der vier Programme Datei / Ansicht /
Extras / Hilfe an derselben Stelle. Diese Tests halten fest, was daran
verbindlich ist: nicht die Beschriftungen, sondern der Aufbau und die
Richtlinien aus der BudgetManager-Vorlage.

Und einen zweiten Fund: Die sechs Titel der Seitenliste standen als
deutscher Klartext im Code - Loop 10 hatte sie uebersehen.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from lifeplanner_core.i18n import t
from lifeplanner_core.ui.menu_bar import SEITEN

WURZEL = Path(__file__).resolve().parents[1] / "lifeplanner_core" / "i18n"


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def fenster(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "daten"))
    monkeypatch.setenv("FPM_SUITE_BRIDGE_REGISTRY", str(tmp_path / "bridges.json"))
    from lifeplanner_core.plugin_loader import discover_modules
    from lifeplanner_core.settings import SettingsStore
    from lifeplanner_core.ui.main_window import MainWindow

    w = MainWindow(discover_modules(), SettingsStore())
    yield w
    w.timer.stop()
    w.close()


def _menues(fenster) -> dict:
    """Die Menues, wie das Fenster sie haelt.

    Nicht ueber ``menuBar().actions()[i].menu()``: ``QAction.menu`` liefert in
    PySide6 eine Huelle, die Python gehoert - als verworfener Zwischenwert
    nimmt sie das Menue mit.
    """
    return {menu.title(): menu for menu in fenster._menus}


def test_die_vier_menues_der_vorlage_sind_da(fenster):
    assert list(_menues(fenster)) == [
        t("menu.file"), t("menu.view"), t("menu.extras"), t("menu.help")
    ]


def test_jedes_menue_hat_eindeutige_zugriffstasten(fenster):
    """Zwei Eintraege mit demselben ``&``-Buchstaben machen die Zugriffstaste
    wertlos - sie springt dann nur noch hin und her."""
    for titel, menu in _menues(fenster).items():
        tasten = [a.text().split("&", 1)[1][:1].lower()
                  for a in menu.actions() if "&" in a.text()]
        assert len(tasten) == len(set(tasten)), f"{titel}: {tasten}"


def test_keine_auslassungspunkte_ohne_dialog(fenster):
    """``…`` steht nur vor Befehlen mit Rueckfrage. Der Host hat keine - alle
    seine Befehle laufen sofort los."""
    for menu in _menues(fenster).values():
        for aktion in menu.actions():
            assert "..." not in aktion.text()
            assert not aktion.text().endswith("…"), aktion.text()


def test_ueber_steht_zuletzt(fenster):
    hilfe = _menues(fenster)[t("menu.help")]
    assert [a.text() for a in hilfe.actions() if a.text()][-1] == t("menu.about")


def test_das_ansichtsmenue_kennt_jede_seite(fenster):
    """Das Menue ist eine zweite Tuer zum selben Raum: Was die Seitenliste
    anbietet, muss auch hier stehen - und in derselben Reihenfolge, sonst
    fuehrt Ctrl+3 woanders hin als der dritte Eintrag."""
    assert len(fenster._menu_page_actions) == fenster.nav.count()
    aus_liste = [fenster.nav.item(i).text() for i in range(fenster.nav.count())]
    assert [a.text() for a in fenster._menu_page_actions] == aus_liste


def test_das_seitenkuerzel_fuehrt_auf_dieselbe_seite(fenster):
    for zeile, aktion in enumerate(fenster._menu_page_actions):
        aktion.trigger()
        assert fenster.nav.currentRow() == zeile
        assert fenster.stack.currentIndex() == zeile


def test_die_seitenliste_ist_uebersetzt(fenster):
    """Loop 10 machte den LifePlanner dreisprachig - diese sechs Titel blieben
    dabei deutscher Klartext im Code. Auf Englisch war die Seitenliste damit
    das einzige, was deutsch blieb."""
    aus_liste = [fenster.nav.item(i).text() for i in range(fenster.nav.count())]
    assert aus_liste == [t(s) for s in SEITEN]
    assert not any(s in fenster.nav.item(0).text() for s in ("{", "}"))


def test_jede_sprache_kennt_alle_seitentitel():
    """Ein fehlender Schluessel faellt sonst erst dem auf, der die Sprache
    benutzt - und sieht dann den Schluesselnamen in der Seitenliste."""
    for sprache in ("de", "en", "fr"):
        daten = json.loads((WURZEL / f"{sprache}.json").read_text(encoding="utf-8"))
        for schluessel in SEITEN:
            abschnitt, name = schluessel.split(".")
            assert name in daten[abschnitt], f"{sprache}: {schluessel} fehlt"
            assert daten[abschnitt][name].strip()


def test_zugriffstasten_sind_in_jeder_sprache_eindeutig():
    """Uebersetzt wird Wort fuer Wort, das ``&`` wandert mit - und landet
    leicht auf einem Buchstaben, den im selben Menue schon jemand hat."""
    gruppen = {
        "leiste": ["file", "view", "extras", "help"],
        "file": ["open_data_folder", "open_bridge_folder", "exit"],
        "view": ["pages", "fullscreen"],
        "extras": ["backup", "diagnostics", "refresh"],
        "help": ["check_updates", "about"],
    }
    for sprache in ("de", "en", "fr"):
        menu = json.loads((WURZEL / f"{sprache}.json").read_text(encoding="utf-8"))["menu"]
        for name, schluessel in gruppen.items():
            fehlend = [k for k in schluessel if "&" not in menu[k]]
            assert not fehlend, f"{sprache}/{name} ohne Zugriffstaste: {fehlend}"
            tasten = [menu[k].split("&", 1)[1][:1].lower() for k in schluessel]
            assert len(tasten) == len(set(tasten)), f"{sprache}/{name}: {tasten}"


def test_das_menue_waechst_mit_der_schrift():
    """Loop 8 hat das durchgesetzt, Loop 9 die abgestuften Radien. Eine
    Menueleiste mit festen Pixelwerten waere in beidem ein Rueckschritt - und
    faellt sofort auf, weil sie als einziger Teil der Oberflaeche stehen
    bliebe."""
    from lifeplanner_core.theme import ThemeProfile, build_stylesheet

    def polster(schrift: int) -> str:
        css = build_stylesheet(ThemeProfile("probe", {"schriftgroesse": schrift}))
        i = css.index("QMenuBar::item {")
        return css[i:css.index("}", i)]

    assert polster(9) != polster(16)
    assert "border-radius" in polster(9)
