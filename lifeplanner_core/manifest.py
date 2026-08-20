from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from packaging.version import InvalidVersion, Version

_ID_RE = re.compile(r"^[a-z][a-z0-9_.-]{1,63}$")
_ALLOWED_PERMISSIONS = {
    "own_data_read",
    "own_data_write",
    "bridge_read",
    "bridge_write",
    "network_optional",
    "local_ai_optional",
}


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class ModuleManifest:
    module_id: str
    name: str
    version: str
    description: str
    source_entry: str
    windows_executable: str = ""
    linux_executable: str = ""
    permissions: tuple[str, ...] = field(default_factory=tuple)
    environment: dict[str, str] = field(default_factory=dict)
    module_dir: Path = Path(".")

    @classmethod
    def load(cls, path: Path) -> "ModuleManifest":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ManifestError(f"Manifest kann nicht gelesen werden: {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ManifestError(f"Manifest muss ein JSON-Objekt sein: {path}")
        if str(raw.get("schema", "")).strip() != "lifeplanner.module.v1":
            raise ManifestError(f"Unbekanntes Modulmanifest-Schema in {path}")
        module_id = str(raw.get("id", "")).strip()
        if not _ID_RE.fullmatch(module_id):
            raise ManifestError(f"Ungültige Modul-ID in {path}: {module_id!r}")
        version = str(raw.get("version", "")).strip()
        try:
            Version(version)
        except InvalidVersion as exc:
            raise ManifestError(f"Ungültige Modulversion in {path}: {version!r}") from exc
        permissions = tuple(str(p) for p in raw.get("permissions", []))
        unknown = sorted(set(permissions) - _ALLOWED_PERMISSIONS)
        if unknown:
            raise ManifestError(f"Unbekannte Berechtigungen in {path}: {', '.join(unknown)}")
        environment = raw.get("environment", {})
        if not isinstance(environment, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in environment.items()
        ):
            raise ManifestError(f"environment muss string:string enthalten: {path}")
        if any("{bridge_dir}" in value for value in environment.values()) and not (
            {"bridge_read", "bridge_write"} & set(permissions)
        ):
            raise ManifestError(f"Bridge-Umgebung ohne bridge_read/bridge_write in {path}")
        source_entry = cls._safe_relative(str(raw.get("source_entry", "main.py")), "source_entry")
        win_exe = cls._safe_relative(str(raw.get("windows_executable", "")), "windows_executable", allow_empty=True)
        linux_exe = cls._safe_relative(str(raw.get("linux_executable", "")), "linux_executable", allow_empty=True)
        return cls(
            module_id=module_id,
            name=str(raw.get("name", module_id)).strip() or module_id,
            version=version,
            description=str(raw.get("description", "")).strip(),
            source_entry=source_entry,
            windows_executable=win_exe,
            linux_executable=linux_exe,
            permissions=permissions,
            environment=dict(environment),
            module_dir=path.resolve().parent,
        )

    @staticmethod
    def _safe_relative(value: str, field_name: str, allow_empty: bool = False) -> str:
        value = value.strip()
        if allow_empty and not value:
            return ""
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ManifestError(f"{field_name} muss ein sicherer relativer Pfad sein")
        return value

    def executable_relative(self) -> str:
        return self.windows_executable if sys.platform.startswith("win") else self.linux_executable
