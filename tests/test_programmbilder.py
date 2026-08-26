"""Die Programmbilder des Hosts und der Module.

Der LifePlanner trat bis hierhin ohne Bild auf. Diese Tests halten fest, was
daran verbindlich ist - und zwar am Verhalten, nicht am Quelltext:

* Das Programmsymbol liegt in den ueblichen Groessen vor, und jede Datei ist
  wirklich so gross, wie ihr Name sagt.
* Die ``.ico`` traegt mehrere Aufloesungen. Eine mit nur einer sieht in der
  Windows-Taskleiste matschig aus, und niemand merkt es beim Bauen.
* Jedes Modul aus ``dependencies/modules.lock.json`` hat ein aufloesbares
  Bild. Nimmt jemand ein viertes auf, ohne ein Bild abzulegen, sagt es der
  Lauf hier statt der Nutzer.
* Der Rueckfall greift. Ein fehlendes Bild darf die Modulliste nicht leeren
  und den Starter nicht abbrechen - das ist die Eigenschaft, die zaehlt.
* Das Banner behaelt sein Seitenverhaeltnis. In eine quadratische Flaeche
  gequetscht waere die Schrift darin unleserlich.

Die Bildmasse werden aus den Dateikoepfen gelesen, nicht mit Pillow: Pillow
gehoert zur Bildpflege (``tools/generate_icons.py``) und steht bewusst nicht
in den Laufzeit-Abhaengigkeiten. Ein Test, der es voraussetzt, waere auf dem
Gate-Rechner uebersprungen und damit wertlos.
"""

from __future__ import annotations

import json
import os
import struct
from pathlib import Path

import pytest

from lifeplanner_core import branding

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

WURZEL = Path(__file__).resolve().parents[1]
ICONS = WURZEL / "lifeplanner_core" / "resources" / "icons"
LOCK = WURZEL / "dependencies" / "modules.lock.json"


def _png_masse(pfad: Path) -> tuple[int, int]:
    """Breite und Hoehe aus dem IHDR-Block einer PNG-Datei."""
    rohdaten = pfad.read_bytes()
    assert rohdaten[:8] == b"\x89PNG\r\n\x1a\n", f"{pfad.name} ist keine PNG-Datei"
    assert rohdaten[12:16] == b"IHDR", f"{pfad.name}: IHDR steht nicht am Anfang"
    breite, hoehe = struct.unpack(">II", rohdaten[16:24])
    return breite, hoehe


def _ico_masse(pfad: Path) -> list[tuple[int, int]]:
    """Alle Bildgroessen aus dem Verzeichnis einer ICO-Datei.

    Breite und Hoehe stehen dort in je einem Byte; 0 bedeutet 256 - deshalb
    die Umrechnung. Genau daran scheitert eine naive Pruefung, die 256er
    Eintraege fuer leer haelt.
    """
    rohdaten = pfad.read_bytes()
    reserviert, typ, anzahl = struct.unpack("<HHH", rohdaten[:6])
    assert (reserviert, typ) == (0, 1), f"{pfad.name} ist keine ICO-Datei"
    masse = []
    for i in range(anzahl):
        eintrag = rohdaten[6 + i * 16 : 6 + i * 16 + 16]
        breite = eintrag[0] or 256
        hoehe = eintrag[1] or 256
        masse.append((breite, hoehe))
    return masse


def _modul_ids() -> list[str]:
    daten = json.loads(LOCK.read_text(encoding="utf-8"))
    return [modul["id"] for modul in daten["modules"]]


# --- Die Dateien selbst -------------------------------------------------


@pytest.mark.parametrize("groesse", branding.APP_ICON_GROESSEN)
def test_das_programmsymbol_liegt_in_jeder_groesse_vor(groesse: int) -> None:
    pfade = branding.app_icon_pfade()
    assert groesse in pfade, f"lifeplanner-{groesse}.png fehlt"
    assert _png_masse(pfade[groesse]) == (groesse, groesse)


def test_die_ico_traegt_mehrere_aufloesungen() -> None:
    pfad = branding.app_ico_pfad()
    assert pfad is not None, "lifeplanner.ico fehlt"
    masse = _ico_masse(pfad)
    assert len(masse) > 1, f"nur eine Aufloesung in der .ico: {masse}"
    # Die kleine fuer Menue und Dateidialog, die grosse fuer die Taskleiste
    # bei hoher Bildschirmaufloesung. Fehlt eine davon, skaliert Windows.
    assert (16, 16) in masse and (256, 256) in masse, masse


