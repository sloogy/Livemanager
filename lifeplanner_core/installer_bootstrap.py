from __future__ import annotations

import argparse
import configparser
import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests

from . import APP_VERSION
from .github_auth import github_token

from .installer_catalog import (
    InstallerCatalogError,
    load_module_sources,
    query_catalog,
    read_catalog_ini,
    write_catalog_ini,
)
from .module_installer import ModuleInstallerError, ModuleInstallerService
from .plugin_loader import discover_modules
from .updater.apply_plan import apply_plan
from .updater.io import MAX_COMPONENT_BYTES
from .updater.service import UpdateService

_ALLOWED_FINAL_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}


def _write_result(path: Path | None, *, success: bool, message: str, components: list[str] | None = None) -> None:
    if path is None:
        return
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    config["result"] = {
        "success": "1" if success else "0",
        "message": str(message).replace("\r", " ").replace("\n", " ").strip(),
        "components": ",".join(components or []),
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        config.write(handle)
    os.replace(temporary, target)


def _download(url: str, destination: Path, expected_size: int, *, timeout: int = 120) -> Path:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https" or (parsed.hostname or "").lower() != "github.com":
        raise InstallerCatalogError("Moduldownload muss von github.com stammen.")
    if expected_size <= 0 or expected_size > MAX_COMPONENT_BYTES:
        raise InstallerCatalogError("Ungültige Größe des Moduldownloads.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + ".part")
    headers = {"User-Agent": f"LifePlanner-Installer/{APP_VERSION}"}
    token = github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with requests.get(url, headers=headers, timeout=timeout, stream=True, allow_redirects=True) as response:
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
                    if total > expected_size + 1024 or total > MAX_COMPONENT_BYTES:
                        raise InstallerCatalogError("Moduldownload ist größer als von GitHub angegeben.")
                    handle.write(chunk)
        if temp.stat().st_size != expected_size:
            raise InstallerCatalogError(
                f"Moduldownload hat die falsche Größe: erwartet {expected_size}, erhalten {temp.stat().st_size}."
            )
        os.replace(temp, destination)
        return destination
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def command_catalog(args: argparse.Namespace) -> int:
    sources = load_module_sources(args.sources)
    releases = query_catalog(sources, timeout=args.timeout)
    write_catalog_ini(releases, args.output)
    available = sum(1 for item in releases if item.available)
    print(json.dumps({"available": available, "count": len(releases)}, ensure_ascii=False))
    return 0 if available else 4


def command_install(args: argparse.Namespace) -> int:
    app_root = Path(args.app_root).resolve()
    if not app_root.is_dir():
        raise InstallerCatalogError(f"LifePlanner-Zielordner fehlt: {app_root}")
    selected = [value.strip() for value in args.selected.split(",") if value.strip()]
    if not selected:
        raise InstallerCatalogError("Mindestens ein Programm muss ausgewählt sein.")
    releases = {item.module_id: item for item in read_catalog_ini(args.catalog)}
    if len(set(selected)) != len(selected):
        raise InstallerCatalogError("Doppelte Modulauswahl im Installationsauftrag.")
    unknown = [module_id for module_id in selected if module_id not in releases]
    if unknown:
        raise InstallerCatalogError(f"Unbekannte Module: {', '.join(unknown)}")

    os.environ["LIFEPLANNER_APP_DIR"] = str(app_root)
    cache = Path(args.cache).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    update_service = UpdateService(discover_modules())
    installer = ModuleInstallerService(update_service)
    staged = []
    for module_id in selected:
        release = releases[module_id]
        if not release.available:
            raise InstallerCatalogError(f"{release.name} ist nicht verfügbar: {release.error}")
        archive = cache / release.asset_name
        _download(release.asset_url, archive, release.asset_size)
        info = installer.inspect_package(archive)
        # Bleibt stehen, obwohl stage_package seit Loop 34 selbst ablehnt: Der
        # Bootstrap laeuft ohne Nutzer vor sich, und hier soll die Meldung
        # sagen, um welches Modul es geht - nicht nur, dass etwas unsigniert
        # war. Bestaetigen darf er nie.
        if not info.signed:
            raise ModuleInstallerError(f"Remote-Modul {info.name} ist nicht signiert und wird abgelehnt.")
        if info.component_id != module_id:
            raise ModuleInstallerError(f"Paket-ID {info.component_id} passt nicht zur Auswahl {module_id}.")
        if release.version and info.version != release.version:
            raise ModuleInstallerError(
                f"Paketversion {info.version} passt nicht zur GitHub-Version {release.version}."
            )
        staged.append(installer.stage_package(info))

    plan = update_service.write_plan(staged, parent_pid=0)
    result = apply_plan(plan)
    _write_result(
        getattr(args, "result", None),
        success=True,
        message="Ausgewählte Programme wurden erfolgreich installiert.",
        components=selected,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LifePlanner GitHub-Modulbootstrapper")
    sub = parser.add_subparsers(dest="command", required=True)
    catalog = sub.add_parser("catalog", help="GitHub-Repositories abfragen")
    catalog.add_argument("--sources", type=Path, required=True)
    catalog.add_argument("--output", type=Path, required=True)
    catalog.add_argument("--timeout", type=int, default=20)
    catalog.set_defaults(func=command_catalog)

    install = sub.add_parser("install", help="Ausgewählte GitHub-Module installieren")
    install.add_argument("--catalog", type=Path, required=True)
    install.add_argument("--selected", required=True)
    install.add_argument("--app-root", type=Path, required=True)
    install.add_argument("--cache", type=Path, default=Path(tempfile.gettempdir()) / "LifePlannerModuleCache")
    install.add_argument("--result", type=Path, help="INI-Ergebnisdatei für den Windows-Setup-Assistenten")
    install.set_defaults(func=command_install)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (InstallerCatalogError, ModuleInstallerError, OSError, ValueError) as exc:
        _write_result(getattr(args, "result", None), success=False, message=str(exc))
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
