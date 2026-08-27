"""Wo die Bilder des Hosts liegen - im Quellbaum wie im gefrorenen Build.

Der LifePlanner trat bis hierhin ohne Bild auf: Das Fenster trug das graue
Ersatzsymbol des Fenstermanagers, die Modulkacheln bestanden aus Text, und
der Installer setzte auf der Verknuepfung das Standardsymbol von Windows.
Vier Programme, die eine Suite sein sollen, sahen an genau der Stelle
zusammenhanglos aus, an der man sie zuerst sieht.

Dieses Modul kennt nur Pfade, kein Qt. Das ist Absicht: Wer wissen will, ob
ein Symbol vorhanden ist - der Paketbau, ein Test, der Installer - soll dafuer
keine Oberflaeche starten muessen. Das Laden uebernimmt
``lifeplanner_core.ui.icons``.

Die Zuordnung Modul zu Bild geschieht ausschliesslich ueber den Dateinamen:
``modules/<modul-id>.png``. Ein viertes Modul braucht damit eine Bilddatei und
keine Zeile Code. Fehlt sie, geben die Funktionen hier ``None`` zurueck - die
Oberflaeche setzt dann ein neutrales Symbol ein, statt eine leere Kachel zu
zeigen.
"""
from __future__ import annotations

import sys
from pathlib import Path

#: Die erzeugten Kantenlaengen des Programmsymbols, aufsteigend.
#: ``tools/generate_icons.py`` schreibt genau diese.
APP_ICON_GROESSEN: tuple[int, ...] = (16, 32, 48, 64, 128, 256, 512)

#: Dateiname des Banners in Bildschirmgroesse, fuer helle Flaechen.
LOGO_DATEI = "lifeplanner-logo-512.png"

#: Dieselbe Zeichnung fuer dunkle Flaechen. Der Schriftzug ist zur Haelfte
#: dunkelblau; auf den dunklen Profilen - Fensterfarben bis #1e1e1e - waere
#: genau dieses halbe Wort weg.
LOGO_HELL_DATEI = "lifeplanner-logo-hell-512.png"

#: Dateiname der Windows-Symboldatei mit mehreren Aufloesungen.
ICO_DATEI = "lifeplanner.ico"


def icons_dir() -> Path:
    """Ordner der mitgelieferten Bilder - im Quellbaum wie im Build.

    Dieselbe Reihenfolge wie ``theme.bundled_theme_dir``: erst das
    Entpackverzeichnis von PyInstaller, dann der Ordner neben der
    ausfuehrbaren Datei, zuletzt der Quellbaum. Gibt es keinen davon,
    kommt der letzte Kandidat zurueck - dann melden die Aufrufer unten
    schlicht "kein Bild", statt hier eine Ausnahme zu werfen.
    """
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        candidates.append(Path(meipass) / "icons")
    if getattr(sys, "frozen", False):
        executable_dir = Path(sys.executable).resolve().parent
        candidates.append(executable_dir / "icons")
        candidates.append(executable_dir / "_internal" / "icons")
    candidates.append(Path(__file__).resolve().parent / "resources" / "icons")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[-1]


def app_icon_pfade() -> dict[int, Path]:
    """Alle vorhandenen Groessen des Programmsymbols, Kantenlaenge zu Datei."""
    ordner = icons_dir()
    gefunden: dict[int, Path] = {}
    for groesse in APP_ICON_GROESSEN:
        pfad = ordner / f"lifeplanner-{groesse}.png"
        if pfad.is_file():
            gefunden[groesse] = pfad
    return gefunden


def app_ico_pfad() -> Path | None:
    """Die ``.ico`` mit mehreren Aufloesungen - fuer Windows und den Installer."""
    pfad = icons_dir() / ICO_DATEI
    return pfad if pfad.is_file() else None


def logo_pfad(*, fuer_dunklen_untergrund: bool = False) -> Path | None:
    """Das breite Logo-Banner in der Fassung fuer diesen Untergrund.

    Fehlt die helle Fassung, kommt die dunkle zurueck: ein schwer lesbares
    Banner ist immer noch besser als eine leere Flaeche.
    """
    if fuer_dunklen_untergrund:
        hell = icons_dir() / LOGO_HELL_DATEI
        if hell.is_file():
            return hell
    pfad = icons_dir() / LOGO_DATEI
    return pfad if pfad.is_file() else None


def modul_icons_dir() -> Path:
    return icons_dir() / "modules"


def modul_icon_pfad(modul_id: str) -> Path | None:
    """Das Bild eines Moduls, oder ``None``.

    ``None`` ist kein Fehler: Ein Modul, das der Host noch nicht kennt, hat
    hier naturgemaess kein Bild. Die Oberflaeche faellt dann auf ein
    neutrales Symbol zurueck.
    """
    kennung = str(modul_id or "").strip().lower()
    # Nur einfache Kennungen. Ein Punkt oder ein Trenner im Namen wuerde die
    # Suche aus dem Bilderordner heraus fuehren - Modul-IDs stammen aus
    # Manifesten, die nicht vom Host geschrieben werden.
    if not kennung or not all(zeichen.isalnum() or zeichen in "-_" for zeichen in kennung):
        return None
    pfad = modul_icons_dir() / f"{kennung}.png"
    return pfad if pfad.is_file() else None


def bekannte_modul_icons() -> dict[str, Path]:
    """Alle abgelegten Modulbilder, Modul-ID zu Datei."""
    ordner = modul_icons_dir()
    if not ordner.is_dir():
        return {}
    return {pfad.stem: pfad for pfad in sorted(ordner.glob("*.png"))}


__all__ = [
    "APP_ICON_GROESSEN",
    "LOGO_HELL_DATEI",
    "app_ico_pfad",
    "app_icon_pfade",
    "bekannte_modul_icons",
    "icons_dir",
    "logo_pfad",
    "modul_icon_pfad",
    "modul_icons_dir",
]
