from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

from .paths import config_dir
from .repositories import CORE_LATEST_MANIFEST_URL

_DEFAULTS: dict[str, Any] = {
    "schema": 1,
    "active_profile": "default",
    "theme": "system",
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
        self.load()

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
