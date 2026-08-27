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
* Die ausgelieferten Bilder sind randlos zugeschnitten und die Symbole sitzen
  mittig. Die Bildmappe der Suite liefert ungleiche unsichtbare Raender; ein
  Banner mit Rand wirkt in einer Flaeche fester Hoehe zu klein und rutscht
  aus der Mitte, ein Modulsymbol mit schiefem Rand haengt in der Kachelreihe
  neben den anderen sichtbar daneben.
* Es gibt eine Bannerfassung fuer dunkle Flaechen. Der Schriftzug ist zur
  Haelfte dunkelblau; auf den dunklen Profilen waere das halbe Wort weg.
* Der Startbildschirm ueberbrueckt die Modulsuche und ist danach wieder weg.

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


#: Dieselbe Schwelle wie in tools/generate_icons.py: Die Marken-PNGs der
#: Bildmappe tragen einen unsichtbaren Alphaschleier, der jede Randmessung
#: gegen Null wertlos macht.
ALPHA_SCHWELLE = 8


def _motiv_rahmen(pfad: Path) -> tuple[int, int, int, int]:
    """Rahmen um alles Sichtbare: links, oben, rechts, unten (exklusiv)."""
    from PySide6.QtGui import QImage

    bild = QImage(str(pfad))
    assert not bild.isNull(), f"{pfad.name} laesst sich nicht laden"
    links, oben = bild.width(), bild.height()
    rechts = unten = 0
    for y in range(bild.height()):
        for x in range(bild.width()):
            if bild.pixelColor(x, y).alpha() > ALPHA_SCHWELLE:
                links = min(links, x)
                oben = min(oben, y)
                rechts = max(rechts, x + 1)
                unten = max(unten, y + 1)
    assert rechts > links and unten > oben, f"{pfad.name} ist vollstaendig unsichtbar"
    return links, oben, rechts, unten


def _mittlere_helligkeit(pfad: Path) -> float:
    """Durchschnittliche Helligkeit aller sichtbaren Bildpunkte, 0.0 bis 1.0."""
    from PySide6.QtGui import QImage

    bild = QImage(str(pfad))
    assert not bild.isNull(), f"{pfad.name} laesst sich nicht laden"
    summe = 0.0
    gezaehlt = 0
    for y in range(bild.height()):
        for x in range(bild.width()):
            farbe = bild.pixelColor(x, y)
            if farbe.alpha() > ALPHA_SCHWELLE:
                summe += farbe.lightnessF()
                gezaehlt += 1
    assert gezaehlt, f"{pfad.name} ist vollstaendig unsichtbar"
    return summe / gezaehlt


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


def test_das_banner_hat_keinen_unsichtbaren_rand(qapp) -> None:
    """Randlos, sonst passt es in keine Flaeche.

    Die Quelldatei traegt 69 Bildpunkte links und 42 rechts, 66 oben und 84
    unten. Wer ein solches Bild in eine Flaeche fester Hoehe legt, bekommt ein
    Logo, das zu klein wirkt und sichtbar aus der Mitte rutscht - obwohl das
    Layout korrekt zentriert.
    """
    pfad = branding.logo_pfad()
    assert pfad is not None
    breite, hoehe = _png_masse(pfad)
    assert _motiv_rahmen(pfad) == (0, 0, breite, hoehe)


@pytest.mark.parametrize("groesse", (128, 256, 512))
def test_das_programmsymbol_sitzt_mittig(qapp, groesse: int) -> None:
    """Gleicher Rand links wie rechts und oben wie unten.

    Das Quellbild ist unsymmetrisch beschnitten. Unkorrigiert haengt das
    Symbol in Taskleiste und Titelleiste schief - sichtbar erst neben
    anderen Symbolen.
    """
    links, oben, rechts, unten = _motiv_rahmen(ICONS / f"lifeplanner-{groesse}.png")
    # Eine ungerade Restbreite laesst sich nicht gleichmaessig verteilen,
    # deshalb ein Bildpunkt Spielraum.
    assert abs(links - (groesse - rechts)) <= 1, f"{groesse}px sitzt waagerecht schief"
    assert abs(oben - (groesse - unten)) <= 1, f"{groesse}px sitzt senkrecht schief"


