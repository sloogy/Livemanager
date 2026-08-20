from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..plugin_loader import PluginLoadResult
from ..settings import SettingsStore
from ..theme import SYSTEM_THEME, ThemeCatalog, ThemeProfile, build_stylesheet

SYSTEM_LABEL = "Systemvorgabe (hell/dunkel automatisch)"


class ThemePreview(QFrame):
    """Zeigt ein Designprofil, bevor es übernommen wird."""

    def __init__(self):
        super().__init__()
        self.setObjectName("themePreview")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        self.title = QLabel("Vorschau")
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        self.title.setFont(font)
        layout.addWidget(self.title)
        card = QFrame()
        card.setObjectName("moduleCard")
        card_layout = QVBoxLayout(card)
        card_layout.addWidget(QLabel("BudgetManager"))
        status = QLabel("Läuft")
        status.setObjectName("moduleStatus")
        card_layout.addWidget(status)
        bar = QProgressBar()
        bar.setValue(64)
        card_layout.addWidget(bar)
        buttons = QHBoxLayout()
        primary = QPushButton("Öffnen")
        primary.setObjectName("primaryButton")
        buttons.addWidget(primary)
        buttons.addWidget(QPushButton("Datenordner"))
        card_layout.addLayout(buttons)
        layout.addWidget(card)
        note = QLabel("So sehen Kacheln, Schaltflächen und Hinweise mit diesem Profil aus.")
        note.setObjectName("notice")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)

    def show_profile(self, profile: ThemeProfile) -> None:
        self.title.setText(f"Vorschau: {profile.name}")
        self.setStyleSheet(build_stylesheet(profile))


class AppearancePage(QWidget):
    def __init__(
        self,
        host,
        load_result: PluginLoadResult,
        settings: SettingsStore,
        catalog: ThemeCatalog,
    ):
        super().__init__()
        self.host = host
        self.settings = settings
        self.catalog = catalog
        self.load_result = load_result
        self.module_boxes: dict[str, QComboBox] = {}
        self._build_ui()
        self._load_from_settings()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.addLayout(
            self.host._header(
                "Darstellung",
                "Ein Designprofil für LifePlanner und alle Module. Die Profile sind mit dem "
                "BudgetManager identisch, damit überall dieselben Farben gelten.",
            )
        )

        chooser = QHBoxLayout()
        self.profile_list = QListWidget()
        self.profile_list.setMinimumWidth(280)
        QListWidgetItem(SYSTEM_LABEL, self.profile_list).setData(
            Qt.ItemDataRole.UserRole, SYSTEM_THEME
        )
        for name in self.catalog.names():
            QListWidgetItem(name, self.profile_list).setData(Qt.ItemDataRole.UserRole, name)
        self.profile_list.currentItemChanged.connect(self._preview_current)
        chooser.addWidget(self.profile_list, 1)
        self.preview = ThemePreview()
        chooser.addWidget(self.preview, 1)
        layout.addLayout(chooser, 1)

        self.apply_all = QCheckBox("Dasselbe Design für alle Module verwenden")
        self.apply_all.toggled.connect(self._toggle_module_overrides)
        layout.addWidget(self.apply_all)

        self.module_group = QGroupBox("Design je Modul")
        form = QFormLayout(self.module_group)
        for manifest in self.load_result.modules:
            box = QComboBox()
            box.addItem("Wie LifePlanner", "")
            for name in self.catalog.names():
                box.addItem(name, name)
            self.module_boxes[manifest.module_id] = box
            form.addRow(manifest.name, box)
        if not self.module_boxes:
            form.addRow(QLabel("Kein Modul installiert."))
        layout.addWidget(self.module_group)

        self.hint = QLabel()
        self.hint.setObjectName("notice")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        row = QHBoxLayout()
        apply_button = QPushButton("Übernehmen")
        apply_button.setObjectName("primaryButton")
        apply_button.clicked.connect(self.apply_selection)
        reset = QPushButton("Verwerfen")
        reset.clicked.connect(self._load_from_settings)
        row.addWidget(apply_button)
        row.addWidget(reset)
        row.addStretch(1)
        layout.addLayout(row)

        if self.catalog.errors:
            errors = QLabel("Profile mit Fehlern:\n" + "\n".join(self.catalog.errors))
            errors.setObjectName("errorNotice")
            errors.setWordWrap(True)
            layout.addWidget(errors)

    # -------------------------------------------------------------- Zustand

    def _select(self, name: str) -> None:
        for index in range(self.profile_list.count()):
            item = self.profile_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == name:
                self.profile_list.setCurrentRow(index)
                return
        self.profile_list.setCurrentRow(0)

    def _load_from_settings(self) -> None:
        self._select(self.settings.theme)
        self.apply_all.setChecked(self.settings.theme_applies_to_all)
        overrides = self.settings.get("module_themes", {}) or {}
        for module_id, box in self.module_boxes.items():
            wanted = str(overrides.get(module_id, "") or "") if isinstance(overrides, dict) else ""
            index = box.findData(wanted)
            box.setCurrentIndex(index if index >= 0 else 0)
        self._toggle_module_overrides(self.apply_all.isChecked())
        self._update_hint()

    def selected_theme(self) -> str:
        item = self.profile_list.currentItem()
        if item is None:
            return SYSTEM_THEME
        return str(item.data(Qt.ItemDataRole.UserRole))

    def _preview_current(self) -> None:
        self.preview.show_profile(
            self.catalog.resolve(self.selected_theme(), dark_hint=self.host.prefers_dark())
        )

    def _toggle_module_overrides(self, apply_all: bool) -> None:
        self.module_group.setEnabled(not apply_all and bool(self.module_boxes))
        self._update_hint()

    def _update_hint(self) -> None:
        running = [
            manifest.name
            for manifest in self.load_result.modules
            if (state := self.host.process_manager.get(manifest.module_id)) and state.is_running
        ]
        if running:
            self.hint.setText(
                "Laufende Module übernehmen das Design beim nächsten Start: "
                + ", ".join(running)
            )
        else:
            self.hint.setText(
                "Module erhalten das Profil beim Start. LifePlanner selbst wechselt sofort."
            )

    # ---------------------------------------------------------------- Aktion

    def apply_selection(self) -> None:
        self.settings.set("theme", self.selected_theme())
        self.settings.set("theme_apply_to_all", self.apply_all.isChecked())
        if not self.apply_all.isChecked():
            for module_id, box in self.module_boxes.items():
                self.settings.set_module_theme(module_id, str(box.currentData() or ""))
        self.host.apply_theme()
        self._update_hint()
