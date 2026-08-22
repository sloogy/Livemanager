from __future__ import annotations

import json
import logging
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

from .paths import config_dir
from .repositories import CORE_LATEST_MANIFEST_URL
from .zeitmarke import dateimarke

# Auslieferungszustand einer neuen Installation. Bewusst getrennt von den
# Rückfallprofilen: ein frisch installierter LifePlanner soll nicht nach
# Rückfall aussehen.
INITIAL_LIGHT_THEME = "V2 Hell – Neon Cyan"
INITIAL_DARK_THEME = "V2 Dunkel – Graphite Cyan"

_log = logging.getLogger(__name__)

_DEFAULTS: dict[str, Any] = {
    "schema": 1,
    "active_profile": "default",
    # Sprache der Host-Oberflaeche. Die Module bringen ihre eigene mit; der
    # Host reicht sie nicht durch, weil jedes Programm sie selbst speichert.
    "language": "de",
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
        # Die gespeicherte Sprache gilt ab dem Start, nicht erst nachdem
        # jemand die Darstellungsseite geoeffnet hat.
        from .i18n import setze_sprache

        setze_sprache(self.language)

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
                except (OSError, json.JSONDecodeError) as fehler:
                    self._beiseitelegen(fehler)
                    self._data = deepcopy(_DEFAULTS)
                else:
                    if isinstance(raw, dict):
                        self._data = self._merge(deepcopy(_DEFAULTS), raw)
                    else:
                        # Gültiges JSON, aber kein Objekt - eine Liste oder eine
                        # nackte Zahl. Genauso unbrauchbar wie kaputtes JSON.
                        self._beiseitelegen(
                            ValueError(f"Kein JSON-Objekt: {type(raw).__name__}")
                        )
                        self._data = deepcopy(_DEFAULTS)
            return deepcopy(self._data)

    def _beiseitelegen(self, grund: Exception) -> None:
        """Rettet eine unlesbare Einstellungsdatei, statt sie zu überschreiben.

        Ohne das war sie beim nächsten ``save()`` endgültig weg - samt allem,
        was darin stand. Oft ist nur ein Zeichen falsch und die Datei ließe
        sich von Hand retten; dafür muss sie aber noch da sein.
        """
        marke = dateimarke()
        ziel = self.path.with_name(f"{self.path.name}.kaputt-{marke}")
        # Zwei Fehlschlaege in derselben Sekunde bekamen denselben
        # Namen; der zweite ueberschrieb den ersten und die
        # urspruengliche Fassung war weg.
        zaehler = 1
        while ziel.exists():
            ziel = self.path.with_name(
                f"{self.path.name}.kaputt-{marke}-{zaehler}"
            )
            zaehler += 1
        try:
            self.path.replace(ziel)
        except OSError as fehler:
            _log.warning("Beschädigte %s ließ sich nicht sichern: %s",
                         self.path.name, fehler)
            return
        _log.warning("%s war unlesbar (%s) - beiseitegelegt als %s, "
                     "es gelten die Standardwerte",
                     self.path.name, grund, ziel.name)
        self._kaputte_ausduennen()

    def _kaputte_ausduennen(self, behalten: int = 10) -> None:
        """Haelt die beiseitegelegten Fassungen in Grenzen.

        Ohne das entsteht bei jedem Start eine weitere Datei, solange
        die Einstellungen kaputt bleiben - und niemand raeumt sie je auf.
        """
        pfad = self.path
        try:
            staende = sorted(
                pfad.parent.glob(f"{pfad.name}.kaputt-*"),
                key=lambda q: q.stat().st_mtime,
                reverse=True,
            )
        except OSError as fehler:
            _log.debug("Beiseitegelegte Fassungen nicht auflistbar: %s", fehler)
            return
        for veraltet in staende[behalten:]:
            try:
                veraltet.unlink()
            except OSError as fehler:
                _log.debug("%s bleibt liegen: %s", veraltet.name, fehler)


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
            from .atomic_write import atomar_schreiben

            # Seit Loop 27 der gemeinsame Helfer. Er traegt den fsync auf das
            # Verzeichnis nach - ohne den ueberlebt der Inhalt einen
            # Stromausfall, aber nicht der Eintrag, der auf ihn zeigt - und
            # gibt der Zwischendatei die Prozessnummer, damit zwei Instanzen
            # sich nicht dieselbe teilen.
            atomar_schreiben(
                self.path,
                json.dumps(self._data, ensure_ascii=False, indent=2, sort_keys=True),
            )

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
    def language(self) -> str:
        from .i18n import SPRACHEN, STANDARD

        wert = str(self.get("language", STANDARD) or STANDARD)
        return wert if wert in SPRACHEN else STANDARD

    def set_language(self, sprache: str) -> None:
        """Speichert die Sprache und stellt sie sofort um."""
        from .i18n import SPRACHEN, STANDARD, setze_sprache

        gewaehlt = sprache if sprache in SPRACHEN else STANDARD
        self.set("language", gewaehlt)
        setze_sprache(gewaehlt)

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