@pytest.mark.parametrize("modul_id", _modul_ids())
def test_jedes_modulsymbol_sitzt_mittig(qapp, modul_id: str) -> None:
    """Sonst haengt eine Kachel in der Reihe sichtbar neben den anderen."""
    pfad = branding.modul_icon_pfad(modul_id)
    assert pfad is not None, modul_id
    breite, hoehe = _png_masse(pfad)
    links, oben, rechts, unten = _motiv_rahmen(pfad)
    assert abs(links - (breite - rechts)) <= 1, f"{modul_id} sitzt waagerecht schief"
    assert abs(oben - (hoehe - unten)) <= 1, f"{modul_id} sitzt senkrecht schief"


def test_es_gibt_eine_bannerfassung_fuer_dunkle_flaechen(qapp) -> None:
    """Auf dunklen Profilen muss das ganze Wort lesbar bleiben.

    Der Schriftzug ist zur Haelfte dunkelblau (#0D1B3A); die Fensterfarben
    der dunklen Profile gehen bis #1e1e1e. Der Test vergleicht die mittlere
    Helligkeit beider Fassungen - die helle muss deutlich heller sein, sonst
    ist sie nur eine Kopie.
    """
    hell = branding.logo_pfad(fuer_dunklen_untergrund=True)
    dunkel = branding.logo_pfad(fuer_dunklen_untergrund=False)
    assert hell is not None and dunkel is not None
    assert hell != dunkel, "ohne eigene Fassung ist das Logo dort halb weg"
    assert _png_masse(hell) == _png_masse(dunkel), "dieselbe Zeichnung"
    assert _mittlere_helligkeit(hell) > _mittlere_helligkeit(dunkel) + 0.15


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
    # bekommt hier 1.0 statt des Seitenverhaeltnisses der Quelle.
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
    assert ziele.get(branding.LOGO_HELL_DATEI) == "icons"
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


# --- Bannerfassung und Startbildschirm ----------------------------------


def test_das_banner_folgt_dem_designprofil(qapp, tmp_path, monkeypatch) -> None:
    """Beim Wechsel auf ein dunkles Profil muss das Banner mitwechseln.

    Es ist ein Bild und kein Text - ein Stylesheet erreicht es nicht. Ohne
    das Auffrischen bliebe die dunkelblaue Haelfte des Schriftzugs stehen und
    verschwaende auf der dunklen Flaeche.
    """
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "daten"))
    from lifeplanner_core.plugin_loader import PluginLoadResult
    from lifeplanner_core.settings import SettingsStore
    from lifeplanner_core.ui.main_window import MainWindow

    # Mit Modulen, nicht ohne: Eine leere Modulliste laesst die Modulseite
    # 350 ms spaeter den GitHub-Katalog abfragen - eine echte Netzanfrage in
    # einem eigenen Thread, die in einem Testlauf nichts zu suchen hat.
    fenster = MainWindow(PluginLoadResult(modules=tuple(_manifeste()), errors=()), SettingsStore())
    try:
        zeile = fenster._logo_label
        assert zeile is not None, "die Startseite zeigt kein Banner"

        def helligkeit() -> float:
            bild = zeile.pixmap().toImage()
            summe = anzahl = 0.0
            # Jeder vierte Bildpunkt genuegt: Gemessen wird ein Mittelwert
            # ueber Zehntausende, und der Test soll nicht sekundenlang
            # rechnen.
            for y in range(0, bild.height(), 4):
                for x in range(0, bild.width(), 4):
                    farbe = bild.pixelColor(x, y)
                    if farbe.alpha() > ALPHA_SCHWELLE:
                        summe += farbe.lightnessF()
                        anzahl += 1
            assert anzahl
            return summe / anzahl

        fenster.settings.set("theme", "Standard - Hell")
        fenster.apply_theme()
        auf_hell = helligkeit()

        fenster.settings.set("theme", "Standard - Dunkel")
        fenster.apply_theme()
        auf_dunkel = helligkeit()

        assert auf_dunkel > auf_hell + 0.15
    finally:
        fenster.close()


