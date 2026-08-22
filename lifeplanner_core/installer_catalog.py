from __future__ import annotations

import configparser
import json
import os
import re
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from packaging.version import InvalidVersion, Version

from . import APP_VERSION
from .github_auth import github_token
from .repositories import TRUSTED_MODULE_REPOSITORIES, module_asset_pattern
from .updater.io import MAX_COMPONENT_BYTES

_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_MODULE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_GITHUB_DOWNLOAD_HOSTS = {"github.com"}
_ALLOWED_FINAL_HOSTS = {"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"}


class InstallerCatalogError(RuntimeError):
    """Raised when the installer catalog cannot be queried or trusted."""


@dataclass(frozen=True)
class ModuleSource:
    module_id: str
    name: str
    repository: str
    asset_pattern: str
    description: str = ""
    required_host: str = ">=0.5.0"
    allow_prerelease: bool = False
    minimum_version: str = ""


@dataclass(frozen=True)
class ModuleRelease:
    module_id: str
    name: str
    repository: str
    available: bool
    version: str = ""
    tag: str = ""
    description: str = ""
    asset_name: str = ""
    asset_url: str = ""
    asset_size: int = 0
    error: str = ""


def default_module_sources() -> tuple[ModuleSource, ...]:
    """Return the built-in allow-listed GitHub module repositories for this OS."""
    return tuple(
        ModuleSource(
            module_id=item.module_id,
            name=item.name,
            repository=item.repository,
            asset_pattern=module_asset_pattern(item.module_id),
            description=item.description,
            required_host=">=0.5.0",
            allow_prerelease=False,
            minimum_version=item.minimum_version,
        )
        for item in TRUSTED_MODULE_REPOSITORIES
    )


def download_release_asset(
    release: ModuleRelease,
    destination_dir: Path | str,
    *,
    timeout: int = 120,
) -> Path:
    """Download one allow-listed GitHub release asset with strict size/host checks."""
    if not release.available or not release.asset_url or not release.asset_name:
        raise InstallerCatalogError(f"{release.name} ist nicht als installierbares Modul verfügbar.")
    if release.asset_size <= 0 or release.asset_size > MAX_COMPONENT_BYTES:
        raise InstallerCatalogError("Ungültige Größe des Moduldownloads.")
    _validate_download_url(release.asset_url)
    destination = Path(destination_dir).resolve() / release.asset_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + ".part")
    headers = {
        "Accept": "application/octet-stream",
        "User-Agent": f"LifePlanner/{APP_VERSION}",
    }
    token = github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with requests.get(
            release.asset_url, headers=headers, timeout=timeout, stream=True, allow_redirects=True
        ) as response:
            response.raise_for_status()
            final = urlparse(response.url)
            if final.scheme.lower() != "https" or (final.hostname or "").lower() not in _ALLOWED_FINAL_HOSTS:
                raise InstallerCatalogError("GitHub leitete auf einen nicht erlaubten Downloadhost um.")
            total = 0
            with temp.open("wb") as handle:
                for chunk in response.iter_content(1024 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > release.asset_size + 1024 or total > MAX_COMPONENT_BYTES:
                        raise InstallerCatalogError("Moduldownload ist größer als von GitHub angegeben.")
                    handle.write(chunk)
        actual = temp.stat().st_size
        if actual != release.asset_size:
            raise InstallerCatalogError(
                f"Moduldownload hat die falsche Größe: erwartet {release.asset_size}, erhalten {actual}."
            )
        temp.replace(destination)
        return destination
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def load_module_sources(path: Path | str) -> tuple[ModuleSource, ...]:
    source_path = Path(path)
    try:
        raw = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallerCatalogError(f"Modulquellen konnten nicht gelesen werden: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema") != "lifeplanner.installer-sources.v1":
        raise InstallerCatalogError("Unbekanntes Installer-Quellenformat.")
    modules = raw.get("modules")
    if not isinstance(modules, list) or not modules:
        raise InstallerCatalogError("Der Installer enthält keine Modulquellen.")
    result: list[ModuleSource] = []
    seen: set[str] = set()
    for index, item in enumerate(modules):
        if not isinstance(item, dict):
            raise InstallerCatalogError(f"Modulquelle {index + 1} ist ungültig.")
        module_id = str(item.get("id", "")).strip()
        name = str(item.get("name", module_id)).strip() or module_id
        repository = str(item.get("repository", "")).strip()
        asset_pattern = str(item.get("asset_pattern", "")).strip()
        if not _MODULE_ID_RE.fullmatch(module_id):
            raise InstallerCatalogError(f"Ungültige Modul-ID: {module_id!r}")
        if module_id in seen:
            raise InstallerCatalogError(f"Doppelte Modul-ID: {module_id}")
        if not _REPOSITORY_RE.fullmatch(repository):
            raise InstallerCatalogError(f"Ungültiges GitHub-Repository für {name}: {repository!r}")
        try:
            re.compile(asset_pattern)
        except re.error as exc:
            raise InstallerCatalogError(f"Ungültiges Asset-Muster für {name}: {exc}") from exc
        seen.add(module_id)
        result.append(
            ModuleSource(
                module_id=module_id,
                name=name,
                repository=repository,
                asset_pattern=asset_pattern,
                description=str(item.get("description", "")).strip(),
                required_host=str(item.get("requires_host", ">=0.5.0")).strip() or ">=0.5.0",
                allow_prerelease=bool(item.get("allow_prerelease", False)),
            )
        )
    return tuple(result)


def _meets_minimum_version(version: str, minimum: str) -> bool:
    if not minimum:
        return True
    try:
        return Version(version) >= Version(minimum)
    except InvalidVersion:
        # Ohne verwertbare Version lieber nichts anbieten als eine zu alte.
        return False


def _safe_description(value: Any, fallback: str) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return (text[:400] if text else fallback) or "LifePlanner-Modul"


def _validate_download_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme.lower() != "https" or host not in _GITHUB_DOWNLOAD_HOSTS:
        raise InstallerCatalogError("GitHub-Asset verwendet keine erlaubte HTTPS-Adresse.")
    return url


def query_module_release(
    source: ModuleSource,
    *,
    session: requests.Session | None = None,
    timeout: int = 20,
) -> ModuleRelease:
    owns_session = session is None
    client = session or requests.Session()
    url = f"https://api.github.com/repos/{source.repository}/releases?per_page=20"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"LifePlanner-Installer/{APP_VERSION}",
    }
    token = github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        try:
            response = client.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            releases = response.json()
        except (requests.RequestException, ValueError) as exc:
            return ModuleRelease(
                module_id=source.module_id,
                name=source.name,
                repository=source.repository,
                available=False,
                description=source.description,
                error=f"Repository nicht erreichbar: {exc}",
            )
    finally:
        if owns_session:
            client.close()
    if not isinstance(releases, list):
        return ModuleRelease(
            module_id=source.module_id,
            name=source.name,
            repository=source.repository,
            available=False,
            description=source.description,
            error="GitHub lieferte kein gültiges Release-Array.",
        )
    pattern = re.compile(source.asset_pattern, re.IGNORECASE)
    for release in releases:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        if release.get("prerelease") and not source.allow_prerelease:
            continue
        assets = release.get("assets")
        if not isinstance(assets, list):
            continue
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            asset_name = str(asset.get("name", "")).strip()
            match = pattern.fullmatch(asset_name)
            if not match:
                continue
            try:
                asset_size = int(asset.get("size", 0))
            except (TypeError, ValueError):
                asset_size = 0
            if asset_size <= 0 or asset_size > MAX_COMPONENT_BYTES:
                continue
            try:
                asset_url = _validate_download_url(str(asset.get("browser_download_url", "")).strip())
            except InstallerCatalogError:
                continue
            groups = match.groupdict()
            version = str(groups.get("version") or "").strip()
            if not version:
                version = str(release.get("tag_name", "")).strip().lstrip("vV")
            if not _meets_minimum_version(version, source.minimum_version):
                continue
            return ModuleRelease(
                module_id=source.module_id,
                name=source.name,
                repository=source.repository,
                available=True,
                version=version,
                tag=str(release.get("tag_name", "")).strip(),
                description=_safe_description(release.get("body"), source.description),
                asset_name=asset_name,
                asset_url=asset_url,
                asset_size=asset_size,
            )
    return ModuleRelease(
        module_id=source.module_id,
        name=source.name,
        repository=source.repository,
        available=False,
        description=source.description,
        error="Kein passendes freigegebenes .lpmodule in den letzten 20 Releases gefunden.",
    )


