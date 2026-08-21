from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..backup_service import BackupError, create_profile_backup
from ..bridge import summarize_fpm_outbox
from ..diagnostics import write_diagnostics
from ..manifest import ModuleManifest
from ..paths import bridge_dir, data_root, module_data_dir
from ..repositories import BUDGETMANAGER_REPOSITORY, CORE_REPOSITORY, FPM_REPOSITORY
from ..plugin_loader import PluginLoadResult
from ..process_manager import ModuleLaunchError, ModuleProcessManager
from ..settings import SettingsStore
from ..theme import (SYSTEM_THEME, ThemeCatalog, build_stylesheet,
                     publish_shared_theme, publish_theme)
from .appearance_page import AppearancePage
from .module_manager_page import ModuleManagerPage
from .update_page import UpdatePage

logger = logging.getLogger(__name__)


class ModuleCard(QFrame):
    def __init__(self, manifest: ModuleManifest, host: "MainWindow"):
        super().__init__()
        self.manifest = manifest
        self.host = host
        self.setObjectName("moduleCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        title = QLabel(manifest.name)
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        layout.addWidget(QLabel(f"Version {manifest.version}"))
        desc = QLabel(manifest.description)
        desc.setWordWrap(True)
        layout.addWidget(desc)
        self.status = QLabel("Bereit")
        self.status.setObjectName("moduleStatus")
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        self.launch_button = QPushButton("Öffnen")
        self.launch_button.setObjectName("primaryButton")
        self.launch_button.clicked.connect(self._toggle)
        folder_button = QPushButton("Datenordner")
        folder_button.clicked.connect(self._open_data)
        buttons.addWidget(self.launch_button)
        buttons.addWidget(folder_button)
        layout.addLayout(buttons)

    def _toggle(self) -> None:
        running = self.host.process_manager.get(self.manifest.module_id)
        if running and running.is_running:
            self.host.stop_module(self.manifest)
        else:
            self.host.start_module(self.manifest)

    def _open_data(self) -> None:
        self.host.open_folder(module_data_dir(self.host.profile_id, self.manifest.module_id))

    def refresh(self) -> None:
        running = self.host.process_manager.get(self.manifest.module_id)
        if running and running.is_running:
            self.status.setText("Läuft")
            self.launch_button.setText("Beenden")
        else:
            self.status.setText("Bereit")
            self.launch_button.setText("Öffnen")


class MainWindow(QMainWindow):
    def __init__(self, load_result: PluginLoadResult, settings: SettingsStore, module_package: Path | None = None):
        super().__init__()
        self.settings = settings
        self.profile_id = settings.active_profile
        self.theme_catalog = ThemeCatalog()
        self.process_manager = ModuleProcessManager(settings, self.theme_catalog)
        self.load_result = load_result
        self.cards: dict[str, ModuleCard] = {}
        self.setWindowTitle("LifePlanner")
        self.resize(1120, 720)
        self.setMinimumSize(900, 600)
        self._build_ui(load_result)
        self.apply_theme()
        self._watch_system_color_scheme()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_status)
        self.timer.start(1000)
        QTimer.singleShot(1800, self.update_page.auto_check_if_enabled)
        if module_package is not None:
            QTimer.singleShot(250, lambda: self.module_manager_page.install_package_path(module_package))

    def _build_ui(self, load_result: PluginLoadResult) -> None:
        root = QWidget()
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        self.nav = QListWidget()
        self.nav.setFixedWidth(220)
        for title in ("Übersicht", "Module", "Integration", "Darstellung", "Updates", "System"):
            QListWidgetItem(title, self.nav)
        self.nav.currentRowChanged.connect(self._change_page)
        outer.addWidget(self.nav)
        self.stack = QStackedWidget()
        self.overview_page = self._overview_page(load_result)
        self.module_manager_page = ModuleManagerPage(self, load_result)
        self.integration_page = self._integration_page()
        self.appearance_page = AppearancePage(self, load_result, self.settings, self.theme_catalog)
        self.update_page = UpdatePage(self, load_result, self.settings)
        self.system_page = self._system_page(load_result)
        self.stack.addWidget(self.overview_page)
        self.stack.addWidget(self.module_manager_page)
        self.stack.addWidget(self.integration_page)
        self.stack.addWidget(self.appearance_page)
        self.stack.addWidget(self.update_page)
        self.stack.addWidget(self.system_page)
        outer.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.nav.setCurrentRow(0)

    def _header(self, title: str, subtitle: str) -> QVBoxLayout:
        layout = QVBoxLayout()
        heading = QLabel(title)
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        heading.setFont(font)
        layout.addWidget(heading)
        detail = QLabel(subtitle)
        detail.setWordWrap(True)
        layout.addWidget(detail)
        return layout

    def _overview_page(self, load_result: PluginLoadResult) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.addLayout(self._header("Dein LifePlanner", f"Profil: {self.profile_id} · Wähle ein Modul und arbeite fokussiert weiter."))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        grid = QGridLayout(content)
        grid.setSpacing(18)
        for index, manifest in enumerate(load_result.modules):
            card = ModuleCard(manifest, self)
            self.cards[manifest.module_id] = card
            grid.addWidget(card, index // 2, index % 2)
        if not load_result.modules:
            grid.addWidget(QLabel("Keine gültigen Module gefunden."), 0, 0)
        grid.setRowStretch((len(load_result.modules) + 1) // 2, 1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return page

    def _integration_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.addLayout(self._header("Integration", "Module tauschen ausschließlich prüfbare Dateien und Events aus - niemals direkte SQL-Zugriffe."))
        self.bridge_summary = QLabel()
        self.bridge_summary.setWordWrap(True)
        layout.addWidget(self.bridge_summary)
        row = QHBoxLayout()
        refresh = QPushButton("Status aktualisieren")
        refresh.clicked.connect(self._refresh_bridge)
        folder = QPushButton("Bridge-Ordner öffnen")
        folder.clicked.connect(lambda: self.open_folder(bridge_dir(self.profile_id)))
        row.addWidget(refresh)
        row.addWidget(folder)
        row.addStretch(1)
        layout.addLayout(row)
        note = QLabel(
            "FPM schreibt ausschließlich prüfbare Vorschläge. BudgetManager übernimmt sie erst nach Freigabe in der Import-Inbox. "
            "Der zentrale Updater aktualisiert Core und Module getrennt, ohne ihre Datenbanken miteinander zu koppeln."
        )
        note.setWordWrap(True)
        note.setObjectName("notice")
        layout.addWidget(note)
        layout.addStretch(1)
        self._refresh_bridge()
        return page

    def _system_page(self, load_result: PluginLoadResult) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.addLayout(self._header("System", "Zentrale Pfade, Sicherung und Diagnose des LifePlanner-Core."))
        path_label = QLabel(
            f"Lokaler LifePlanner-Datenstamm:\n{data_root()}\n\n"
            f"GitHub Core: {CORE_REPOSITORY}\n"
            f"BudgetManager: {BUDGETMANAGER_REPOSITORY}\n"
            f"FPM: {FPM_REPOSITORY}"
        )
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(path_label)
        module_text = "\n".join(f"• {m.name} {m.version}" for m in load_result.modules) or "• keine"
        layout.addWidget(QLabel(f"Geladene Module:\n{module_text}"))
        if load_result.errors:
            error = QLabel("Modulfehler:\n" + "\n".join(load_result.errors))
            error.setWordWrap(True)
            error.setObjectName("errorNotice")
            layout.addWidget(error)
        row = QHBoxLayout()
        backup = QPushButton("Profil sichern")
        backup.setObjectName("primaryButton")
        backup.clicked.connect(self._create_backup)
        diagnostics = QPushButton("Diagnose schreiben")
        diagnostics.clicked.connect(self._write_diagnostics)
        open_data = QPushButton("Datenordner öffnen")
        open_data.clicked.connect(lambda: self.open_folder(data_root()))
        row.addWidget(backup)
        row.addWidget(diagnostics)
        row.addWidget(open_data)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(1)
        return page

    def _change_page(self, row: int) -> None:
        if row >= 0:
            self.stack.setCurrentIndex(row)
            current = self.stack.currentWidget()
            if current is self.module_manager_page:
                self.module_manager_page.refresh_modules()
            elif current is self.appearance_page:
                self.appearance_page._load_from_settings()

    def show_updates(self) -> None:
        self.nav.setCurrentRow(self.stack.indexOf(self.update_page))

    def start_module(self, manifest: ModuleManifest) -> None:
        try:
            self.process_manager.start(manifest, self.profile_id)
            self.cards[manifest.module_id].refresh()
        except ModuleLaunchError as exc:
            QMessageBox.critical(self, "Modulstart fehlgeschlagen", str(exc))

    def stop_module(self, manifest: ModuleManifest) -> None:
        self.process_manager.stop(manifest.module_id, profile_id=self.profile_id)
        self.cards[manifest.module_id].refresh()

    def _refresh_status(self) -> None:
        for card in self.cards.values():
            card.refresh()
        self.module_manager_page.refresh_process_states()

    def _refresh_bridge(self) -> None:
        """Zeigt alle drei Brückendateien statt nur der FPM-Richtung.

        Entscheidend ist die Unterscheidung zwischen "Datei fehlt" und "Datei
        ist leer": Fehlt sie, hat das schreibende Programm noch nichts
        abgelegt - dann liegt es dort, nicht an der Brücke.
        """
        summary = summarize_fpm_outbox(self.profile_id)
        zeilen: list[str] = []
        for befund in summary.dateien:
            if not befund.vorhanden:
                zeilen.append(
                    f"{befund.name}: noch nichts geschrieben "
                    f"({befund.pfad.name})"
                )
                continue
            waehrungen = ", ".join(befund.waehrungen) or "-"
            hinweis = (
                f" · ungültige Zeilen {befund.ungueltige_zeilen}"
                if befund.ungueltige_zeilen
                else ""
            )
            zeilen.append(
                f"{befund.name}: {befund.eintraege} Einträge · "
                f"Summe {befund.summe:.2f} · Währungen {waehrungen}{hinweis}"
            )
        zeilen.append(str(bridge_dir(self.profile_id)))
        self.bridge_summary.setText("\n".join(zeilen))

    def _create_backup(self) -> None:
        try:
            path = create_profile_backup(self.profile_id)
        except BackupError as exc:
            QMessageBox.critical(self, "Sicherung fehlgeschlagen", str(exc))
            return
        QMessageBox.information(self, "Sicherung erstellt", f"Das Profil wurde geprüft und gesichert:\n{path}")

    def _write_diagnostics(self) -> None:
        path = write_diagnostics()
        QMessageBox.information(self, "Diagnose erstellt", f"Diagnosedatei:\n{path}")

    @staticmethod
    def open_folder(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.process_manager.stop_all(profile_id=self.profile_id)
        super().closeEvent(event)

    def _watch_system_color_scheme(self) -> None:
        """Auf den Hell/Dunkel-Wechsel des Betriebssystems reagieren.

        Ohne diese Verbindung griffe das Profil "system" erst beim nächsten
        Start - und genau dann hilft es niemandem. Der Host reicht das Profil
        anschließend an alle laufenden Module weiter.
        """
        app = QApplication.instance()
        if app is None:
            return
        signal = getattr(app.styleHints(), "colorSchemeChanged", None)
        if signal is None:  # Qt älter als 6.5
            return
        signal.connect(self._system_color_scheme_changed)

    def _system_color_scheme_changed(self, _scheme) -> None:
        if str(self.settings.theme or "").strip().lower() != SYSTEM_THEME:
            return
        self.apply_theme()

    def prefers_dark(self) -> bool:
        """Ob das System dunkel eingestellt ist - Grundlage für das Profil "system".

        Qt sagt es seit 6.5 direkt. Die Palette bleibt als Rückfall: sie ist ein
        Umweg über die Fensterfarbe und liegt daneben, sobald ein Stylesheet
        oder ein Plattformthema dazwischenfunkt.
        """
        hints = QApplication.instance().styleHints() if QApplication.instance() else None
        scheme = getattr(hints, "colorScheme", None)
        if scheme is not None:
            value = scheme()
            if value == Qt.ColorScheme.Dark:
                return True
            if value == Qt.ColorScheme.Light:
                return False
        window = self.palette().color(self.palette().ColorRole.Window)
        return window.lightness() < 128

    def apply_theme(self) -> None:
        """Wendet das gewählte Profil auf den Host an und stellt es Modulen bereit."""
        profile = self.theme_catalog.resolve(
            self.settings.theme, dark_hint=self.prefers_dark(),
            system_pair=self.settings.system_theme_pair)
        self.process_manager.prefers_dark = self.prefers_dark()
        self.setStyleSheet(build_stylesheet(profile))
        font = self.font()
        font.setPointSize(profile.font_size)
        self.setFont(font)
        try:
            for module_id in list(self.cards):
                publish_theme(self.profile_id, module_id, self.theme_catalog.resolve(
                    self.settings.theme_for(module_id), dark_hint=self.prefers_dark(),
                    system_pair=self.settings.system_theme_pair
                ))
            if self.settings.theme_applies_to_all:
                # Nur bei "für alle" veröffentlichen - sonst würde der Eintrag
                # die abweichende Wahl einzelner Module überstimmen.
                publish_shared_theme(self.profile_id, profile)
        except OSError as exc:
            logger.warning("Designprofil nicht schreibbar: %s", exc)
