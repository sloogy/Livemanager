from __future__ import annotations

from ..i18n import SPRACHEN, t
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

def _system_label() -> str:
    """Erst beim Aufbau der Seite auflösen - beim Import steht die Sprache
    noch nicht fest."""
    return t("darstellung.systemvorgabe_label")


class ThemePreview(QFrame):
    """Zeigt ein Designprofil, bevor es übernommen wird."""

    def __init__(self):
        super().__init__()
        self.setObjectName("themePreview")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        self.title = QLabel(t("darstellung.vorschau"))
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        self.title.setFont(font)
        layout.addWidget(self.title)
        card = QFrame()
        card.setObjectName("moduleCard")
        card_layout = QVBoxLayout(card)
        card_layout.addWidget(QLabel("BudgetManager"))
        status = QLabel(t("gemeinsam.laeuft"))
        status.setObjectName("moduleStatus")
        card_layout.addWidget(status)
        bar = QProgressBar()
        bar.setValue(64)
        card_layout.addWidget(bar)
        buttons = QHBoxLayout()
        primary = QPushButton(t("gemeinsam.oeffnen"))
        primary.setObjectName("primaryButton")
        buttons.addWidget(primary)
        buttons.addWidget(QPushButton(t("gemeinsam.datenordner")))
        card_layout.addLayout(buttons)
        layout.addWidget(card)
        note = QLabel(t("darstellung.vorschau_hinweis"))
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
            self.host._header(t("darstellung.titel"), t("darstellung.einleitung"))
        )

        chooser = QHBoxLayout()
        self.profile_list = QListWidget()
        self.profile_list.setMinimumWidth(280)
        QListWidgetItem(_system_label(), self.profile_list).setData(
            Qt.ItemDataRole.UserRole, SYSTEM_THEME
        )
        for name in self.catalog.names():
            QListWidgetItem(name, self.profile_list).setData(Qt.ItemDataRole.UserRole, name)
        self.profile_list.currentItemChanged.connect(self._preview_current)
        self.profile_list.currentItemChanged.connect(self._toggle_system_group)
        chooser.addWidget(self.profile_list, 1)
        self.preview = ThemePreview()
        chooser.addWidget(self.preview, 1)
        layout.addLayout(chooser, 1)

        # Sprache der Host-Oberflaeche. Sie steht hier, weil Darstellung und
        # Sprache dasselbe betreffen: wie das Programm sich zeigt.
        sprach_gruppe = QGroupBox(t("darstellung.sprache"))
        sprach_form = QFormLayout(sprach_gruppe)
        self.language_box = QComboBox()
        for kuerzel, bezeichnung in SPRACHEN.items():
            self.language_box.addItem(bezeichnung, kuerzel)
        sprach_form.addRow(t("darstellung.sprache"), self.language_box)
        hinweis = QLabel(t("darstellung.sprache_hinweis"))
        hinweis.setWordWrap(True)
        hinweis.setObjectName("notice")
        sprach_form.addRow("", hinweis)
        layout.addWidget(sprach_gruppe)

        # Was "Systemvorgabe" bedeutet, gehört sichtbar dazu: Zu einem dunklen
        # Design gibt es nicht automatisch ein passendes helles, das der Host
        # erfinden könnte.
        self.system_group = QGroupBox(t("darstellung.systemvorgabe"))
        system_form = QFormLayout(self.system_group)
        self.system_light = QComboBox()
        self.system_dark = QComboBox()
        for box in (self.system_light, self.system_dark):
            for name in self.catalog.names():
                box.addItem(name, name)
        system_form.addRow(t("darstellung.system_hell"), self.system_light)
        system_form.addRow(t("darstellung.system_dunkel"), self.system_dark)
        layout.addWidget(self.system_group)

        self.apply_all = QCheckBox(t("darstellung.alle_module"))
        self.apply_all.toggled.connect(self._toggle_module_overrides)
        layout.addWidget(self.apply_all)

        self.module_group = QGroupBox(t("darstellung.je_modul"))
        form = QFormLayout(self.module_group)
        for manifest in self.load_result.modules:
            box = QComboBox()
            box.addItem(t("darstellung.wie_host"), "")
            for name in self.catalog.names():
                box.addItem(name, name)
            self.module_boxes[manifest.module_id] = box
            form.addRow(manifest.name, box)
        if not self.module_boxes:
            form.addRow(QLabel(t("darstellung.kein_modul")))
        layout.addWidget(self.module_group)

        self.hint = QLabel()
        self.hint.setObjectName("notice")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        row = QHBoxLayout()
        apply_button = QPushButton(t("darstellung.uebernehmen"))
        apply_button.setObjectName("primaryButton")
        apply_button.clicked.connect(self.apply_selection)
        reset = QPushButton(t("darstellung.verwerfen"))
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
        index = self.language_box.findData(self.settings.language)
        self.language_box.setCurrentIndex(max(0, index))
        light, dark = self.settings.system_theme_pair
        for box, wanted in ((self.system_light, light), (self.system_dark, dark)):
            box.setCurrentIndex(max(0, box.findData(wanted)))
        self.apply_all.setChecked(self.settings.theme_applies_to_all)
        overrides = self.settings.get("module_themes", {}) or {}
        for module_id, box in self.module_boxes.items():
            wanted = str(overrides.get(module_id, "") or "") if isinstance(overrides, dict) else ""
            index = box.findData(wanted)
            box.setCurrentIndex(index if index >= 0 else 0)
        self._toggle_module_overrides(self.apply_all.isChecked())
        self._toggle_system_group()
        self._update_hint()

    def selected_theme(self) -> str:
        item = self.profile_list.currentItem()
        if item is None:
            return SYSTEM_THEME
        return str(item.data(Qt.ItemDataRole.UserRole))

    def _preview_current(self) -> None:
        self.preview.show_profile(
            self.catalog.resolve(self.selected_theme(),
                                 dark_hint=self.host.prefers_dark(),
                                 system_pair=self._selected_system_pair())
        )

    def _selected_system_pair(self) -> tuple[str, str]:
        return (str(self.system_light.currentData() or ""),
                str(self.system_dark.currentData() or ""))

    def _toggle_system_group(self) -> None:
        self.system_group.setEnabled(self.selected_theme() == SYSTEM_THEME)

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
                t("darstellung.uebernahme_hinweis")
            )

    # ---------------------------------------------------------------- Aktion

    def apply_selection(self) -> None:
        # Zuerst die Sprache: Meldungen, die dieser Aufruf noch ausloest,
        # sollen schon in der neuen Sprache erscheinen.
        self.settings.set_language(str(self.language_box.currentData() or "de"))
        self.settings.set("theme", self.selected_theme())
        self.settings.set_system_theme_pair(*self._selected_system_pair())
        self.settings.set("theme_apply_to_all", self.apply_all.isChecked())
        if not self.apply_all.isChecked():
            for module_id, box in self.module_boxes.items():
                self.settings.set_module_theme(module_id, str(box.currentData() or ""))
        self.host.apply_theme()
        self._update_hint()
