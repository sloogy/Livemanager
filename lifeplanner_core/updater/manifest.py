from __future__ import annotations

import platform
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

_COMPONENT_ID_RE = re.compile(r"^[a-z][a-z0-9_.-]{1,63}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_KINDS = {"core", "module"}
_ALLOWED_CHANNELS = {"stable", "beta"}
_ALLOWED_ASSET_TYPES = {"component-zip"}


class UpdateManifestError(ValueError):
    pass


@dataclass(frozen=True)
class UpdateAsset:
    url: str
    sha256: str
    size: int
    asset_type: str = "component-zip"


@dataclass(frozen=True)
class UpdateComponent:
    component_id: str
    name: str
    version: str
    kind: str
    assets: Mapping[str, UpdateAsset]
    requires_host: str = ""
    notes: str = ""

    def asset_for_current_platform(self) -> UpdateAsset | None:
        key = platform_key()
        return self.assets.get(key) or self.assets.get(platform_family_key())


@dataclass(frozen=True)
class UpdateManifest:
    schema: str
    channel: str
    generated_at: str
    components: Mapping[str, UpdateComponent]


@dataclass(frozen=True)
class ComponentStatus:
    component_id: str
    name: str
    kind: str
    installed: bool
    installed_version: str
    available_version: str
    update_available: bool
    compatible: bool
    reason: str
    component: UpdateComponent


def platform_family_key() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "macos"
    return sys.platform


def platform_key() -> str:
    machine = platform.machine().lower().replace("amd64", "x86_64")
    if machine in {"x64", "x86-64"}:
        machine = "x86_64"
    return f"{platform_family_key()}-{machine}"


def _version(value: str, *, label: str) -> Version:
    try:
        return Version(str(value).strip())
    except InvalidVersion as exc:
        raise UpdateManifestError(f"Ungültige Version für {label}: {value!r}") from exc


def _safe_specifier(value: str, *, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        SpecifierSet(text)
    except InvalidSpecifier as exc:
        raise UpdateManifestError(f"Ungültige Versionsanforderung für {label}: {text!r}") from exc
    return text


def parse_manifest(raw: Any) -> UpdateManifest:
    if not isinstance(raw, dict):
        raise UpdateManifestError("Update-Manifest muss ein JSON-Objekt sein")
    schema = str(raw.get("schema", "")).strip()
    if schema != "lifeplanner.update.v1":
        raise UpdateManifestError(f"Unbekanntes Update-Schema: {schema!r}")
    channel = str(raw.get("channel", "stable")).strip().lower()
    if channel not in _ALLOWED_CHANNELS:
        raise UpdateManifestError(f"Unbekannter Update-Kanal: {channel!r}")
    generated_at = str(raw.get("generated_at", "")).strip()
    components_raw = raw.get("components")
    if not isinstance(components_raw, dict) or not components_raw:
        raise UpdateManifestError("Update-Manifest enthält keine Komponenten")

    components: dict[str, UpdateComponent] = {}
    for key, value in components_raw.items():
        if not isinstance(value, dict):
            raise UpdateManifestError(f"Komponente {key!r} ist kein Objekt")
        component_id = str(value.get("id", key)).strip()
        if component_id != str(key):
            raise UpdateManifestError(f"Komponenten-ID stimmt nicht mit dem Schlüssel überein: {key!r}")
        if not _COMPONENT_ID_RE.fullmatch(component_id):
            raise UpdateManifestError(f"Ungültige Komponenten-ID: {component_id!r}")
        kind = str(value.get("kind", "module")).strip().lower()
        if kind not in _ALLOWED_KINDS:
            raise UpdateManifestError(f"Ungültiger Komponententyp für {component_id}: {kind!r}")
        version = str(value.get("version", "")).strip()
        _version(version, label=component_id)
        requires_host = _safe_specifier(value.get("requires_host", ""), label=component_id)
        assets_raw = value.get("assets")
        if not isinstance(assets_raw, dict) or not assets_raw:
            raise UpdateManifestError(f"Komponente {component_id} enthält keine Assets")
        assets: dict[str, UpdateAsset] = {}
        for asset_key, asset_raw in assets_raw.items():
            if not isinstance(asset_raw, dict):
                raise UpdateManifestError(f"Asset {component_id}/{asset_key} ist kein Objekt")
            url = str(asset_raw.get("url", "")).strip()
            sha256 = str(asset_raw.get("sha256", "")).strip().lower()
            asset_type = str(asset_raw.get("type", "component-zip")).strip().lower()
            try:
                size = int(asset_raw.get("size", 0))
            except (TypeError, ValueError) as exc:
                raise UpdateManifestError(f"Ungültige Asset-Größe für {component_id}/{asset_key}") from exc
            if not url:
                raise UpdateManifestError(f"Asset-URL fehlt für {component_id}/{asset_key}")
            if not _SHA256_RE.fullmatch(sha256):
                raise UpdateManifestError(f"Ungültiger SHA-256 für {component_id}/{asset_key}")
            if size <= 0:
                raise UpdateManifestError(f"Asset-Größe fehlt für {component_id}/{asset_key}")
            if asset_type not in _ALLOWED_ASSET_TYPES:
                raise UpdateManifestError(f"Nicht erlaubter Asset-Typ für {component_id}/{asset_key}: {asset_type}")
            assets[str(asset_key)] = UpdateAsset(url=url, sha256=sha256, size=size, asset_type=asset_type)
        components[component_id] = UpdateComponent(
            component_id=component_id,
            name=str(value.get("name", component_id)).strip() or component_id,
            version=version,
            kind=kind,
            assets=assets,
            requires_host=requires_host,
            notes=str(value.get("notes", "")).strip(),
        )
    core = components.get("lifeplanner.core")
    if core and core.kind != "core":
        raise UpdateManifestError("lifeplanner.core muss den Typ core besitzen")
    return UpdateManifest(
        schema=schema,
        channel=channel,
        generated_at=generated_at,
        components=components,
    )


def compare_manifest(
    manifest: UpdateManifest,
    installed_versions: Mapping[str, str],
    *,
    host_version: str,
) -> tuple[ComponentStatus, ...]:
    installed_host = _version(host_version, label="installierter LifePlanner-Core")
    remote_core = manifest.components.get("lifeplanner.core")
    effective_host = installed_host
    if remote_core and remote_core.asset_for_current_platform() is not None:
        try:
            remote_host_version = _version(remote_core.version, label="LifePlanner-Core")
            if remote_host_version > installed_host:
                effective_host = remote_host_version
        except UpdateManifestError:
            pass

    statuses: list[ComponentStatus] = []
    for component_id, component in sorted(manifest.components.items(), key=lambda item: (item[1].kind != "core", item[1].name.lower())):
        is_installed = component_id in installed_versions
        installed_text = str(installed_versions.get(component_id, "0.0.0"))
        installed = _version(installed_text, label=f"installierte Version {component_id}")
        available = _version(component.version, label=component_id)
        update_available = available > installed
        compatible = True
        reason = "Aktuell"
        if component.asset_for_current_platform() is None:
            compatible = False
            reason = f"Kein Asset für {platform_key()}"
        elif component.requires_host:
            requirement = SpecifierSet(component.requires_host)
            if effective_host not in requirement:
                compatible = False
                reason = f"Benötigt LifePlanner {component.requires_host}"
        if update_available and compatible:
            reason = "Update verfügbar" if is_installed else "Zur Installation verfügbar"
        elif available < installed:
            reason = "Installierte Version ist neuer"
        statuses.append(
            ComponentStatus(
                component_id=component_id,
                name=component.name,
                kind=component.kind,
                installed=is_installed,
                installed_version=installed_text if is_installed else "–",
                available_version=component.version,
                update_available=update_available,
                compatible=compatible,
                reason=reason,
                component=component,
            )
        )
    return tuple(statuses)
