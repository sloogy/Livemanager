from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..installer_catalog import (
    ModuleRelease,
    default_module_sources,
    download_release_asset,
    query_catalog,
)
from ..manifest import ModuleManifest
from ..module_installer import ModuleInstallerError, ModuleInstallerService, ModulePackageInfo
from ..i18n import t
from ..paths import data_root, module_data_dir, modules_dir
from ..plugin_loader import discover_modules
from ..updater.service import UpdateService


_PERMISSION_LABELS = {
    "own_data_read": "eigene Daten lesen",
    "own_data_write": "eigene Daten schreiben",
    "bridge_read": "Integrationsdaten lesen",
    "bridge_write": "Integrationsdaten schreiben",
    "network_optional": "optionaler Netzwerkzugriff",
    "local_ai_optional": "optionale lokale KI",
}


class _InspectPackageWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, service: ModuleInstallerService, path: Path):
        super().__init__()
        self.service = service
        self.path = path

    def run(self) -> None:
        try:
            self.succeeded.emit(self.service.inspect_package(self.path))
        except Exception as exc:
            self.failed.emit(str(exc))


class _CatalogWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        try:
            self.succeeded.emit(query_catalog(default_module_sources(), timeout=20))
        except Exception as exc:
            self.failed.emit(str(exc))


class _DownloadReleaseWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, release: ModuleRelease, cache_dir: Path):
        super().__init__()
        self.release = release
        self.cache_dir = cache_dir

    def run(self) -> None:
        try:
            self.succeeded.emit(download_release_asset(self.release, self.cache_dir))
        except Exception as exc:
            self.failed.emit(str(exc))


