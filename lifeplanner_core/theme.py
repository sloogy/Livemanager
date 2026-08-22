"""Zentrale Designprofile für den Host und alle Module.

Die Profildateien unter ``lifeplanner_core/themes`` verwenden dasselbe Schema
wie die Profile des BudgetManagers. Damit bedeutet "überall dasselbe Theme"
tatsächlich dieselben Farbwerte und nicht nur denselben Namen.

Der Host wählt ein Profil aus, schreibt es je Modul in den Profilordner und
reicht Name und Dateipfad über die Umgebung an den Modulprozess weiter. Module
bleiben eigenständige Programme; sie lesen das Profil, statt dass der Host in
sie hineingreift.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import APP_VERSION
from .paths import bridge_dir, profile_dir

THEME_ENV_NAME = "LIFEPLANNER_THEME"
THEME_ENV_FILE = "LIFEPLANNER_THEME_FILE"
SYSTEM_THEME = "system"

# Der FreizeitManager hat dieses Austauschformat im Bridge-Ordner bereits
# festgelegt. Host und Module verwenden es unverändert weiter, damit es im
# Ökosystem genau ein Themeformat gibt und nicht zwei.
SHARED_THEME_SCHEMA = "lifeplanner.theme.v1"
SHARED_THEME_FILE = "shared_theme.json"

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def bundled_theme_dir() -> Path:
    """Ordner der mitgelieferten Profile - im Quellbaum wie im Build."""
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        candidates.append(Path(meipass) / "themes")
    if getattr(sys, "frozen", False):
        executable_dir = Path(sys.executable).resolve().parent
        candidates.append(executable_dir / "themes")
        candidates.append(executable_dir / "_internal" / "themes")
    candidates.append(Path(__file__).resolve().parent / "themes")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[-1]


# Fallback, falls die mitgelieferten Profildateien fehlen (verstümmeltes
# Paket, defekter Build). Der Host bleibt dann bedienbar statt farblos.
_FALLBACK: dict[str, dict[str, Any]] = {
    "Standard - Hell": {
        "modus": "hell",
        "hintergrund_app": "#ffffff",
        "hintergrund_panel": "#f6f7f9",
        "hintergrund_seitenleiste": "#f0f2f5",
        "text": "#111111",
        "text_gedimmt": "#444444",
        "akzent": "#2f80ed",
        "tabelle_gitter": "#d6dbe3",
        "auswahl_hintergrund": "#2f80ed",
        "auswahl_text": "#ffffff",
        "schriftgroesse": 10,
    },
    "Standard - Dunkel": {
        "modus": "dunkel",
        "hintergrund_app": "#1e1e1e",
        "hintergrund_panel": "#2d2d30",
        "hintergrund_seitenleiste": "#252526",
        "text": "#cccccc",
        "text_gedimmt": "#808080",
        "akzent": "#007acc",
        "tabelle_gitter": "#3e3e42",
        "auswahl_hintergrund": "#007acc",
        "auswahl_text": "#ffffff",
        "schriftgroesse": 10,
    },
}


class ThemeError(ValueError):
    pass


@dataclass(frozen=True)
class ThemeProfile:
    name: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def mode(self) -> str:
        return str(self.data.get("modus", "hell")).strip().lower()

    @property
    def is_dark(self) -> bool:
        return self.mode == "dunkel"

    @property
    def font_size(self) -> int:
        try:
            return max(6, min(30, int(self.data.get("schriftgroesse", 10) or 10)))
        except (TypeError, ValueError):
            return 10

    def color(self, key: str, default: str) -> str:
        value = str(self.data.get(key, "") or "").strip()
        return value if _HEX_RE.fullmatch(value) else default

    def to_dict(self) -> dict[str, Any]:
        payload = dict(self.data)
        payload["name"] = self.name
        return payload


def _validate(name: str, data: dict[str, Any]) -> None:
    if str(data.get("modus", "hell")).strip().lower() not in ("hell", "dunkel"):
        raise ThemeError(f"Profil {name}: modus muss 'hell' oder 'dunkel' sein")
    try:
        size = int(data.get("schriftgroesse", 10) or 10)
    except (TypeError, ValueError) as exc:
        raise ThemeError(f"Profil {name}: ungültige schriftgroesse") from exc
    if not 6 <= size <= 30:
        raise ThemeError(f"Profil {name}: schriftgroesse {size} außerhalb 6..30")
    for key, value in data.items():
        if isinstance(value, str) and value.strip().startswith("#") and not _HEX_RE.fullmatch(value.strip()):
            raise ThemeError(f"Profil {name}: ungültige Farbe {key}={value}")


class ThemeCatalog:
    """Liest die mitgelieferten Designprofile ein."""

    def __init__(self, directory: Path | None = None):
        self.directory = directory or bundled_theme_dir()
        self._profiles: dict[str, ThemeProfile] = {}
        self.errors: list[str] = []
        self.reload()

    def reload(self) -> None:
        self._profiles.clear()
        self.errors.clear()
        if self.directory.is_dir():
            for path in sorted(self.directory.glob("*.json")):
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    self.errors.append(f"{path.name}: {exc}")
                    continue
                if not isinstance(raw, dict):
                    self.errors.append(f"{path.name}: kein JSON-Objekt")
                    continue
                data = dict(raw)
                name = str(data.pop("name", "") or "").strip() or path.stem.replace("_", " ")
                try:
                    _validate(name, data)
                except ThemeError as exc:
                    self.errors.append(str(exc))
                    continue
                self._profiles[name] = ThemeProfile(name, data)
        for name, data in _FALLBACK.items():
            self._profiles.setdefault(name, ThemeProfile(name, dict(data)))

    def names(self) -> list[str]:
        return sorted(self._profiles, key=str.casefold)

    def get(self, name: str) -> ThemeProfile | None:
        return self._profiles.get(str(name or "").strip())

    def default_name(self, dark: bool = False) -> str:
        wanted = "Standard - Dunkel" if dark else "Standard - Hell"
        if wanted in self._profiles:
            return wanted
        for name in self.names():
            if self._profiles[name].is_dark == dark:
                return name
        return self.names()[0]

    def resolve(self, name: str, dark_hint: bool = False,
                system_pair: tuple[str, str] | None = None) -> ThemeProfile:
        """Profil zum Namen; ``system`` folgt dem Paar, Unbekanntes dem Standard.

        ``system_pair`` sagt, was "system" bedeutet - ohne Angabe bleibt es beim
        Standardpaar. So kann eine neue Installation mit einem anderen
        Auslieferungsdesign starten, ohne dass bestehende ihres verlieren.
        """
        profile = self.get(name)
        if profile is not None:
            return profile
        if str(name or "").strip().lower() == SYSTEM_THEME and system_pair:
            wanted = system_pair[1] if dark_hint else system_pair[0]
            chosen = self.get(wanted)
            if chosen is not None:
                return chosen
        return self._profiles[self.default_name(dark_hint)]


def build_stylesheet(profile: ThemeProfile) -> str:
    """Stylesheet für die Host-Oberfläche aus einem Designprofil."""
    bg_app = profile.color("hintergrund_app", "#ffffff")
    bg_panel = profile.color("hintergrund_panel", bg_app)
    bg_side = profile.color("hintergrund_seitenleiste", bg_panel)
    text = profile.color("text", "#111111")
    text_dim = profile.color("text_gedimmt", text)
    accent = profile.color("akzent", "#2f80ed")
    grid = profile.color("tabelle_gitter", text_dim)
    sel_bg = profile.color("auswahl_hintergrund", accent)
    sel_text = profile.color("auswahl_text", "#ffffff")
    hover_bg = profile.color("hover_hintergrund", sel_bg)
    hover_text = profile.color("hover_text", sel_text)
    field_bg = profile.color("dropdown_bg", bg_panel)
    field_text = profile.color("dropdown_text", text)
    field_border = profile.color("dropdown_border", grid)

    # Groessen wachsen mit der eingestellten Schrift, wie in den Modulen.
    # Vorher standen hier feste Pixelwerte: Wer die Schrift hochstellte, bekam
    # groesseren Text in unveraendert engen Schaltflaechen.
    scale = max(0.85, min(1.50, profile.font_size / 10.0))

    def px(wert: float) -> int:
        return max(1, round(wert * scale))

    # Abgestufte Radien nach dem Vorbild des BudgetManagers: je groesser die
    # Flaeche, desto runder die Ecke.
    radius_feld = px(4)
    radius = px(6)
    radius_karte = px(8)
    return f"""