def test_der_startbildschirm_ueberbrueckt_und_verschwindet(qapp) -> None:
    """Zwischen Start und Hauptfenster durchsucht der Host die Modulordner."""
    from PySide6.QtWidgets import QWidget

    from lifeplanner_core.ui.startup_splash import StartupSplash

    splash = StartupSplash.start(qapp)
    try:
        assert splash.is_visible()

        fenster = QWidget()
        fenster.show()
        splash.finish(fenster)

        assert not splash.is_visible()
        assert splash.widget() is None
        assert StartupSplash._active is None
        fenster.close()
    finally:
        StartupSplash.close_active()


def test_der_startbildschirm_weicht_einem_modalen_dialog(qapp) -> None:
    """Sonst klebt er ueber der Warnung zu uebersprungenen Modulen."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QDialog

    from lifeplanner_core.ui.startup_splash import StartupSplash

    splash = StartupSplash.start(qapp)
    try:
        assert splash.is_visible()

        sichtbar: list[bool] = []
        dialog = QDialog()
        QTimer.singleShot(
            0, lambda: (sichtbar.append(splash.is_visible()), dialog.accept())
        )
        dialog.exec()
        qapp.processEvents()

        assert sichtbar == [False]
        assert splash.is_visible(), "danach soll er das Laden weiter ueberbruecken"
    finally:
        StartupSplash.close_active()


def test_der_startbildschirm_laesst_sich_ohne_referenz_schliessen(qapp) -> None:
    """Der Notausgang in main.py haelt keine Referenz auf den Splash."""
    from lifeplanner_core.ui.startup_splash import StartupSplash

    splash = StartupSplash.start(qapp)
    StartupSplash.close_active()
    assert not splash.is_visible()

    # Idempotent: ein zweiter Aufruf darf nicht scheitern.
    StartupSplash.close_active()
    splash.close()
    splash.finish(None)
    assert StartupSplash._active is None


def test_schliessen_zerstoert_keine_laufende_katalogabfrage(qapp, tmp_path, monkeypatch) -> None:
    """Wer den Host waehrend der GitHub-Abfrage schliesst, darf keinen Absturz sehen.

    Die Abfrage laeuft in einem eigenen Thread und darf bis zu zwanzig
    Sekunden dauern; auf sie zu warten hiesse, das Schliessen so lange
    aufzuhalten. Wird sie dagegen mit der Seite abgeraeumt, bricht Qt das
    Programm mit "QThread: Destroyed while thread is still running" ab - nach
    dem Schliessen, wenn niemand mehr hinsieht.
    """
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path / "daten"))
    from PySide6.QtCore import QThread

    from lifeplanner_core.plugin_loader import PluginLoadResult
    from lifeplanner_core.settings import SettingsStore
    from lifeplanner_core.ui import module_manager_page as seite
    from lifeplanner_core.ui.main_window import MainWindow

    fenster = MainWindow(PluginLoadResult(modules=tuple(_manifeste()), errors=()), SettingsStore())
    arbeiter = seite._CatalogWorker()
    # Nicht die echte Abfrage: Der Test braucht einen Thread, der beim
    # Schliessen noch laeuft, und keinen Netzzugriff.
    monkeypatch.setattr(type(arbeiter), "run", lambda self: QThread.msleep(400))
    getroffen: list[object] = []
    arbeiter.finished.connect(getroffen.append)
    fenster.module_manager_page.catalog_worker = arbeiter
    arbeiter.start()
    try:
        fenster.close()

        assert fenster.module_manager_page.catalog_worker is None
        assert arbeiter in seite._ABGELOESTE_ARBEITER, (
            "der Arbeiter haengt an nichts mehr und wird mit der Seite abgeraeumt"
        )
        assert arbeiter.wait(5000), "der Thread ist nicht zu Ende gekommen"
        qapp.processEvents()
        assert arbeiter not in seite._ABGELOESTE_ARBEITER, "er traegt sich nicht aus"
        assert getroffen == [], "die Ergebnissignale wurden nicht getrennt"
    finally:
        arbeiter.wait(5000)
        seite._ABGELOESTE_ARBEITER.discard(arbeiter)


def test_der_windows_installer_bringt_sein_eigenes_symbol_mit() -> None:
    text = (WURZEL / "installer" / "LifePlanner.iss").read_text(encoding="utf-8")
    assert "SetupIconFile=" in text
    assert "lifeplanner.ico" in text
