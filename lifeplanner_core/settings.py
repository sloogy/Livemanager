from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

from .paths import config_dir
from .repositories import CORE_LATEST_MANIFEST_URL

# Auslieferungszustand einer neuen Installation. Bewusst getrennt von den
# Rückfallprofilen: ein frisch installierter LifePlanner soll nicht nach
# Rückfall aussehen.
INITIAL_LIGHT_THEME = "V2 Hell – Neon Cyan"
INITIAL_DARK_THEME = "V2 Dunkel – Graphite Cyan"

_DEFAULTS: dict[str, Any] = {
    "schema": 1,
    "active_profile": "default",
    "theme": "system",
    # Welche Profile "system" bedeutet. Für bestehende Konfigurationen bleibt
    # es beim Standardpaar - ein Update soll niemandem die Farben umstellen.
    # Eine neu angelegte settings.json bekommt stattdessen das Auslieferungspaar
    # (siehe _apply_initial_theme).
    "system_theme_light": "Standard - Hell",
    "system_theme_dark": "Standard - Dunkel",
    # Ein Häkchen im Darstellungsbereich hält Host und alle Module auf
    # demselben Profil; ausgeschaltet zählt der Eintrag in module_themes.
    "theme_apply_to_all": True,
    "module_themes": {},
    "language": "de",
    "ollama": {"enabled": False, "endpoint": "http://127.0.0.1:11434", "model": ""},
    "updates": {"manifest_url": CORE_LATEST_MANIFEST_URL, "auto_check": False, "channel": "stable"},
    "permissions": {},
}


class SettingsStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (config_dir() / "settings.json")
        self._lock = threading.RLock()
        self._data = deepcopy(_DEFAULTS)
        existed = self.path.is_file()
        self.load()
        if not existed:
            self._apply_initial_theme()

    def _apply_initial_theme(self) -> None:
        """Auslieferungspaar einer neuen Installation einmalig festhalten.

        Nur wenn es noch keine settings.json gab: Wer LifePlanner schon nutzt,
        behält sein Erscheinungsbild, auch wenn er nie eines gewählt hat.
        """
        with self._lock:
            self._data["system_theme_light"] = INITIAL_LIGHT_THEME
            self._data["system_theme_dark"] = INITIAL_DARK_THEME
        self.save()

    def load(self) -> dict[str, Any]:
        with self._lock:
            if self.path.is_file():
                try:
                    raw = json.loads(self.path.read_text(encoding="utf-8"))
                    if isinstance(raw, dict):
                        self._data = self._merge(deepcopy(_DEFAULTS), raw)
                except (OSError, json.JSONDecodeError):
                    self._data = deepcopy(_DEFAULTS)
            return deepcopy(self._data)

    @staticmethod
    def _merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
        for key, value in incoming.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                base[key] = SettingsStore._merge(base[key], value)
            else:
                base[key] = value
        return base

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            payload = json.dumps(self._data, ensure_ascii=False, indent=2, sort_keys=True)
            with tmp.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return deepcopy(self._data.get(key, default))

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = deepcopy(value)
            self.save()

    @property
    def active_profile(self) -> str:
        return str(self.get("active_profile", "default"))

    @property
    def system_theme_pair(self) -> tuple[str, str]:
        """Die beiden Profile, die "system" bei hell und dunkel bedeutet."""
        light = str(self.get("system_theme_light", "") or "").strip()
        dark = str(self.get("system_theme_dark", "") or "").strip()
        return light or "Standard - Hell", dark or "Standard - Dunkel"

    def set_system_theme_pair(self, light: str, dark: str) -> None:
        self.set("system_theme_light", str(light or "").strip() or "Standard - Hell")
        self.set("system_theme_dark", str(dark or "").strip() or "Standard - Dunkel")

    @property
    def theme(self) -> str:
        return str(self.get("theme", "system") or "system")

    @property
    def theme_applies_to_all(self) -> bool:
        return bool(self.get("theme_apply_to_all", True))

    def theme_for(self, module_id: str) -> str:
        """Profilname für ein Modul unter Berücksichtigung des Häkchens."""
        if self.theme_applies_to_all:
            return self.theme
        overrides = self.get("module_themes", {})
        if isinstance(overrides, dict):
            value = str(overrides.get(module_id, "") or "").strip()
            if value:
                return value
        return self.theme

    def set_module_theme(self, module_id: str, name: str) -> None:
        overrides = self.get("module_themes", {})
        if not isinstance(overrides, dict):
            overrides = {}
        value = str(name or "").strip()
        if value:
            overrides[module_id] = value
        else:
            overrides.pop(module_id, None)
        self.set("module_themes", overrides)