def test_das_banner_ist_deutlich_breiter_als_hoch() -> None:
    """Ein quadratisches Banner waere ein verwechseltes Quellbild."""
    pfad = branding.logo_pfad()
    assert pfad is not None, "das Logo-Banner fehlt"
    breite, hoehe = _png_masse(pfad)
    assert breite > hoehe * 2, f"{breite}x{hoehe} sieht nicht nach einem Banner aus"


def test_die_unskalierten_quellbilder_liegen_daneben() -> None:
    """Ohne sie laesst sich tools/generate_icons.py nicht wiederholen."""
    original = ICONS / "original"
    assert (original / "lifeplanner-icon.png").is_file()
    assert (original / "lifeplanner-logo.png").is_file()
    for modul_id in _modul_ids():
        assert (original / "modules" / f"{modul_id}.png").is_file(), modul_id


def test_das_quellbild_ist_groesser_als_jede_ableitung() -> None:
    breite, hoehe = _png_masse(ICONS / "original" / "lifeplanner-icon.png")
    assert breite == hoehe, "das App-Quellbild ist nicht quadratisch"
    assert breite >= max(branding.APP_ICON_GROESSEN), (
        f"{breite}px Quelle fuer bis zu {max(branding.APP_ICON_GROESSEN)}px - hochskaliert"
    )


# --- Zuordnung Modul zu Bild --------------------------------------------


@pytest.mark.parametrize("modul_id", _modul_ids())
def test_jedes_modul_der_lockdatei_hat_ein_bild(modul_id: str) -> None:
    pfad = branding.modul_icon_pfad(modul_id)
    assert pfad is not None, f"{modul_id}: kein Bild unter resources/icons/modules"
    assert _png_masse(pfad) == (256, 256)


def test_die_zuordnung_haengt_nur_am_dateinamen() -> None:
    """Ein viertes Modul soll ohne Codeaenderung dazukommen koennen."""
    abgelegt = branding.bekannte_modul_icons()
    assert set(_modul_ids()).issubset(abgelegt), sorted(abgelegt)
    for modul_id, pfad in abgelegt.items():
        assert branding.modul_icon_pfad(modul_id) == pfad


def test_ein_unbekanntes_modul_liefert_keinen_pfad() -> None:
    assert branding.modul_icon_pfad("gibtesnicht") is None


@pytest.mark.parametrize("kennung", ["", "  ", "../lifeplanner-256", "a/b", "a.b"])
def test_eine_kennung_ausserhalb_des_ordners_wird_abgewiesen(kennung: str) -> None:
    """Modul-IDs stammen aus fremden Manifesten, nicht aus dem Host."""
    assert branding.modul_icon_pfad(kennung) is None


# --- Verhalten der Oberflaeche ------------------------------------------


@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_der_rueckfall_greift_bei_fehlendem_bild(qapp) -> None:
    """Die entscheidende Eigenschaft: die Liste bleibt gefuellt."""
    from lifeplanner_core.ui.icons import modul_icon

    symbol = modul_icon("gibtesnicht")
    assert not symbol.isNull(), "ein fehlendes Bild laesst die Kachel leer"
    assert not symbol.pixmap(48, 48).isNull()


