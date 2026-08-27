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
* ``lifeplanner-logo-hell-512.png`` - dieselbe Zeichnung fuer dunkle
  Flaechen. Der Schriftzug ist zur Haelfte dunkelblau; auf den dunklen
  Profilen - Fensterfarben bis #1e1e1e - waere das halbe Wort weg.
* ``modules/<modul-id>.png`` in 256 Pixeln - die Zuordnung geschieht ueber
  den Dateinamen, nicht ueber eine Liste im Quelltext.

Was dabei mit den Quellen geschieht
-----------------------------------
Sie werden nicht unveraendert verkleinert. Die Bildmappe der Suite liefert
PNGs mit ungleichen unsichtbaren Raendern - beim Banner 69 Bildpunkte links
und 42 rechts, 66 oben und 84 unten. Wer ein solches Bild in eine Flaeche
fester Hoehe legt, bekommt ein Logo, das zu klein wirkt und sichtbar aus der
Mitte rutscht, obwohl das Layout korrekt zentriert. Und ein Modulsymbol mit
schiefem Rand haengt in der Kachelreihe neben den anderen sichtbar daneben.

Ueber jedem Blatt liegt zusaetzlich ein Schleier mit Alpha 1 bis 3:
unsichtbar, aber fuer ``getbbox`` deckend. Ein Zuschnitt auf "Alpha > 0"
schnitte deshalb gar nichts weg. Gemessen wird gegen :data:`ALPHA_SCHWELLE`.

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

#: Ab welchem Alphawert ein Bildpunkt als Motiv zaehlt. Zwischen 8 und 128
#: verschiebt sich der Rahmen um hoechstens einen Bildpunkt - die Schwelle
#: ist also nicht empfindlich gewaehlt.
ALPHA_SCHWELLE = 8

#: Rand je Seite der quadratischen Symbole, als Anteil der Kantenlaenge.
#: Randlos darf ein Symbol nicht sein - in 16 Bildpunkten klebt es sonst an
#: der Kante -, aber der Rand muss ringsum gleich sein.
RAND_ANTEIL = 0.02

#: Die vier Flaechenfarben der Bildmappe und ihre Entsprechung fuer dunkle
#: Flaechen. Zugeordnet wird ueber den naechstliegenden Ankerpunkt: Die
#: Bilder bestehen aus flachen Farbfeldern, die nur gegen die Transparenz
#: weichgezeichnet sind - zwischen zwei Feldern liegen kaum Mischwerte, an
#: denen die Zuordnung kippen koennte.
FARB_ANKER: tuple[tuple[tuple[int, int, int], tuple[int, int, int]], ...] = (
    ((13, 27, 58), (255, 255, 255)),      # Dunkelblau -> Weiss
    ((14, 116, 144), (77, 195, 220)),     # Petrol -> helles Petrol
    ((86, 180, 74), (124, 214, 112)),     # Gruen -> helles Gruen
    ((245, 245, 245), (245, 245, 245)),   # Weiss bleibt Weiss
)


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


def _zuschneiden(bild):
    """Schneidet die unsichtbaren Raender weg - gemessen an der Schwelle."""
    maske = bild.getchannel("A").point(
        lambda wert: 255 if wert > ALPHA_SCHWELLE else 0
    )
    rahmen = maske.getbbox()
    if rahmen is None or rahmen == (0, 0, bild.width, bild.height):
        return bild
    return bild.crop(rahmen)