QMainWindow, QWidget {{ background: {bg_app}; color: {text}; }}
QLabel {{ color: {text}; background: transparent; }}

/* Loop 33: Menueleiste, nach der BudgetManager-Vorlage. Sie wuchs sonst als
   einziger Teil der Oberflaeche nicht mit der Schrift und truege keinen der
   abgestuften Radien. */
QMenuBar {{ background: {bg_panel}; color: {text}; font-size: {px(14)}px; padding: {px(2)}px; }}
QMenuBar::item {{ padding: {px(4)}px {px(10)}px; border-radius: {radius}px; }}
QMenuBar::item:selected {{ background: {sel_bg}; color: {sel_text}; }}
QMenu {{ background: {bg_panel}; color: {text}; border: 1px solid {grid}; border-radius: {radius}px; padding: {px(4)}px; font-size: {px(14)}px; }}
QMenu::item {{ padding: {px(6)}px {px(18)}px; border-radius: {radius_feld}px; }}
QMenu::item:selected {{ background: {sel_bg}; color: {sel_text}; }}
QMenu::item:disabled {{ color: {text_dim}; }}
QMenu::separator {{ height: 1px; background: {grid}; margin: {px(4)}px {px(8)}px; }}
QListWidget {{ background: {bg_side}; color: {text}; border: 0; padding: {px(18)}px {px(8)}px; font-size: {px(15)}px; }}
QListWidget::item {{ padding: 12px; border-radius: {radius_karte}px; margin: 2px 0; }}
QListWidget::item:hover {{ background: {hover_bg}; color: {hover_text}; }}
QListWidget::item:selected {{ background: {sel_bg}; color: {sel_text}; }}
QFrame#moduleCard {{ background: {bg_panel}; border: 1px solid {grid}; border-radius: {px(12)}px; padding: 14px; }}
QLabel#moduleStatus {{ font-weight: 600; color: {accent}; }}
QLabel#notice {{ background: {bg_panel}; border: 1px solid {grid}; border-radius: {radius_karte}px; padding: 12px; color: {text_dim}; }}
QLabel#errorNotice {{ background: {bg_panel}; border: 1px solid {profile.color('negativ_text', '#e74c3c')}; border-radius: {radius_karte}px; padding: 12px; }}
QPushButton {{ background: {field_bg}; color: {field_text}; border: 1px solid {field_border}; min-height: {px(36)}px; padding: 0 14px; border-radius: {radius_karte}px; }}
QPushButton:hover {{ background: {hover_bg}; color: {hover_text}; }}
QPushButton:disabled {{ color: {text_dim}; }}
QPushButton#primaryButton {{ background: {accent}; color: {profile.color('akzent_text', sel_text)}; border: 1px solid {accent}; font-weight: 700; }}
QComboBox, QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox {{ background: {field_bg}; color: {field_text}; border: 1px solid {field_border}; border-radius: {radius}px; padding: {px(4)}px {px(8)}px; }}
QComboBox QAbstractItemView {{ background: {field_bg}; color: {field_text}; selection-background-color: {profile.color('dropdown_selection', sel_bg)}; selection-color: {profile.color('dropdown_selection_text', sel_text)}; border: 1px solid {field_border}; }}
QCheckBox, QRadioButton {{ color: {text}; background: transparent; }}
QGroupBox {{ border: 1px solid {grid}; border-radius: {radius_karte}px; margin-top: 12px; padding-top: 10px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {text_dim}; }}
QScrollArea {{ border: 0; background: {bg_app}; }}
QTableView, QTreeView, QListView {{ background: {profile.color('tabelle_hintergrund', bg_panel)}; alternate-background-color: {profile.color('tabelle_alt', bg_panel)}; color: {text}; gridline-color: {grid}; selection-background-color: {sel_bg}; selection-color: {sel_text}; }}
QHeaderView::section {{ background: {profile.color('tabelle_header', bg_panel)}; color: {profile.color('tabelle_header_text', text)}; border: 0; border-bottom: 1px solid {grid}; padding: 6px; }}
QProgressBar {{ background: {bg_panel}; border: 1px solid {grid}; border-radius: {radius}px; text-align: center; color: {text}; }}
QProgressBar::chunk {{ background: {accent}; border-radius: {radius}px; }}
QStatusBar {{ background: {bg_panel}; color: {text_dim}; border-top: 1px solid {grid}; }}
""".strip()


def theme_record(profile: ThemeProfile, profile_id: str) -> dict[str, Any]:
    """Profil im Austauschschema ``lifeplanner.theme.v1``."""
    return {
        "schema": SHARED_THEME_SCHEMA,
        "name": profile.name,
        "modus": profile.mode,
        "schriftgroesse": profile.font_size,
        # Farben mitgeben, damit ein Modul das Theme auch darstellen kann,
        # wenn es dieses Profil selbst nicht mitliefert.
        "farben": {
            key: value
            for key, value in profile.data.items()
            if isinstance(value, str) and _HEX_RE.fullmatch(value.strip())
        },
        "gesetzt_von": "lifeplanner",
        "modul_version": APP_VERSION,
        "profil": profile_id,
        "geaendert_am": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _write_atomic(target: Path, record: dict[str, Any]) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    tmp = target.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, target)
    return target


def theme_file(profile_id: str, module_id: str) -> Path:
    """Ablageort des veröffentlichten Profils für ein einzelnes Modul."""
    return profile_dir(profile_id) / "theme" / f"{module_id}.json"


def publish_theme(profile_id: str, module_id: str, profile: ThemeProfile) -> Path:
    """Schreibt das effektive Profil eines Moduls atomar in den Profilordner."""
    return _write_atomic(theme_file(profile_id, module_id), theme_record(profile, profile_id))


def publish_shared_theme(profile_id: str, profile: ThemeProfile) -> Path:
    """Veröffentlicht das gemeinsame Theme im Bridge-Ordner.

    Nur aufrufen, wenn der Nutzer "für alle Module" gewählt hat: ein ungefragt
    geschriebener Eintrag würde die Wahl der anderen Module überschreiben.
    """
    return _write_atomic(
        bridge_dir(profile_id) / SHARED_THEME_FILE, theme_record(profile, profile_id)
    )
