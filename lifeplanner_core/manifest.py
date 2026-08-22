from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from packaging.specifiers import InvalidSpecifier, SpecifierSet
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
_ALLOWED_SCHEMAS = {"lifeplanner.module.v1", "lifeplanner.module.v2"}


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class BridgeContract:
    """Deklarierter Datei-Vertrag eines Moduls im gemeinsamen Bridge-Ordner."""

    name: str
    filename: str
    schemas: tuple[str, ...]
    direction: str


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
    requires_host: str = ""
    bridge_contracts: tuple[BridgeContract, ...] = field(default_factory=tuple)
    schema: str = "lifeplanner.module.v1"
    module_dir: Path = Path(".")

    @classmethod
    def load(cls, path: Path) -> "ModuleManifest":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ManifestError(f"Manifest kann nicht gelesen werden: {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ManifestError(f"Manifest muss ein JSON-Objekt sein: {path}")

        schema = str(raw.get("schema", "")).strip()
        if schema not in _ALLOWED_SCHEMAS:
            raise ManifestError(f"Unbekanntes Modulmanifest-Schema in {path}: {schema!r}")

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

        requires_host = str(raw.get("requires_host", "")).strip()
        if schema == "lifeplanner.module.v2" and not requires_host:
            raise ManifestError(f"Modulmanifest v2 benötigt requires_host: {path}")
        if requires_host:
            try:
                SpecifierSet(requires_host)
            except InvalidSpecifier as exc:
                raise ManifestError(
                    f"Ungültige LifePlanner-Anforderung in {path}: {requires_host!r}"
                ) from exc

        source_entry = cls._safe_relative(
            str(raw.get("source_entry", "main.py")), "source_entry"
        )
        win_exe = cls._safe_relative(
            str(raw.get("windows_executable", "")),
            "windows_executable",
            allow_empty=True,
        )
        linux_exe = cls._safe_relative(
            str(raw.get("linux_executable", "")),
            "linux_executable",
            allow_empty=True,
        )
        bridge_contracts = cls._parse_bridge_contracts(raw.get("bridge"), path)

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
            requires_host=requires_host,
            bridge_contracts=bridge_contracts,
            schema=schema,
            module_dir=path.resolve().parent,
        )

    @classmethod
    def _parse_bridge_contracts(
        cls, value: object, path: Path
    ) -> tuple[BridgeContract, ...]:
        if value is None:
            return ()
        if not isinstance(value, dict):
            raise ManifestError(f"bridge muss ein JSON-Objekt sein: {path}")

        contracts: list[BridgeContract] = []
        for section, direction in (("publishes", "publish"), ("subscribes", "subscribe")):
            entries = value.get(section, [])
            if not isinstance(entries, list):
                raise ManifestError(f"bridge.{section} muss eine Liste sein: {path}")
            for index, entry in enumerate(entries, start=1):
                if not isinstance(entry, dict):
                    raise ManifestError(
                        f"bridge.{section}[{index}] muss ein Objekt sein: {path}"
                    )
                filename = cls._safe_relative(
                    str(entry.get("file", "")), f"bridge.{section}[{index}].file"
                )
                schemas = entry.get("schemas", [])
                if not isinstance(schemas, list) or not schemas or not all(
                    isinstance(item, str) and item.strip() for item in schemas
                ):
                    raise ManifestError(
                        f"bridge.{section}[{index}].schemas benötigt Textwerte: {path}"
                    )
                name = str(entry.get("name", "")).strip() or filename
                contracts.append(
                    BridgeContract(
                        name=name,
                        filename=filename,
                        schemas=tuple(item.strip() for item in schemas),
                        direction=direction,
                    )
                )
        return tuple(contracts)

    @staticmethod
    def _safe_relative(value: str, field_name: str, allow_empty: bool = False) -> str:
        value = value.strip()
        if allow_empty and not value:
            return ""
        if not value:
            raise ManifestError(f"{field_name} darf nicht leer sein")
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ManifestError(f"{field_name} muss ein sicherer relativer Pfad sein")
        return value

    def executable_relative(self) -> str:
        return self.windows_executable if sys.platform.startswith("win") else self.linux_executable

    def host_compatible(self, host_version: str) -> bool:
        """Prüft die persistente Host-Anforderung auch nach der Installation."""
        if not self.requires_host:
            return True
        try:
            return Version(host_version) in SpecifierSet(self.requires_host)
        except (InvalidVersion, InvalidSpecifier):
            return False

    def host_compatibility_reason(self, host_version: str) -> str:
        if self.host_compatible(host_version):
            return "Kompatibel"
        requirement = self.requires_host or "nicht angegeben"
        return f"Benötigt LifePlanner {requirement}; installiert ist {host_version}"
