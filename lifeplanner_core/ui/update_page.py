from __future__ import annotations

import os
from PySide6.QtCore import QCoreApplication, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..updater.service import UpdateCheckResult, UpdateService


class _CheckWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, service: UpdateService, url: str):
        super().__init__()
        self.service = service
        self.url = url

    def run(self) -> None:
        try:
            self.succeeded.emit(self.service.check(self.url))
        except Exception as exc:
            self.failed.emit(str(exc))


class _StageWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, service: UpdateService, result: UpdateCheckResult, component_ids: list[str]):
        super().__init__()
        self.service = service
        self.result = result
        self.component_ids = component_ids

    def run(self) -> None:
        try:
            self.succeeded.emit(self.service.stage(self.result.manifest, self.component_ids))
        except Exception as exc:
            self.failed.emit(str(exc))


class UpdatePage(QWidget):
    def __init__(self, host, load_result, settings):
        super().__init__()
        self.host = host
        self.settings = settings
        self.service = UpdateService(load_result)
        self.check_result: UpdateCheckResult | None = None
        self.check_worker: _CheckWorker | None = None
        self.stage_worker: _StageWorker | None = None
        self._build_ui()
        self._show_last_result()

    def _updates_settings(self) -> dict:
        value = self.settings.get("updates", {})
        return dict(value) if isinstance(value, dict) else {}

    def _save_update_settings(self) -> None:
        value = self._updates_settings()
        value.update(
            {
                "manifest_url": self.url_edit.text().strip(),
                "auto_check": self.auto_check.isChecked(),
                "channel": "stable",
            }
        )
        self.settings.set("updates", value)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        heading = QLabel("Zentrale Updates")
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        heading.setFont(font)
        root.addWidget(heading)
        subtitle = QLabel(
            "LifePlanner prüft Core, installierte Module und neue Module aus dem signierten Online-Katalog gemeinsam. "
            "Jede Komponente wird geprüft, zwischengespeichert und erst nach Rollback-Backup installiert."
        )
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        source = QFrame()
        source.setObjectName("moduleCard")
        source_layout = QVBoxLayout(source)
        source_layout.addWidget(QLabel("Zentrales Update-Manifest"))
        row = QHBoxLayout()
        configured = self._updates_settings().get("manifest_url", "")
        env_url = os.environ.get("LIFEPLANNER_UPDATE_MANIFEST_URL", "").strip()
        self.url_edit = QLineEdit(str(env_url or configured))
        self.url_edit.setPlaceholderText("https://…/lifeplanner-latest.json")
        self.url_edit.setClearButtonEnabled(True)
        self.check_button = QPushButton("Alle Updates prüfen")
        self.check_button.setObjectName("primaryButton")
        self.check_button.clicked.connect(self.check_updates)
        row.addWidget(self.url_edit, 1)
        row.addWidget(self.check_button)
        source_layout.addLayout(row)
        self.auto_check = QCheckBox("Beim Start automatisch prüfen")
        self.auto_check.setChecked(bool(self._updates_settings().get("auto_check", False)))
        self.auto_check.toggled.connect(self._save_update_settings)
        self.url_edit.editingFinished.connect(self._save_update_settings)
        source_layout.addWidget(self.auto_check)
        root.addWidget(source)

        self.status_label = QLabel("Noch nicht geprüft.")
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("notice")
        root.addWidget(self.status_label)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Installieren", "Komponente", "Installiert", "Verfügbar", "Typ", "Status"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in (2, 3, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        select_all = QPushButton("Alle verfügbaren auswählen")
        select_all.clicked.connect(lambda: self._set_all_checks(True))
        select_none = QPushButton("Auswahl aufheben")
        select_none.clicked.connect(lambda: self._set_all_checks(False))
        self.install_button = QPushButton("Auswahl installieren")
        self.install_button.setObjectName("primaryButton")
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self.install_selected)
        buttons.addWidget(select_all)
        buttons.addWidget(select_none)
        buttons.addStretch(1)
        buttons.addWidget(self.install_button)
        root.addLayout(buttons)

        warning = QLabel(
            "Während der Installation werden offene Module kontrolliert beendet. Nicht gespeicherte Eingaben in einem Modul "
            "müssen daher vorher gespeichert werden. Profildaten und Programmdateien erhalten getrennte Rollback-Sicherungen."
        )
        warning.setWordWrap(True)
        warning.setObjectName("notice")
        root.addWidget(warning)

    def auto_check_if_enabled(self) -> None:
        if self.auto_check.isChecked() and self.url_edit.text().strip():
            self.check_updates(silent=True)

    def check_updates(self, _checked: bool = False, *, silent: bool = False) -> None:
        if self.check_worker and self.check_worker.isRunning():
            return
        self._save_update_settings()
        url = self.url_edit.text().strip()
        if not url:
            if not silent:
                QMessageBox.warning(self, "Update-Quelle fehlt", "Bitte die URL des zentralen Update-Manifests eintragen.")
            return
        self._set_busy(True, "Signatur und Versionsstände werden geprüft …")
        self.check_worker = _CheckWorker(self.service, url)
        self.check_worker.succeeded.connect(self._check_succeeded)
        self.check_worker.failed.connect(lambda message: self._check_failed(message, silent=silent))
        self.check_worker.finished.connect(self._worker_finished)
        self.check_worker.start()

    def _check_succeeded(self, result: object) -> None:
        assert isinstance(result, UpdateCheckResult)
        self.check_result = result
        self._populate_table(result)
        count = len(result.available)
        if count:
            installs = sum(1 for status in result.available if not status.installed)
            updates = count - installs
            parts = []
            if updates:
                parts.append(f"{updates} Update(s)")
            if installs:
                parts.append(f"{installs} neue Modulinstallation(en)")
            self.status_label.setText(" und ".join(parts) + " verfügbar. Komponenten sind standardmäßig ausgewählt.")
        else:
            self.status_label.setText("LifePlanner-Core und alle bekannten Module sind aktuell.")
        self.install_button.setEnabled(count > 0)
        self._set_busy(False)

    def _check_failed(self, message: str, *, silent: bool) -> None:
        self.check_result = None
        self.table.setRowCount(0)
        self.status_label.setText(f"Update-Prüfung fehlgeschlagen: {message}")
        self.install_button.setEnabled(False)
        self._set_busy(False)
        if not silent:
            QMessageBox.critical(self, "Update-Prüfung fehlgeschlagen", message)

    def _worker_finished(self) -> None:
        worker = self.sender()
        if worker is self.check_worker:
            self.check_worker = None
        elif worker is self.stage_worker:
            self.stage_worker = None

    def _populate_table(self, result: UpdateCheckResult) -> None:
        self.table.setRowCount(len(result.statuses))
        for row, status in enumerate(result.statuses):
            check_item = QTableWidgetItem()
            check_item.setData(Qt.ItemDataRole.UserRole, status.component_id)
            if status.update_available and status.compatible:
                check_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                check_item.setCheckState(Qt.CheckState.Checked)
            else:
                check_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                check_item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, check_item)
            self.table.setItem(row, 1, QTableWidgetItem(status.name))
            self.table.setItem(row, 2, QTableWidgetItem(status.installed_version))
            self.table.setItem(row, 3, QTableWidgetItem(status.available_version))
            self.table.setItem(row, 4, QTableWidgetItem("Core" if status.kind == "core" else "Modul"))
            self.table.setItem(row, 5, QTableWidgetItem(status.reason))

    def _set_all_checks(self, checked: bool) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def _selected_ids(self) -> list[str]:
        selected: list[str] = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                selected.append(str(item.data(Qt.ItemDataRole.UserRole)))
        return selected

    def install_selected(self) -> None:
        if self.stage_worker and self.stage_worker.isRunning():
            return
        if self.check_result is None:
            return
        selected = self._selected_ids()
        if not selected:
            QMessageBox.information(self, "Keine Auswahl", "Mindestens eine verfügbare Komponente auswählen.")
            return
        names = [
            status.name
            for status in self.check_result.statuses
            if status.component_id in selected
        ]
        answer = QMessageBox.question(
            self,
            "Installation vorbereiten",
            "Folgende Komponenten werden installiert oder aktualisiert:\n\n• "
            + "\n• ".join(names)
            + "\n\nOffene Module werden nach dem Download beendet. Fortfahren?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._set_busy(True, "Updates werden heruntergeladen, geprüft und sicher vorbereitet …")
        self.stage_worker = _StageWorker(self.service, self.check_result, selected)
        self.stage_worker.succeeded.connect(self._stage_succeeded)
        self.stage_worker.failed.connect(self._stage_failed)
        self.stage_worker.finished.connect(self._worker_finished)
        self.stage_worker.start()

    def _stage_succeeded(self, value: object) -> None:
        staged = tuple(value)
        try:
            self.host.process_manager.stop_all(profile_id=self.host.profile_id)
            plan_path = self.service.write_plan(staged, parent_pid=os.getpid())
            self.service.launch_helper(plan_path)
        except Exception as exc:
            self._set_busy(False)
            QMessageBox.critical(self, "Update konnte nicht gestartet werden", str(exc))
            return
        self.status_label.setText(
            "Update vorbereitet. LifePlanner wird jetzt geschlossen; der externe Helfer installiert alle ausgewählten Komponenten und startet neu."
        )
        QMessageBox.information(
            self,
            "Update wird installiert",
            "Alle ausgewählten Komponenten wurden geprüft. LifePlanner wird jetzt geschlossen und nach dem Update automatisch neu gestartet.",
        )
        QTimer.singleShot(0, QCoreApplication.quit)

    def _stage_failed(self, message: str) -> None:
        self._set_busy(False)
        self.status_label.setText(f"Update-Vorbereitung fehlgeschlagen: {message}")
        QMessageBox.critical(self, "Update-Vorbereitung fehlgeschlagen", message)

    def _set_busy(self, busy: bool, text: str = "") -> None:
        self.check_button.setEnabled(not busy)
        self.install_button.setEnabled((not busy) and bool(self.check_result and self.check_result.available))
        self.url_edit.setEnabled(not busy)
        if text:
            self.status_label.setText(text)

    def _show_last_result(self) -> None:
        result = self.service.read_last_result()
        if not result:
            return
        if result.get("success"):
            components = ", ".join(
                f"{item.get('id')} {item.get('version')}" for item in result.get("components", []) if isinstance(item, dict)
            )
            self.status_label.setText(f"Letztes Update erfolgreich: {components or 'Komponenten aktualisiert'}")
        else:
            self.status_label.setText(
                "Das letzte Update ist fehlgeschlagen und wurde zurückgerollt: " + str(result.get("error", "unbekannter Fehler"))
            )