def query_catalog(sources: Iterable[ModuleSource], *, timeout: int = 20) -> tuple[ModuleRelease, ...]:
    items = tuple(sources)
    if not items:
        return ()
    # Die Repositories werden parallel abgefragt, damit der Windows-Assistent
    # auch bei später vielen Modulen nicht pro Repository nacheinander wartet.
    workers = min(4, len(items))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="module-catalog") as executor:
        return tuple(executor.map(lambda source: query_module_release(source, timeout=timeout), items))


def write_catalog_ini(releases: Iterable[ModuleRelease], destination: Path | str) -> Path:
    items = tuple(releases)
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    config["catalog"] = {
        "schema": "lifeplanner.installer-catalog.v1",
        "count": str(len(items)),
        "available": str(sum(1 for item in items if item.available)),
    }
    for index, item in enumerate(items):
        config[f"module{index}"] = {
            "id": item.module_id,
            "name": item.name,
            "repository": item.repository,
            "available": "1" if item.available else "0",
            "version": item.version,
            "tag": item.tag,
            "description": item.description,
            "asset_name": item.asset_name,
            "asset_url": item.asset_url,
            "asset_size": str(item.asset_size),
            "error": item.error,
        }
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        config.write(handle)
    os.replace(temp, target)
    return target


def read_catalog_ini(path: Path | str) -> tuple[ModuleRelease, ...]:
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    if not config.read(Path(path), encoding="utf-8"):
        raise InstallerCatalogError("Installer-Katalog fehlt.")
    if config.get("catalog", "schema", fallback="") != "lifeplanner.installer-catalog.v1":
        raise InstallerCatalogError("Unbekanntes Installer-Katalogformat.")
    count = config.getint("catalog", "count", fallback=0)
    result: list[ModuleRelease] = []
    for index in range(count):
        section = f"module{index}"
        if not config.has_section(section):
            raise InstallerCatalogError(f"Katalogabschnitt fehlt: {section}")
        result.append(
            ModuleRelease(
                module_id=config.get(section, "id", fallback=""),
                name=config.get(section, "name", fallback=""),
                repository=config.get(section, "repository", fallback=""),
                available=config.getboolean(section, "available", fallback=False),
                version=config.get(section, "version", fallback=""),
                tag=config.get(section, "tag", fallback=""),
                description=config.get(section, "description", fallback=""),
                asset_name=config.get(section, "asset_name", fallback=""),
                asset_url=config.get(section, "asset_url", fallback=""),
                asset_size=config.getint(section, "asset_size", fallback=0),
                error=config.get(section, "error", fallback=""),
            )
        )
    return tuple(result)