def _quadratisch(Image, bild):
    """Setzt das Motiv mittig auf ein transparentes Quadrat mit gleichem Rand.

    Nicht beschneiden und nicht verzerren: Das Motiv behaelt sein
    Seitenverhaeltnis, die laengere Kante bestimmt die Groesse.
    """
    laengste = max(bild.width, bild.height)
    # Der Rand kommt beidseitig dazu, deshalb geht er zweimal in die Kante ein.
    kante = int(round(laengste / max(1e-6, 1.0 - 2.0 * RAND_ANTEIL)))
    blatt = Image.new("RGBA", (kante, kante), (0, 0, 0, 0))
    blatt.paste(bild, ((kante - bild.width) // 2, (kante - bild.height) // 2), bild)
    return blatt


def _motiv(Image, pfad: Path):
    """Ein quadratisches Symbol: zugeschnitten und mittig eingepasst."""
    return _quadratisch(Image, _zuschneiden(_laden(Image, pfad)))


def _fuer_dunkle_flaechen(Image, bild):
    """Faerbt das Bild fuer dunklen Untergrund um.

    Jeder sichtbare Bildpunkt bekommt die Zielfarbe des naechstliegenden
    Ankers aus :data:`FARB_ANKER`. Unsichtbare Bildpunkte bleiben unberuehrt:
    Ihre Farbe wird nie gezeigt, und der Schleier aus der Bildmappe traegt
    Werte, die jede Zuordnung nur verwirren wuerden.
    """
    anker = list(FARB_ANKER)
    gemerkt: dict[tuple[int, int, int], tuple[int, int, int]] = {}

    def ziel(farbe: tuple[int, int, int]) -> tuple[int, int, int]:
        treffer = gemerkt.get(farbe)
        if treffer is None:
            r, g, b = farbe
            treffer = min(
                anker,
                key=lambda paar: (paar[0][0] - r) ** 2
                + (paar[0][1] - g) ** 2
                + (paar[0][2] - b) ** 2,
            )[1]
            gemerkt[farbe] = treffer
        return treffer

    # Ueber die Rohbytes statt ueber getdata/putdata: das spart eine Million
    # Tupelobjekte und laeuft auf jeder Pillow-Fassung ohne Verfallshinweis.
    roh = bytearray(bild.tobytes())
    for i in range(0, len(roh), 4):
        if roh[i + 3] <= ALPHA_SCHWELLE:
            continue
        roh[i], roh[i + 1], roh[i + 2] = ziel((roh[i], roh[i + 1], roh[i + 2]))
    return Image.frombytes("RGBA", bild.size, bytes(roh))


def app_symbole(Image) -> list[Path]:
    quelle = _motiv(Image, ORIGINAL / "lifeplanner-icon.png")
    geschrieben = []
    for groesse in APP_GROESSEN:
        ziel = ICONS / f"lifeplanner-{groesse}.png"
        _skalieren(Image, quelle, groesse, groesse).save(ziel, "PNG", optimize=True)
        geschrieben.append(ziel)
    ico = ICONS / "lifeplanner.ico"
    quelle.save(ico, "ICO", sizes=[(g, g) for g in ICO_GROESSEN])
    geschrieben.append(ico)
    return geschrieben


def logo(Image) -> list[Path]:
    quelle = _zuschneiden(_laden(Image, ORIGINAL / "lifeplanner-logo.png"))
    breite, hoehe = quelle.size
    verkleinert = _skalieren(
        Image, quelle, LOGO_BREITE, round(hoehe * LOGO_BREITE / breite)
    )
    hell = ICONS / "lifeplanner-logo-512.png"
    verkleinert.save(hell, "PNG", optimize=True)
    dunkel = ICONS / "lifeplanner-logo-hell-512.png"
    _fuer_dunkle_flaechen(Image, verkleinert).save(dunkel, "PNG", optimize=True)
    return [hell, dunkel]


def modul_symbole(Image) -> list[Path]:
    ordner = ICONS / "modules"
    ordner.mkdir(parents=True, exist_ok=True)
    geschrieben = []
    for pfad in sorted((ORIGINAL / "modules").glob("*.png")):
        ziel = ordner / pfad.name
        _skalieren(Image, _motiv(Image, pfad), MODUL_GROESSE, MODUL_GROESSE).save(
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
    for pfad in [*app_symbole(Image), *logo(Image), *modul_symbole(Image)]:
        print(f"{pfad.relative_to(ROOT)}  {pfad.stat().st_size // 1024} KiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