def test_der_rueckfall_greift_auch_bei_unlesbarer_datei(qapp, tmp_path, monkeypatch) -> None:
    """Ein halb heruntergeladenes PNG ist kein Fehler, den Qt meldet."""
    from lifeplanner_core.ui.icons import modul_icon

    ordner = tmp_path / "icons" / "modules"
    ordner.mkdir(parents=True)
    (ordner / "kaputt.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"Muell")
    monkeypatch.setattr(branding, "icons_dir", lambda: tmp_path / "icons")

    symbol = modul_icon("kaputt")
    assert not symbol.isNull()
    assert not symbol.pixmap(48, 48).isNull()


def test_ein_vorhandenes_bild_wird_dem_rueckfall_vorgezogen(qapp) -> None:
    from lifeplanner_core.ui.icons import modul_icon, neutrales_modul_icon

    echt = modul_icon(_modul_ids()[0]).pixmap(48, 48).toImage()
    neutral = neutrales_modul_icon().pixmap(48, 48).toImage()
    assert echt != neutral, "das Modulbild wurde nicht geladen"


def test_das_banner_behaelt_sein_seitenverhaeltnis(qapp) -> None:
    from lifeplanner_core.ui.icons import logo_pixmap

    quelle = _png_masse(branding.logo_pfad())
    verhaeltnis = quelle[0] / quelle[1]
    # Absichtlich eine quadratische Flaeche: Wer KeepAspectRatio vergisst,
    # bekommt hier 1.0 statt der 3 der Quelle.
    bild = logo_pixmap(240, 240)
    assert bild is not None
    assert bild.width() / bild.height() == pytest.approx(verhaeltnis, rel=0.02)
    assert bild.width() <= 240 and bild.height() <= 240


def test_ohne_bilder_gibt_es_kein_banner_statt_eines_leeren(qapp, tmp_path, monkeypatch) -> None:
    from lifeplanner_core.ui.icons import logo_pixmap

    monkeypatch.setattr(branding, "icons_dir", lambda: tmp_path / "leer")
    assert logo_pixmap(240, 80) is None


def _manifeste():
    from lifeplanner_core.manifest import ModuleManifest

    fertig = [
        ModuleManifest(module_id=modul_id, name=modul_id, version="1.0", description="", source_entry="x")
        for modul_id in _modul_ids()
    ]
    # Das vierte, absichtlich ohne Bild: hier muss der Rueckfall greifen.
    fertig.append(
        ModuleManifest(
            module_id="nochkeinbild", name="Zukunftsmodul", version="0.1", description="", source_entry="x"
        )
    )
    return fertig


def test_jede_modulkachel_traegt_ein_bild(qapp, tmp_path, monkeypatch) -> None:
    """Die Startseite ist der Ort, an dem der Nutzer sein Modul sucht."""
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "daten"))
    from PySide6.QtWidgets import QLabel

    from lifeplanner_core.plugin_loader import PluginLoadResult
    from lifeplanner_core.settings import SettingsStore
    from lifeplanner_core.ui.main_window import MainWindow

    manifeste = _manifeste()
    fenster = MainWindow(PluginLoadResult(modules=tuple(manifeste), errors=()), SettingsStore())
    try:
        assert set(fenster.cards) == {m.module_id for m in manifeste}
        for modul_id, kachel in fenster.cards.items():
            gefuellt = [
                w for w in kachel.findChildren(QLabel) if not w.pixmap().isNull()
            ]
            assert gefuellt, f"{modul_id}: Kachel ohne Bild"
    finally:
        fenster.timer.stop()
        fenster.close()


def test_die_modultabelle_traegt_die_bilder(qapp, tmp_path, monkeypatch) -> None:
    """Auch die zweite Liste des Starters, nicht nur die Kacheln."""
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "daten"))
    from lifeplanner_core.plugin_loader import PluginLoadResult
    from lifeplanner_core.settings import SettingsStore
    from lifeplanner_core.ui import module_manager_page as seite
    from lifeplanner_core.ui.main_window import MainWindow

    manifeste = _manifeste()
    geladen = PluginLoadResult(modules=tuple(manifeste), errors=())
    fenster = MainWindow(geladen, SettingsStore())
    try:
        monkeypatch.setattr(seite, "discover_modules", lambda: geladen)
        fenster.module_manager_page.refresh_modules()
        tabelle = fenster.module_manager_page.table
        assert tabelle.rowCount() == len(manifeste)
        for zeile in range(tabelle.rowCount()):
            symbol = tabelle.item(zeile, 0).icon()
            assert not symbol.pixmap(24, 24).isNull(), tabelle.item(zeile, 2).text()
    finally:
        fenster.timer.stop()
        fenster.close()


def test_der_github_katalog_traegt_die_bilder(qapp, tmp_path, monkeypatch) -> None:
    """Die Liste, aus der installiert wird - dort sucht man das Programm zuerst."""
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "daten"))
    from lifeplanner_core.installer_catalog import ModuleRelease
    from lifeplanner_core.plugin_loader import PluginLoadResult
    from lifeplanner_core.settings import SettingsStore
    from lifeplanner_core.ui.main_window import MainWindow

    fenster = MainWindow(PluginLoadResult(modules=(), errors=()), SettingsStore())
    try:
        angebote = tuple(
            ModuleRelease(module_id=modul_id, name=modul_id, repository="sloogy/x", available=True)
            for modul_id in [*_modul_ids(), "nochkeinbild"]
        )
        fenster.module_manager_page._render_github_catalog(angebote)
        tabelle = fenster.module_manager_page.github_table
        assert tabelle.rowCount() == len(angebote)
        for zeile in range(tabelle.rowCount()):
            assert not tabelle.item(zeile, 0).icon().pixmap(24, 24).isNull()
    finally:
        fenster.timer.stop()
        fenster.close()


