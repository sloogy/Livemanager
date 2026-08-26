"""Erzeugt die Programmsymbole des Hosts aus den unskalierten Quellbildern.

Die Quellen liegen unter ``lifeplanner_core/resources/icons/original``. Sie
sind der Grund, warum dieses Skript existiert: Wer eine Kante nachzieht oder
ein viertes Modul aufnimmt, legt das neue Quellbild dorthin und laesst den
Lauf erneut durch - statt irgendwo ein von Hand skaliertes PNG abzulegen, das
niemand mehr reproduzieren kann.

    python3 tools/generate_icons.py

Was entsteht:

* ``lifeplanner-<groesse>.png`` in 16/32/48/64/128/256/512 - die ueblichen
  Fenster- und Desktopgroessen.
* ``lifeplanner.ico`` mit denselben Aufloesungen bis 256 in einer Datei.
  Windows sucht sich die passende selbst; eine ``.ico`` mit nur einer
  Groesse sieht in der Taskleiste matschig aus.
* ``lifeplanner-logo-512.png`` - das Banner in Bildschirmgroesse. Die
  Oberflaeche skaliert es weiter herunter, aber nicht aus 2172 Pixeln
  Breite bei jedem Start.
* ``modules/<modul-id>.png`` in 256 Pixeln - die Zuordnung geschieht ueber
  den Dateinamen, nicht ueber eine Liste im Quelltext.

Pillow wird nur hier gebraucht, nicht zur Laufzeit: Der Host liest fertige
PNG-Dateien und laesst Qt skalieren.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / "lifeplanner_core" / "resources" / "icons"
ORIGINAL = ICONS / "original"

#: Fenster-, Task- und Desktopgroessen. 512 ist die Reserve fuer hohe
#: Bildschirmaufloesungen, 16 die Zeile in einem Dateidialog.
APP_GROESSEN = (16, 32, 48, 64, 128, 256, 512)

#: Was in die ``.ico`` geht. Das Format traegt Breite und Hoehe in je einem
#: Byte, 0 steht fuer 256 - mehr passt nicht hinein. Die 512er-PNG-Datei
#: bleibt daneben liegen, sie ist fuer Qt und den Linux-Desktop da.
ICO_GROESSEN = tuple(g for g in APP_GROESSEN if g <= 256)

#: Kachel- und Tabellensymbole. Ein Wert genuegt: Qt verkleinert sauber,
#: vergroessern wuerde es nicht.
MODUL_GROESSE = 256

#: Hoehe des Banners in der Oberflaeche. Das Seitenverhaeltnis der Quelle
#: bleibt erhalten - die Breite ergibt sich daraus.
LOGO_BREITE = 512


def _pillow():
    try:
        from PIL import Image
    except ModuleNotFoundError:  # pragma: no cover - nur ohne Pillow
        print(
            "Pillow fehlt. Dieses Werkzeug laeuft nur bei der Bildpflege, "
            "nicht im Betrieb: python3 -m pip install Pillow",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
    return Image


def _laden(Image, pfad: Path):
    if not pfad.is_file():
        raise SystemExit(f"Quellbild fehlt: {pfad}")
    bild = Image.open(pfad)
    # RGBA, weil die Quellen einen echten Alphakanal haben. Ein Wechsel nach
    # RGB wuerde den durchsichtigen Rand schwarz fuellen.
    return bild.convert("RGBA")


def _skalieren(Image, bild, breite: int, hoehe: int):
    return bild.resize((breite, hoehe), Image.Resampling.LANCZOS)


def app_symbole(Image) -> list[Path]:
    quelle = _laden(Image, ORIGINAL / "lifeplanner-icon.png")
    geschrieben = []
    for groesse in APP_GROESSEN:
        ziel = ICONS / f"lifeplanner-{groesse}.png"
        _skalieren(Image, quelle, groesse, groesse).save(ziel, "PNG", optimize=True)
        geschrieben.append(ziel)
    ico = ICONS / "lifeplanner.ico"
    quelle.save(ico, "ICO", sizes=[(g, g) for g in ICO_GROESSEN])
    geschrieben.append(ico)
    return geschrieben


def logo(Image) -> Path:
    quelle = _laden(Image, ORIGINAL / "lifeplanner-logo.png")
    breite, hoehe = quelle.size
    ziel = ICONS / "lifeplanner-logo-512.png"
    _skalieren(Image, quelle, LOGO_BREITE, round(hoehe * LOGO_BREITE / breite)).save(
        ziel, "PNG", optimize=True
    )
    return ziel


def modul_symbole(Image) -> list[Path]:
    ordner = ICONS / "modules"
    ordner.mkdir(parents=True, exist_ok=True)
    geschrieben = []
    for pfad in sorted((ORIGINAL / "modules").glob("*.png")):
        ziel = ordner / pfad.name
        _skalieren(Image, _laden(Image, pfad), MODUL_GROESSE, MODUL_GROESSE).save(
            ziel, "PNG", optimize=True
        )
        geschrieben.append(ziel)
    if not geschrieben:
        raise SystemExit(f"Keine Modul-Quellbilder in {ORIGINAL / 'modules'}")
    return geschrieben


def main() -> int:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    Image = _pillow()
    ICONS.mkdir(parents=True, exist_ok=True)
    for pfad in [*app_symbole(Image), logo(Image), *modul_symbole(Image)]:
        print(f"{pfad.relative_to(ROOT)}  {pfad.stat().st_size // 1024} KiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
