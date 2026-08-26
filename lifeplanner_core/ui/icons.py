"""Bilder als Qt-Objekte - mit Rueckfall, wenn eines fehlt.

Die Regel dieses Moduls: Ein fehlendes oder unlesbares Bild darf nie eine
leere Kachel, eine leere Zeile oder einen Absturz erzeugen. Der Starter
listet Module; die Liste ist wichtiger als ihr Schmuck. Darum gibt
``modul_icon`` immer ein anzeigbares Symbol zurueck - notfalls das neutrale
Standardsymbol des Stils.

Warum nicht einfach ``QIcon(pfad)``: Qt beschwert sich ueber eine kaputte
Datei nicht. Und ``QIcon.isNull`` hilft dabei nicht - ein Symbol, das auf
einen Dateinamen zeigt, gilt als vorhanden, auch wenn hinter dem Namen kein
lesbares Bild steht. Erst ``availableSizes`` verraet den Unterschied: Ein
halb heruntergeladenes PNG ergibt eine leere Liste. Ohne diese Pruefung
waere es genau der Fall, den niemand bemerkt, bis die Kachel leer bleibt.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QStyle

from .. import branding


def app_icon() -> QIcon:
    """Das Programmsymbol in allen abgelegten Groessen.

    Alle Groessen in einem ``QIcon``, damit Qt fuer Titelleiste, Taskleiste
    und Alt-Tab jeweils die passende nimmt, statt eine einzige zu skalieren.
    """
    symbol = QIcon()
    for pfad in branding.app_icon_pfade().values():
        symbol.addFile(str(pfad))
    return symbol


def logo_pixmap(breite: int, hoehe: int) -> QPixmap | None:
    """Das Banner, in eine Flaeche eingepasst - oder ``None``.

    Eingepasst heisst: Seitenverhaeltnis erhalten und glatt skaliert. Das
    Banner ist dreimal so breit wie hoch; in eine quadratische Flaeche
    gezwungen waere die Schrift unleserlich.
    """
    pfad = branding.logo_pfad()
    if pfad is None:
        return None
    bild = QPixmap(str(pfad))
    if bild.isNull():
        return None
    return bild.scaled(
        breite,
        hoehe,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def neutrales_modul_icon() -> QIcon:
    """Das Symbol fuer ein Modul ohne eigenes Bild.

    Kein eigenes Bild, sondern das Standardsymbol des gerade aktiven Stils:
    Es passt sich dem Design an und ist erkennbar ein Platzhalter, kein
    falsch zugeordnetes Programmzeichen. ``SP_FileIcon`` und nicht etwa
    ``SP_DesktopIcon``, weil Qt dieses in jeder angefragten Kantenlaenge
    liefert - das Desktopsymbol kommt in fester Groesse und saehe in einer
    Kachel neben den echten Bildern zu klein aus.
    """
    # style() ist in Qt statisch und gibt ohne laufende QApplication None
    # zurueck - derselbe Umgang wie mit QGuiApplication.styleHints() im
    # Hauptfenster. Der Umweg ueber instance() waere nur laenger.
    stil = QApplication.style()
    if stil is None:
        return QIcon()
    return stil.standardIcon(QStyle.StandardPixmap.SP_FileIcon)


def modul_icon(modul_id: str) -> QIcon:
    """Das Bild eines Moduls - immer anzeigbar.

    Fehlt die Datei oder laesst sie sich nicht lesen, kommt das neutrale
    Symbol zurueck. Aufrufer muessen deshalb nichts pruefen.
    """
    pfad = branding.modul_icon_pfad(modul_id)
    if pfad is not None:
        symbol = QIcon(str(pfad))
        if symbol.availableSizes():
            return symbol
    return neutrales_modul_icon()


__all__ = ["app_icon", "logo_pixmap", "modul_icon", "neutrales_modul_icon"]