class ModuleManagerPage(QWidget):
    """Install, reinstall and remove isolated LifePlanner modules."""

    def __init__(self, host, load_result):
        super().__init__()
        self.host = host
        self.load_result = load_result
        self.update_service = UpdateService(load_result)
        self.installer = ModuleInstallerService(self.update_service)
        self.inspect_worker: _InspectPackageWorker | None = None
        self.catalog_worker: _CatalogWorker | None = None
        self.download_worker: _DownloadReleaseWorker | None = None
        self.online_releases: tuple[ModuleRelease, ...] = ()
        self._build_ui()
        self.refresh_modules()
        self._show_last_result()
        if not load_result.modules:
            QTimer.singleShot(350, self.refresh_github_catalog)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)

        heading = QLabel(t("module.titel"))
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        heading.setFont(font)
        root.addWidget(heading)

        subtitle = QLabel(
            t("module.einleitung")
        )
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        actions = QFrame()
        actions.setObjectName("moduleCard")
        action_layout = QHBoxLayout(actions)
        self.install_local_button = QPushButton(t("module.paket_installieren"))
        self.install_local_button.setObjectName("primaryButton")
        self.install_local_button.clicked.connect(self.choose_local_package)
        self.github_button = QPushButton(t("module.von_github"))
        self.github_button.clicked.connect(self.refresh_github_catalog)
        folder_button = QPushButton(t("module.ordner_oeffnen"))
        folder_button.clicked.connect(lambda: self.host.open_folder(modules_dir()))
        action_layout.addWidget(self.install_local_button)
        action_layout.addWidget(self.github_button)
        action_layout.addWidget(folder_button)
        action_layout.addStretch(1)
        root.addWidget(actions)

        self.status_label = QLabel(t("module.bereit"))
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("notice")
        root.addWidget(self.status_label)

        online_title = QLabel(t("module.offizielle"))
        online_font = QFont()
        online_font.setBold(True)
        online_title.setFont(online_font)
        root.addWidget(online_title)
        self.github_table = QTableWidget(0, 5)
        self.github_table.setHorizontalHeaderLabels(["Programm", "Repository", "Installiert", "Online", "Aktion"])
        self.github_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.github_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.github_table.verticalHeader().setVisible(False)
        gh_header = self.github_table.horizontalHeader()
        gh_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        gh_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in (2, 3, 4):
            gh_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.github_table.setMaximumHeight(150)
        root.addWidget(self.github_table)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Modul", "Version", "ID", "Status", "Daten"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._update_selection_buttons)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table, 1)

        row = QHBoxLayout()
        refresh_button = QPushButton(t("module.liste_aktualisieren"))
        refresh_button.clicked.connect(self.refresh_modules)
        self.open_program_button = QPushButton(t("module.programmordner"))
        self.open_program_button.clicked.connect(self.open_selected_program_folder)
        self.open_data_button = QPushButton(t("gemeinsam.datenordner"))
        self.open_data_button.clicked.connect(self.open_selected_data_folder)
        self.uninstall_button = QPushButton(t("module.deinstallieren"))
        self.uninstall_button.clicked.connect(self.uninstall_selected)
        row.addWidget(refresh_button)
        row.addWidget(self.open_program_button)
        row.addWidget(self.open_data_button)
        row.addStretch(1)
        row.addWidget(self.uninstall_button)
        root.addLayout(row)

        note = QLabel(
            t("module.sicherheitshinweis")
        )
        note.setWordWrap(True)
        note.setObjectName("notice")
        root.addWidget(note)
        self._update_selection_buttons()

    def refresh_modules(self) -> None:
        self.load_result = discover_modules()
        self.update_service = UpdateService(self.load_result)
        self.installer = ModuleInstallerService(self.update_service)
        modules = self.load_result.modules
        self.table.setRowCount(len(modules))
        for row, manifest in enumerate(modules):
            name_item = QTableWidgetItem(manifest.name)
            name_item.setData(Qt.ItemDataRole.UserRole, manifest.module_id)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(manifest.version))
            self.table.setItem(row, 2, QTableWidgetItem(manifest.module_id))
            running = self.host.process_manager.get(manifest.module_id)
            self.table.setItem(row, 3, QTableWidgetItem(t("gemeinsam.laeuft") if running and running.is_running else "Installiert"))
            data_path = module_data_dir(self.host.profile_id, manifest.module_id)
            self.table.setItem(row, 4, QTableWidgetItem("vorhanden" if data_path.exists() else "noch keine"))
        if self.load_result.errors:
            self.status_label.setText("Einige Modulmanifeste sind ungültig:\n" + "\n".join(self.load_result.errors))
        elif modules:
            self.status_label.setText(f"{len(modules)} Modul(e) installiert.")
        else:
            self.status_label.setText(t("module.noch_keine"))
        self._update_selection_buttons()
        if self.online_releases:
            self._render_github_catalog(self.online_releases)

    def refresh_github_catalog(self) -> None:
        if self.catalog_worker and self.catalog_worker.isRunning():
            return
        self.github_button.setEnabled(False)
        self.status_label.setText(t("module.github_abfrage"))
        self.catalog_worker = _CatalogWorker()
        self.catalog_worker.succeeded.connect(self._catalog_loaded)
        self.catalog_worker.failed.connect(self._catalog_failed)
        self.catalog_worker.finished.connect(self._catalog_finished)
        self.catalog_worker.start()

    def _catalog_finished(self) -> None:
        self.github_button.setEnabled(True)
        self.catalog_worker = None

    def _catalog_failed(self, message: str) -> None:
        self.status_label.setText(f"GitHub-Katalog konnte nicht geladen werden: {message}")
        QMessageBox.warning(self, t("module.github_katalog"), message)

    def _catalog_loaded(self, value: object) -> None:
        releases = tuple(item for item in (value if isinstance(value, tuple) else ()) if isinstance(item, ModuleRelease))
        self.online_releases = releases
        self._render_github_catalog(releases)
        available = sum(1 for item in releases if item.available)
        if available:
            self.status_label.setText(f"{available} offizielles GitHub-Modul ist für dieses Betriebssystem installierbar." if available == 1 else f"{available} offizielle GitHub-Module sind für dieses Betriebssystem installierbar.")
        else:
            self.status_label.setText(t("module.kein_passendes_paket"))

    def _render_github_catalog(self, releases: tuple[ModuleRelease, ...]) -> None:
        installed = {module.module_id: module.version for module in self.load_result.modules}
        self.github_table.setRowCount(len(releases))
        for row, release in enumerate(releases):
            self.github_table.setItem(row, 0, QTableWidgetItem(release.name))
            self.github_table.setItem(row, 1, QTableWidgetItem(release.repository))
            self.github_table.setItem(row, 2, QTableWidgetItem(installed.get(release.module_id, "–")))
            online_text = release.version if release.available else (release.error or "nicht verfügbar")
            online_item = QTableWidgetItem(online_text)
            online_item.setToolTip(release.error or release.description)
            self.github_table.setItem(row, 3, online_item)
            button = QPushButton("Herunterladen & installieren" if release.module_id not in installed else "Aktualisieren / neu installieren")
            button.setEnabled(release.available and not (self.download_worker and self.download_worker.isRunning()))
            if release.available:
                button.clicked.connect(lambda _checked=False, selected=release: self.download_github_release(selected))
            else:
                button.setToolTip(release.error)
            self.github_table.setCellWidget(row, 4, button)

    def download_github_release(self, release: ModuleRelease) -> None:
        if self.download_worker and self.download_worker.isRunning():
            QMessageBox.information(self, t("module.download_laeuft"), t("module.download_laeuft_hinweis"))
            return
        cache = data_root() / "cache" / "github-modules"
        self._set_busy(True, f"{release.name} {release.version} wird aus {release.repository} geladen …")
        self.download_worker = _DownloadReleaseWorker(release, cache)
        self.download_worker.succeeded.connect(self._github_downloaded)
        self.download_worker.failed.connect(self._github_download_failed)
        self.download_worker.finished.connect(self._github_download_finished)
        self.download_worker.start()

    def _github_download_finished(self) -> None:
        self.download_worker = None
        if not (self.inspect_worker and self.inspect_worker.isRunning()):
            self._set_busy(False)
        if self.online_releases:
            self._render_github_catalog(self.online_releases)

    def _github_download_failed(self, message: str) -> None:
        self.status_label.setText(f"GitHub-Download fehlgeschlagen: {message}")
        QMessageBox.critical(self, t("module.download_fehler"), message)

    def _github_downloaded(self, value: object) -> None:
        if not isinstance(value, Path):
            self._github_download_failed("Interner Fehler: heruntergeladene Datei fehlt.")
            return
        self._set_busy(False, f"Download abgeschlossen: {value.name}. Paket wird jetzt geprüft …")
        self.install_package_path(value)

    def refresh_process_states(self) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if not item:
                continue
            module_id = str(item.data(Qt.ItemDataRole.UserRole))
            running = self.host.process_manager.get(module_id)
            status = self.table.item(row, 3)
            if status:
                status.setText(t("gemeinsam.laeuft") if running and running.is_running else "Installiert")

    def _selected_manifest(self) -> ModuleManifest | None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        if not item:
            return None
        module_id = str(item.data(Qt.ItemDataRole.UserRole))
        return next((module for module in self.load_result.modules if module.module_id == module_id), None)

    def _update_selection_buttons(self) -> None:
        enabled = self._selected_manifest() is not None
        self.open_program_button.setEnabled(enabled)
        self.open_data_button.setEnabled(enabled)
        self.uninstall_button.setEnabled(enabled)

    def choose_local_package(self) -> None:
        if self.inspect_worker and self.inspect_worker.isRunning():
            return
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "LifePlanner-Modulpaket auswählen",
            "",
            "LifePlanner-Module (*.lpmodule *.zip);;Alle Dateien (*)",
        )
        if filename:
            self.install_package_path(Path(filename))

    def install_package_path(self, path: Path | str) -> None:
        if self.inspect_worker and self.inspect_worker.isRunning():
            QMessageBox.information(self, t("module.pruefung_laeuft"), t("module.pruefung_laeuft_hinweis"))
            return
        self.host.nav.setCurrentRow(1)
        self._set_busy(True, "Modulpaket wird sicher entpackt und geprüft …")
        self.inspect_worker = _InspectPackageWorker(self.installer, Path(path))
        self.inspect_worker.succeeded.connect(self._package_inspected)
        self.inspect_worker.failed.connect(self._package_failed)
        self.inspect_worker.finished.connect(self._inspect_finished)
        self.inspect_worker.start()

    def _inspect_finished(self) -> None:
        self.inspect_worker = None

    def _package_failed(self, message: str) -> None:
        self._set_busy(False, f"Modulpaket abgelehnt: {message}")
        QMessageBox.critical(self, t("module.paket_abgelehnt"), message)

    def _package_inspected(self, value: object) -> None:
        if not isinstance(value, ModulePackageInfo):
            self._package_failed("Interner Fehler bei der Paketprüfung.")
            return
        info = value
        self._set_busy(False)
        permissions = "\n".join(f"• {_PERMISSION_LABELS.get(item, item)}" for item in info.permissions) or "• keine"
        installed = info.installed_version or "nicht installiert"
        details = (
            f"{info.name}\n"
            f"Version: {info.version}\n"
            f"Installiert: {installed}\n"
            f"Aktion: {info.action}\n"
            f"Signatur: {info.signature_status}\n"
            f"Kompatibilität: {info.compatibility_reason}\n"
            f"SHA-256: {info.archive_sha256}\n\n"
            f"Deklarierte Berechtigungen:\n{permissions}"
        )
        if not info.compatible:
            QMessageBox.critical(self, t("module.nicht_kompatibel"), details)
            self.status_label.setText(f"{info.name} kann nicht installiert werden: {info.compatibility_reason}")
            return

        if not info.signed:
            answer = QMessageBox.warning(
                self,
                t("module.unsigniert"),
                details
                + "\n\nDie Herkunft dieses Pakets kann nicht kryptografisch bestätigt werden. "
                "Das Modul ist ausführbarer Code und läuft mit deinen Benutzerrechten. Installiere es nur, wenn du die Datei selbst erstellt "
                "oder aus einer vertrauenswürdigen Quelle erhalten hast.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
        else:
            answer = QMessageBox.question(
                self,
                f"{info.action}: {info.name}",
                details
                + "\n\nDie Signatur bestätigt die Paket-Herkunft, nicht die Ungefährlichkeit des Codes. "
                "Das Modul läuft mit deinen Benutzerrechten. Installation jetzt vorbereiten?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
        if answer != QMessageBox.StandardButton.Yes:
            self.status_label.setText(t("module.installation_abgebrochen"))
            return

        if info.is_downgrade:
            downgrade = QMessageBox.warning(
                self,
                t("module.downgrade_bestaetigen"),
                f"Du installierst {info.name} {info.version} über die neuere Version {info.installed_version}. "
                "Die Profildaten bleiben erhalten, könnten aber für die ältere Version zu neu sein. Fortfahren?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if downgrade != QMessageBox.StandardButton.Yes:
                self.status_label.setText(t("module.downgrade_abgebrochen"))
                return
        self._install_package(info)

    def _install_package(self, info: ModulePackageInfo) -> None:
        try:
            staged = self.installer.stage_package(info)
            self.host.process_manager.stop(info.component_id, profile_id=self.host.profile_id)
            plan_path = self.update_service.write_plan([staged], parent_pid=os.getpid())
            self.update_service.launch_helper(plan_path)
        except Exception as exc:
            self._set_busy(False)
            QMessageBox.critical(self, t("module.installation_fehler"), str(exc))
            return
        self.status_label.setText(
            f"{info.name} wurde geprüft. LifePlanner wird geschlossen, das Modul installiert und anschließend neu gestartet."
        )
        QMessageBox.information(
            self,
            t("module.wird_installiert"),
            t("module.installation_hinweis"),
        )
        QTimer.singleShot(0, QCoreApplication.quit)

    def uninstall_selected(self) -> None:
        manifest = self._selected_manifest()
        if manifest is None:
            return
        data_path = module_data_dir(self.host.profile_id, manifest.module_id)
        answer = QMessageBox.warning(
            self,
            t("module.deinstallieren"),
            f"{manifest.name} {manifest.version} wird aus LifePlanner entfernt.\n\n"
            f"Die Programmdaten unter {data_path} bleiben bewusst erhalten und können bei einer späteren Neuinstallation weiterverwendet werden.\n\n"
            "Fortfahren?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.host.process_manager.stop(manifest.module_id, profile_id=self.host.profile_id)
            plan_path = self.installer.write_uninstall_plan(manifest.module_id, parent_pid=os.getpid())
            self.update_service.launch_helper(plan_path)
        except Exception as exc:
            QMessageBox.critical(self, t("module.deinstallation_fehler"), str(exc))
            return
        self.status_label.setText(
            f"{manifest.name} wird nach dem Schließen entfernt. Die Profildaten bleiben erhalten."
        )
        QMessageBox.information(
            self,
            t("module.deinstallation_vorbereitet"),
            t("module.deinstallation_hinweis"),
        )
        QTimer.singleShot(0, QCoreApplication.quit)

    def open_selected_program_folder(self) -> None:
        manifest = self._selected_manifest()
        if manifest:
            self.host.open_folder(manifest.module_dir)

    def open_selected_data_folder(self) -> None:
        manifest = self._selected_manifest()
        if manifest:
            self.host.open_folder(module_data_dir(self.host.profile_id, manifest.module_id))

    def _set_busy(self, busy: bool, text: str = "") -> None:
        self.install_local_button.setEnabled(not busy)
        self.github_button.setEnabled(not busy and not (self.catalog_worker and self.catalog_worker.isRunning()))
        self.table.setEnabled(not busy)
        self.github_table.setEnabled(not busy)
        self.uninstall_button.setEnabled((not busy) and self._selected_manifest() is not None)
        if text:
            self.status_label.setText(text)

    def _show_last_result(self) -> None:
        result = self.update_service.read_last_result()
        if not result:
            return
        components = result.get("components", [])
        if not isinstance(components, list):
            return
        actions = []
        for item in components:
            if not isinstance(item, dict):
                continue
            action = str(item.get("action", "replace"))
            label = "deinstalliert" if action == "remove" else "installiert/aktualisiert"
            actions.append(f"{item.get('id')} {label}")
        if actions and result.get("success"):
            self.status_label.setText("Letzte Modulaktion erfolgreich: " + ", ".join(actions))
