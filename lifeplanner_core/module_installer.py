from __future__ import annotations

import json
import re
import shutil
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from . import APP_VERSION
from .manifest import ManifestError, ModuleManifest
from .paths import data_root
from .plugin_loader import discover_modules
from .updater.io import (
    MAX_COMPONENT_BYTES,
    UpdateIOError,
    ensure_executable,
    secure_extract_zip,
    sha256_file,
    tree_sha256,
)
from .updater.manifest import UpdateComponent, platform_family_key, platform_key
from .updater.service import StagedComponent, UpdateService, UpdateServiceError
from .updater.signing import UpdateSignatureError, verify_manifest_signature

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_EXTENSIONS = {".lpmodule", ".zip"}


class ModuleInstallerError(RuntimeError):
    """Raised when a module package cannot be trusted or installed."""


@dataclass(frozen=True)
class ModulePackageInfo:
    archive_path: Path
    archive_sha256: str
    component_id: str
    name: str
    version: str
    description: str
    requires_host: str
    permissions: tuple[str, ...]
    payload_dir: Path
    payload_sha256: str
    signed: bool
    signature_status: str
    installed_version: str
    action: str
    compatible: bool
    compatibility_reason: str

    @property
    def is_downgrade(self) -> bool:
        if not self.installed_version:
            return False
        try:
            return Version(self.version) < Version(self.installed_version)
        except InvalidVersion:
            return False


