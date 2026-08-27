"""Startbildschirm, der die Zeit bis zum fertigen Hauptfenster ueberbrueckt.

Zwischen Programmstart und Hauptfenster durchsucht der Host die Modulordner,
liest jedes Manifest, prueft die Modulstaende und baut fuer jedes eine
Kachel. Bisher stand in dieser Zeit nichts auf dem Bildschirm - wer doppelt
klickte, sah nichts und klickte noch einmal. Ein zweiter Host waere ihm die
Meldung ueber die bereits laufende Instanz schuldig geblieben, denn die
Sperre greift erst danach.

Ein Splash, der stumpf bis zum Hauptfenster stehen bleibt, waere aber
schlimmer als keiner: Er wuerde ueber jedem Hinweis kleben, den der Start
zeigen will - etwa der Warnung ueber uebersprungene Module. Deshalb beobachtet dieses Modul die Anwendung - sobald ein
modales Fenster sichtbar wird, verschwindet der Splash; ist das letzte
modale Fenster wieder zu, kommt er zurueck.

Zwei Notbremsen sichern ab, dass er nie haengen bleibt:

* ein Watchdog-Timer schliesst ihn nach :data:`WATCHDOG_MS` in jedem Fall,
* :meth:`StartupSplash.close_active` schliesst ihn aus jedem Fehlerpfad, ohne
  dass der Aufrufer eine Referenz halten muss.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QSplashScreen, QWidget

from .icons import logo_pixmap

_log = logging.getLogger(__name__)

#: Logische Fensterbreite des Splash. Das ausgelieferte Banner ist 512
#: Bildpunkte breit; mehr zu verlangen hiesse, es hochzurechnen.
SPLASH_BREITE = 512

#: Absolute Obergrenze. Auch wenn jeder regulaere Schliesspfad ausfaellt, ist
#: der Splash spaetestens danach weg.
WATCHDOG_MS = 30_000


class _ModalWatcher(QObject):
    """Blendet den Splash aus, solange irgendein modales Fenster offen ist."""

    def __init__(self, splash: StartupSplash, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._splash = splash
        self._offene_modale: set[int] = set()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        art = event.type()
        if art not in (QEvent.Type.Show, QEvent.Type.Hide):
            return False
        if not isinstance(obj, QWidget):
            return False
        try:
            if not obj.isWindow() or obj is self._splash.widget():
                return False
            if art == QEvent.Type.Show and obj.isModal():
                self._offene_modale.add(id(obj))
            else:
                self._offene_modale.discard(id(obj))
        except RuntimeError:
            # Widget bereits zerstoert - dann zaehlt es auch nicht mehr mit.
            self._offene_modale.discard(id(obj))
        self._splash.set_suspended(bool(self._offene_modale))
        return False


class StartupSplash:
    """Duenne Huelle um :class:`QSplashScreen`, tolerant gegen fehlendes Bild.

    Alle Methoden sind auch dann gefahrlos aufrufbar, wenn kein Banner
    gefunden wurde oder der Splash schon geschlossen ist. Der Start braucht
    deshalb keine Fallunterscheidung.
    """

    _active: StartupSplash | None = None

    def __init__(self, splash: QSplashScreen | None) -> None:
        self._splash = splash
        self._suspended = False
        self._closed = False
        self._app: QObject | None = None
        self._watcher: _ModalWatcher | None = None
        self._watchdog: QTimer | None = None

    # ── Erzeugung ────────────────────────────────────────────────

    @classmethod
    def start(cls, app, *, breite: int = SPLASH_BREITE) -> StartupSplash:
        """Zeigt den Splash sofort an und gibt die Steuerung zurueck."""
        cls.close_active()
        instanz = cls(cls._fenster_bauen(app, breite))
        instanz._beobachter_einhaengen(app)
        cls._active = instanz
        return instanz

    @staticmethod
    def _fenster_bauen(app, breite: int) -> QSplashScreen | None:
        # Der Splash liegt auf dem Schreibtisch und nicht auf einer Flaeche
        # des Hosts - und er erscheint, bevor ein Designprofil aufgeloest
        # ist. Massgeblich ist deshalb die Helligkeit des Systemdesigns.
        bild = logo_pixmap(
            breite,
            _hoehe_zu(breite),
            fuer_dunklen_untergrund=_system_ist_dunkel(app),
        )
        if bild is None:
            _log.debug("Kein Banner gefunden - Start ohne Splash.")
            return None
        splash = QSplashScreen(bild, Qt.WindowType.WindowStaysOnTopHint)
        # Das Banner ist transparent; ohne dieses Attribut malte Qt eine
        # undurchsichtige Flaeche hinter das freigestellte Motiv.
        splash.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        splash.setEnabled(False)  # nimmt keine Eingaben an
        splash.show()
        try:
            app.processEvents()
        except (AttributeError, RuntimeError) as fehler:
            _log.debug("processEvents beim Splash-Start fehlgeschlagen: %s", fehler)
        return splash

    def _beobachter_einhaengen(self, app) -> None:
        if self._splash is None:
            return
        self._app = app
        self._watcher = _ModalWatcher(self, self._splash)
        try:
            app.installEventFilter(self._watcher)
        except (AttributeError, RuntimeError) as fehler:
            _log.debug("Splash-Eventfilter nicht installierbar: %s", fehler)
            self._watcher = None

        watchdog = QTimer(self._splash)
        watchdog.setSingleShot(True)
        watchdog.timeout.connect(self._watchdog_abgelaufen)
        watchdog.start(WATCHDOG_MS)
        self._watchdog = watchdog

    # ── Zustand ──────────────────────────────────────────────────

    def widget(self) -> QSplashScreen | None:
        return self._splash

    def is_visible(self) -> bool:
        if self._closed or self._splash is None:
            return False
        try:
            return bool(self._splash.isVisible())
        except RuntimeError:
            return False

    def set_suspended(self, ausgeblendet: bool) -> None:
        """Blendet den Splash aus/ein, ohne ihn endgueltig zu schliessen."""
        if self._closed or self._splash is None:
            return
        ausgeblendet = bool(ausgeblendet)
        if ausgeblendet == self._suspended:
            return
        self._suspended = ausgeblendet
        try:
            if ausgeblendet:
                self._splash.hide()
            else:
                self._splash.show()
        except RuntimeError:
            self._closed = True

    # ── Beenden ──────────────────────────────────────────────────

    def _watchdog_abgelaufen(self) -> None:
        if not self._closed:
            _log.warning(
                "Startbildschirm nach %s ms zwangsweise geschlossen.", WATCHDOG_MS
            )
        self.close()

    def finish(self, fenster: QWidget | None) -> None:
        """Uebergibt an das fertige Hauptfenster und schliesst den Splash."""
        if self._splash is not None and not self._closed and fenster is not None:
            try:
                self._splash.finish(fenster)
            except (RuntimeError, TypeError) as fehler:
                _log.debug("Splash-finish fehlgeschlagen: %s", fehler)
        self.close()

    def close(self) -> None:
        """Schliesst den Splash endgueltig. Mehrfach aufrufbar."""
        if self._closed:
            return
        self._closed = True
        self._beobachter_aushaengen()
        splash, self._splash = self._splash, None
        if splash is not None:
            try:
                splash.hide()
                splash.deleteLater()
            except RuntimeError:
                pass
        if type(self)._active is self:
            type(self)._active = None

    def _beobachter_aushaengen(self) -> None:
        if self._watchdog is not None:
            try:
                self._watchdog.stop()
            except RuntimeError:
                pass
            self._watchdog = None
        if self._watcher is not None and self._app is not None:
            try:
                self._app.removeEventFilter(self._watcher)
            except (AttributeError, RuntimeError):
                pass
        self._watcher = None
        self._app = None

    @classmethod
    def close_active(cls) -> None:
        """Schliesst einen noch offenen Splash - aus jedem Fehlerpfad nutzbar."""
        aktiv = cls._active
        if aktiv is not None:
            aktiv.close()
        cls._active = None


def _hoehe_zu(breite: int) -> int:
    """Grosszuegige Hoehenschranke fuer die Einpassung.

    ``logo_pixmap`` passt mit ``KeepAspectRatio`` ein; bindend ist bei einem
    Banner von mehr als 4:1 immer die Breite. Die Hoehe muss nur gross genug
    sein, um nicht selbst zu binden.
    """
    return max(1, breite)


def _system_ist_dunkel(app) -> bool:
    """Ob der Schreibtisch dunkel ist - so gut, wie Qt es sagen kann.

    Erst die Auskunft von Qt, dann als Rueckfall die Fensterfarbe der
    Palette. Weiss keines von beidem etwas, gilt hell: Das ist die Fassung
    des Banners, die es immer gibt.
    """
    try:
        schema = app.styleHints().colorScheme()
    except (AttributeError, RuntimeError, TypeError):
        schema = None
    if schema is not None:
        if schema == Qt.ColorScheme.Dark:
            return True
        if schema == Qt.ColorScheme.Light:
            return False
    try:
        farbe = app.palette().color(app.palette().ColorRole.Window)
        return farbe.lightness() < 128
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return False



__all__ = ["SPLASH_BREITE", "WATCHDOG_MS", "StartupSplash"]
