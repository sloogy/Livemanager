"""Menüleiste des Hauptfensters – Aufbau nach der BudgetManager-Vorlage.

Der LifePlanner hatte bis Loop 33 keine, genau wie FPM bis Loop 32 und der
FreizeitManager bis zu diesem Loop. Damit hat jetzt jedes der vier Programme
Datei / Ansicht / Extras / Hilfe an derselben Stelle – der Punkt, um den es
beim Leitgedanken „es soll einer Suite ähneln" geht.

Die Richtlinien stammen aus ``views/help_menu.py`` des BudgetManagers:
kurz halten, mit Trennlinien gruppieren, ``…`` nur vor Befehlen mit
Rückfrage und immer als ein Zeichen, eindeutige Zugriffstasten je Menü,
„Über" zuletzt.

Der LifePlanner ist der Host: Seine Extras sind keine Dateneingaben, sondern
die Werkzeuge, die bisher nur auf der Systemseite lagen – sichern, Diagnose,
Status. Wer sie sucht, musste vorher wissen, dass sie dort sind.

Zur Lebensdauer: ``QMenuBar.addMenu`` gibt in PySide6 eine Hülle zurück, die
Python gehört – fällt der letzte Verweis, nimmt sie das Menü mit. Darum hält
das Fenster seine Menüs in ``_menus`` fest.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenuBar

from ..i18n import t

#: Reihenfolge der Seiten im Stapel - dieselbe wie in der Seitenliste. Das
#: Menue ist eine zweite Tuer zum selben Raum, keine eigene Ordnung.
SEITEN = (
    "navigation.uebersicht",
    "navigation.module",
    "navigation.integration",
    "navigation.darstellung",
    "navigation.updates",
    "navigation.system",
)


def _eintrag(menu, fenster, text: str, callback, *, kuerzel: str = "", tip: str = ""):
    """Ein Menüeintrag mit Zugriffstaste, Kürzel und Statuszeilentext."""
    aktion = QAction(text, fenster)
    if kuerzel:
        aktion.setShortcut(QKeySequence(kuerzel))
        # Ohne diesen Kontext feuert das Kuerzel nur, solange das Menue offen
        # ist - also nie.
        aktion.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
    if tip:
        aktion.setStatusTip(tip)
    aktion.triggered.connect(callback)
    menu.addAction(aktion)
    return aktion


def build_menu_bar(fenster) -> QMenuBar:
    """Baut die Menüleiste des Hauptfensters auf und gibt sie zurück."""
    leiste = fenster.menuBar()
    leiste.clear()
    fenster._menu_bar = leiste
    fenster._menus = [
        _datei_menu(leiste, fenster),
        _ansicht_menu(leiste, fenster),
        _extras_menu(leiste, fenster),
        _hilfe_menu(leiste, fenster),
    ]
    return leiste


def _datei_menu(leiste: QMenuBar, fenster):
    from ..paths import bridge_dir, data_root

    menu = leiste.addMenu(t("menu.file"))
    _eintrag(menu, fenster, t("menu.open_data_folder"),
             lambda: fenster.open_folder(data_root()))
    _eintrag(menu, fenster, t("menu.open_bridge_folder"),
             lambda: fenster.open_folder(bridge_dir(fenster.profile_id)))
    menu.addSeparator()
    _eintrag(menu, fenster, t("menu.exit"), fenster.close,
             kuerzel="Ctrl+Q", tip=t("menu.exit_tip"))
    return menu


def _ansicht_menu(leiste: QMenuBar, fenster):
    menu = leiste.addMenu(t("menu.view"))

    seiten = menu.addMenu(t("menu.pages"))
    fenster._menu_page_actions = []
    for zeile, schluessel in enumerate(SEITEN):
        aktion = QAction(t(schluessel), fenster)
        # Ctrl+1..6, wie die Seitenkuerzel in FPM und BudgetManager.
        aktion.setShortcut(QKeySequence(f"Ctrl+{zeile + 1}"))
        aktion.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        aktion.triggered.connect(lambda _=False, r=zeile: fenster.nav.setCurrentRow(r))
        seiten.addAction(aktion)
        fenster._menu_page_actions.append(aktion)

    menu.addSeparator()

    vollbild = QAction(t("menu.fullscreen"), fenster)
    vollbild.setCheckable(True)
    vollbild.setShortcut(QKeySequence("F11"))
    vollbild.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
    vollbild.setStatusTip(t("menu.fullscreen_tip"))
    vollbild.triggered.connect(lambda an: _vollbild(fenster, an))
    menu.addAction(vollbild)
    fenster._menu_fullscreen_action = vollbild
    fenster._menu_pages = seiten
    return menu


def _extras_menu(leiste: QMenuBar, fenster):
    """Die Werkzeuge des Hosts.

    Sie lagen bisher nur auf der Systemseite - wer sie suchte, musste wissen,
    dass sie dort sind. Dieselben Befehle, nur auffindbar.
    """
    menu = leiste.addMenu(t("menu.extras"))
    _eintrag(menu, fenster, t("menu.backup"), fenster._create_backup)
    _eintrag(menu, fenster, t("menu.diagnostics"), fenster._write_diagnostics)
    menu.addSeparator()
    _eintrag(menu, fenster, t("menu.refresh"), fenster._refresh_status, kuerzel="F5")
    return menu


def _hilfe_menu(leiste: QMenuBar, fenster):
    menu = leiste.addMenu(t("menu.help"))
    _eintrag(menu, fenster, t("menu.check_updates"), fenster.show_updates)
    menu.addSeparator()
    # Ueber steht zuletzt
    _eintrag(menu, fenster, t("menu.about"), lambda: _ueber_zeigen(fenster))
    return menu


def _vollbild(fenster, an: bool) -> None:
    if an:
        fenster.showFullScreen()
    else:
        fenster.showNormal()


def _ueber_zeigen(fenster) -> None:
    """Version, Profil und Datenordner.

    Welches Profil gerade gilt, stand bisher nur klein in der Einleitung der
    Übersichtsseite - und der Datenordner gar nicht.
    """
    from PySide6.QtWidgets import QMessageBox

    from .. import APP_VERSION
    from ..paths import data_root

    QMessageBox.information(
        fenster,
        t("menu.about_title"),
        f"LifePlanner {APP_VERSION}\n\n"
        f"{t('menu.about_profile')} {fenster.profile_id}\n"
        f"{t('menu.about_data')} {data_root()}",
    )


def sync_menu_state(fenster) -> None:
    """Hält das Vollbild-Häkchen mit dem tatsächlichen Zustand gleich."""
    vollbild = getattr(fenster, "_menu_fullscreen_action", None)
    if vollbild is not None:
        vollbild.setChecked(fenster.isFullScreen())


__all__ = ["build_menu_bar", "sync_menu_state", "SEITEN"]