def test_der_ueber_dialog_zeigt_das_banner(qapp, tmp_path, monkeypatch) -> None:
    """Die Stelle, an der sich das Programm vorstellt."""
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "daten"))
    from lifeplanner_core.plugin_loader import PluginLoadResult
    from lifeplanner_core.settings import SettingsStore
    from lifeplanner_core.ui.main_window import MainWindow
    from lifeplanner_core.ui.menu_bar import _ueber_dialog

    fenster = MainWindow(PluginLoadResult(modules=(), errors=()), SettingsStore())
    try:
        dialog = _ueber_dialog(fenster)
        bild = dialog.iconPixmap()
        assert not bild.isNull(), "der Ueber-Dialog zeigt nur das Standardsymbol"
        quelle = _png_masse(branding.logo_pfad())
        assert bild.width() / bild.height() == pytest.approx(quelle[0] / quelle[1], rel=0.02)
        # Ohne den Platzhalter draengt das Banner den Datenordner in einen
        # Umbruch je Wortsilbe - der Dialog wird dann schmaler als das Bild.
        assert dialog.sizeHint().width() > bild.width() * 2
        dialog.deleteLater()
    finally:
        fenster.timer.stop()
        fenster.close()


def test_das_hauptfenster_traegt_das_programmsymbol(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "daten"))
    from lifeplanner_core.plugin_loader import PluginLoadResult
    from lifeplanner_core.settings import SettingsStore
    from lifeplanner_core.ui.main_window import MainWindow

    fenster = MainWindow(PluginLoadResult(modules=(), errors=()), SettingsStore())
    try:
        verfuegbar = {groesse.width() for groesse in fenster.windowIcon().availableSizes()}
        assert set(branding.APP_ICON_GROESSEN).issubset(verfuegbar), sorted(verfuegbar)
    finally:
        fenster.timer.stop()
        fenster.close()


def test_das_programmsymbol_traegt_alle_groessen(qapp) -> None:
    from lifeplanner_core.ui.icons import app_icon

    symbol = app_icon()
    assert not symbol.isNull()
    verfuegbar = {groesse.width() for groesse in symbol.availableSizes()}
    assert set(branding.APP_ICON_GROESSEN).issubset(verfuegbar), sorted(verfuegbar)


# --- Der Weg in das gebaute Programm ------------------------------------


def _spec_datas() -> list[tuple[str, str]]:
    """Die ``datas``-Liste aus LifePlanner.spec, wirklich ausgewertet."""
    spec = (WURZEL / "LifePlanner.spec").read_text(encoding="utf-8")
    kopf = spec.split("a = Analysis(", 1)[0]
    raum: dict[str, object] = {"SPECPATH": str(WURZEL)}
    exec(compile(kopf, "LifePlanner.spec", "exec"), raum)
    return list(raum["datas"])  # type: ignore[arg-type]


def test_die_spec_packt_die_bilder_in_den_ordner_den_der_host_durchsucht() -> None:
    """Sonst startet der gebaute Host ohne Symbole, ohne dass etwas meldet."""
    datas = _spec_datas()
    ziele = {Path(quelle).name: ordner for quelle, ordner in datas}
    assert ziele.get("lifeplanner.ico") == "icons"
    assert ziele.get(branding.LOGO_DATEI) == "icons"
    for groesse in branding.APP_ICON_GROESSEN:
        assert ziele.get(f"lifeplanner-{groesse}.png") == "icons"
    for modul_id in _modul_ids():
        assert ziele.get(f"{modul_id}.png") == "icons/modules", modul_id


def test_die_unskalierten_quellen_bleiben_aus_dem_paket_draussen() -> None:
    """Zwei Megabyte, die im Betrieb niemand liest."""
    for quelle, _ in _spec_datas():
        assert "original" not in Path(quelle).parts, quelle


@pytest.mark.parametrize(
    "spec", ["LifePlanner.spec", "LifePlannerLauncher.spec", "LifePlannerUpdater.spec"]
)
def test_die_ausfuehrbaren_dateien_tragen_das_symbol(spec: str) -> None:
    text = (WURZEL / spec).read_text(encoding="utf-8")
    assert "icon=icon_datei" in text, f"{spec}: EXE ohne Symbol"
    assert "lifeplanner.ico" in text, f"{spec}: kein Weg zur Symboldatei"


def test_der_windows_installer_bringt_sein_eigenes_symbol_mit() -> None:
    text = (WURZEL / "installer" / "LifePlanner.iss").read_text(encoding="utf-8")
    assert "SetupIconFile=" in text
    assert "lifeplanner.ico" in text