class ModuleInstallerService:
    """Inspect and stage local LifePlanner module packages.

    A package is a ZIP-compatible ``.lpmodule`` file containing exactly the
    updater component layout::

        component.json
        component.json.sig      # optional for local development, recommended
        payload/module.json
        payload/...

    Signed packages must include ``payload_sha256`` in ``component.json`` so
    the detached signature binds the complete payload tree.
    """

    def __init__(self, update_service: UpdateService):
        self.update_service = update_service
        self.root = data_root() / "updates" / "module-installer"
        self.inspection_root = self.root / "inspection"
        self.inspection_root.mkdir(parents=True, exist_ok=True)

    def installed_modules(self) -> tuple[ModuleManifest, ...]:
        return discover_modules().modules

    def inspect_package(self, archive_path: Path | str) -> ModulePackageInfo:
        archive = Path(archive_path).expanduser().resolve()
        if not archive.is_file():
            raise ModuleInstallerError(f"Modulpaket fehlt: {archive}")
        if archive.suffix.lower() not in _ALLOWED_EXTENSIONS:
            raise ModuleInstallerError("Erlaubt sind .lpmodule- oder .zip-Dateien.")
        try:
            size = archive.stat().st_size
        except OSError as exc:
            raise ModuleInstallerError(f"Modulpaket kann nicht gelesen werden: {exc}") from exc
        if size <= 0 or size > MAX_COMPONENT_BYTES:
            raise ModuleInstallerError("Modulpaket ist leer oder überschreitet 1 GiB.")

        inspection = self.inspection_root / uuid.uuid4().hex
        try:
            secure_extract_zip(archive, inspection)
            metadata_path = inspection / "component.json"
            payload = inspection / "payload"
            if not metadata_path.is_file() or not payload.is_dir():
                raise ModuleInstallerError("Modulpaket benötigt component.json und payload/.")
            metadata_bytes = metadata_path.read_bytes()
            try:
                metadata = json.loads(metadata_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ModuleInstallerError(f"component.json ist ungültig: {exc}") from exc
            if not isinstance(metadata, dict):
                raise ModuleInstallerError("component.json muss ein JSON-Objekt sein.")
            if str(metadata.get("schema", "")) != "lifeplanner.component.v1":
                raise ModuleInstallerError("Unbekanntes Modulpaket-Schema.")
            if str(metadata.get("kind", "")) != "module":
                raise ModuleInstallerError("Das Paket ist kein LifePlanner-Modul.")

            component_id = str(metadata.get("id", "")).strip()
            version = str(metadata.get("version", "")).strip()
            name = str(metadata.get("name", component_id)).strip() or component_id
            requires_host = str(metadata.get("requires_host", "")).strip()
            platforms = metadata.get("platforms", [])
            if platforms is None:
                platforms = []
            if not isinstance(platforms, list) or not all(isinstance(value, str) for value in platforms):
                raise ModuleInstallerError("platforms muss eine Liste aus Textwerten sein.")
            try:
                Version(version)
            except InvalidVersion as exc:
                raise ModuleInstallerError(f"Ungültige Modulversion: {version!r}") from exc
            if requires_host:
                try:
                    requirement = SpecifierSet(requires_host)
                except InvalidSpecifier as exc:
                    raise ModuleInstallerError(f"Ungültige Core-Anforderung: {requires_host!r}") from exc
            else:
                requirement = SpecifierSet("")

            component = UpdateComponent(
                component_id=component_id,
                name=name,
                version=version,
                kind="module",
                assets={},
                requires_host=requires_host,
                notes=str(metadata.get("notes", "")).strip(),
            )
            try:
                validated_payload = self.update_service._validate_component_archive(inspection, component)
            except (ValueError, ManifestError) as exc:
                raise ModuleInstallerError(str(exc)) from exc
            module_manifest = ModuleManifest.load(validated_payload / "module.json")

            actual_payload_hash = tree_sha256(validated_payload)
            declared_payload_hash = str(metadata.get("payload_sha256", "")).strip().lower()
            if declared_payload_hash:
                if not _SHA256_RE.fullmatch(declared_payload_hash):
                    raise ModuleInstallerError("payload_sha256 ist ungültig.")
                if declared_payload_hash != actual_payload_hash:
                    raise ModuleInstallerError("Payload-Prüfsumme stimmt nicht; Paket wurde verändert.")

            signature_path = inspection / "component.json.sig"
            signed = signature_path.is_file()
            if signed:
                if not declared_payload_hash:
                    raise ModuleInstallerError(
                        "Signiertes Paket ohne payload_sha256 wird abgelehnt, da die Signatur den Inhalt nicht bindet."
                    )
                try:
                    verify_manifest_signature(metadata_bytes, signature_path.read_bytes())
                except (OSError, UpdateSignatureError) as exc:
                    raise ModuleInstallerError(f"Paketsignatur ist ungültig: {exc}") from exc
                signature_status = "Signatur gültig"
            else:
                signature_status = "Nicht signiert – manuelle Vertrauensbestätigung erforderlich"

            compatible = True
            reasons: list[str] = []
            if requires_host and Version(APP_VERSION) not in requirement:
                compatible = False
                reasons.append(f"Benötigt LifePlanner {requires_host}; installiert ist {APP_VERSION}")
            accepted_platforms = {value.strip().lower() for value in platforms if value.strip()}
            if accepted_platforms and not ({platform_key(), platform_family_key()} & accepted_platforms):
                compatible = False
                reasons.append(f"Paket ist nicht für {platform_key()} vorgesehen")

            executable = module_manifest.executable_relative()
            executable_ok = bool(executable and (validated_payload / executable).is_file())
            if executable_ok:
                # Not every published package records the execute bit, and the
                # payload hash covers path, size and content only — so granting
                # it here keeps the module launchable without altering the hash.
                ensure_executable(validated_payload / executable)
            source_ok = bool(module_manifest.source_entry and (validated_payload / module_manifest.source_entry).is_file())
            if getattr(sys, "frozen", False):
                if not executable_ok:
                    compatible = False
                    reasons.append("Der installierte LifePlanner benötigt eine passende gebaute Modulprogrammdatei")
            elif not executable_ok and not source_ok:
                compatible = False
                reasons.append("Weder passende Programmdatei noch Python-Startdatei ist enthalten")

            installed = {module.module_id: module.version for module in self.installed_modules()}
            installed_version = installed.get(component_id, "")
            action = "Installieren" if not installed_version else "Neu installieren"
            if installed_version:
                available = Version(version)
                current = Version(installed_version)
                if available > current:
                    action = "Aktualisieren"
                elif available < current:
                    action = "Downgrade"

            return ModulePackageInfo(
                archive_path=archive,
                archive_sha256=sha256_file(archive),
                component_id=component_id,
                name=module_manifest.name,
                version=version,
                description=module_manifest.description,
                requires_host=requires_host,
                permissions=module_manifest.permissions,
                payload_dir=validated_payload,
                payload_sha256=actual_payload_hash,
                signed=signed,
                signature_status=signature_status,
                installed_version=installed_version,
                action=action,
                compatible=compatible,
                compatibility_reason="; ".join(reasons) if reasons else "Kompatibel",
            )
        except (OSError, UpdateIOError, ModuleInstallerError):
            shutil.rmtree(inspection, ignore_errors=True)
            raise
        except Exception as exc:
            shutil.rmtree(inspection, ignore_errors=True)
            raise ModuleInstallerError(str(exc)) from exc

    def stage_package(self, info: ModulePackageInfo) -> StagedComponent:
        if not info.compatible:
            raise ModuleInstallerError(info.compatibility_reason)
        if not info.payload_dir.is_dir():
            raise ModuleInstallerError("Der geprüfte Paketinhalt ist nicht mehr vorhanden.")
        if tree_sha256(info.payload_dir) != info.payload_sha256:
            raise ModuleInstallerError("Der geprüfte Paketinhalt wurde nachträglich verändert.")
        return StagedComponent(
            component_id=info.component_id,
            name=info.name,
            version=info.version,
            kind="module",
            payload_dir=info.payload_dir.resolve(),
            tree_sha256=info.payload_sha256,
        )

    def write_uninstall_plan(self, module_id: str, *, parent_pid: int) -> Path:
        try:
            return self.update_service.write_remove_plan([module_id], parent_pid=parent_pid)
        except UpdateServiceError as exc:
            raise ModuleInstallerError(str(exc)) from exc
