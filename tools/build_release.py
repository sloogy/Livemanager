from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.module_sources import (
    ModuleSourceError,
    ResolvedModuleSource,
    load_lock,
    resolve_module_sources,
)
from tools.release_signing import ReleaseSigning, resolve_release_signing

DIST = ROOT / "dist"
BUILD = ROOT / "build"
RELEASE = ROOT / "release"
APP_VERSION = "0.5.6"


def run(*args: str, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(args))
    subprocess.run(args, cwd=cwd, check=True, env=env)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _zip_component(
    *,
    payload: Path,
    component_id: str,
    name: str,
    version: str,
    kind: str,
    output: Path,
    requires_host: str = "",
    description: str = "",
    platforms: tuple[str, ...] = (),
    private_key_b64: str,
) -> Path:
    from lifeplanner_core.updater.package_builder import build_component_package

    return build_component_package(
        payload=payload,
        component_id=component_id,
        name=name,
        version=version,
        kind=kind,
        output=output,
        requires_host=requires_host,
        description=description,
        platforms=platforms,
        private_key_b64=private_key_b64,
    )


def _module_info(module_dir: Path) -> dict:
    return json.loads((module_dir / "module.json").read_text(encoding="utf-8"))


def _build_update_assets(shell: Path, *, signing: ReleaseSigning) -> None:
    update_dir = RELEASE / "update-assets"
    update_dir.mkdir(parents=True, exist_ok=True)
    platform_key = "windows-x86_64"

    core_payload = RELEASE / ".core-payload"
    shutil.rmtree(core_payload, ignore_errors=True)
    core_payload.mkdir(parents=True)
    for item in shell.iterdir():
        if item.name in {"modules", "portable.flag", "installation.json"}:
            continue
        target = core_payload / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)

    components: list[tuple[str, str, str, str, Path, str, str, str]] = []
    core_name = f"LifePlanner_Core_{APP_VERSION}_Windows_x86_64.zip"
    components.append(
        (
            "lifeplanner.core",
            "LifePlanner Core",
            APP_VERSION,
            "core",
            core_payload,
            core_name,
            "",
            "LifePlanner Plattform-Core",
        )
    )
    module_root = shell / "modules"
    for module_path in sorted(
        path for path in module_root.iterdir() if path.is_dir() and (path / "module.json").is_file()
    ):
        info = _module_info(module_path)
        module_id = str(info["id"])
        safe_id = "".join(char if char.isalnum() or char in "-_" else "_" for char in module_id)
        filename = f"{safe_id}_{info['version']}_Windows_x86_64.lpmodule"
        components.append(
            (
                module_id,
                str(info["name"]),
                str(info["version"]),
                "module",
                module_path,
                filename,
                ">=0.5.0",
                str(info.get("description", "")),
            )
        )

    base_url = os.environ.get("LIFEPLANNER_RELEASE_BASE_URL", "").strip().rstrip("/")
    if not base_url:
        repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
        tag = os.environ.get("GITHUB_REF_NAME", "").strip()
        if repository and tag:
            base_url = f"https://github.com/{repository}/releases/download/{tag}"
    if not base_url:
        base_url = "https://example.invalid/lifeplanner-release"
        print("WARNUNG: LIFEPLANNER_RELEASE_BASE_URL fehlt; Manifest enthält example.invalid.")

    manifest_components: dict[str, dict] = {}
    for component_id, name, version, kind, payload, filename, requires_host, description in components:
        output = _zip_component(
            payload=payload,
            component_id=component_id,
            name=name,
            version=version,
            kind=kind,
            output=update_dir / filename,
            requires_host=requires_host,
            description=description,
            platforms=(platform_key,),
            private_key_b64=signing.private_key_b64,
        )
        manifest_components[component_id] = {
            "id": component_id,
            "name": name,
            "version": version,
            "kind": kind,
            "requires_host": requires_host,
            "description": description,
            "assets": {
                platform_key: {
                    "url": f"{base_url}/{filename}",
                    "sha256": sha256(output),
                    "size": output.stat().st_size,
                    "type": "component-zip",
                }
            },
        }

    manifest = {
        "schema": "lifeplanner.update.v1",
        "channel": "stable",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "components": manifest_components,
    }
    manifest_path = update_dir / "lifeplanner-latest.json"
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    manifest_path.write_bytes(manifest_bytes)

    if signing.private_key_b64:
        from lifeplanner_core.updater.signing import sign_manifest

        (update_dir / "lifeplanner-latest.json.sig").write_bytes(
            sign_manifest(manifest_bytes, signing.private_key_b64)
        )
    else:
        print("WARNUNG: --allow-unsigned aktiv; Pakete und Update-Manifest bleiben unsigniert.")
    shutil.rmtree(core_payload, ignore_errors=True)


def _repository_variables() -> dict[str, str]:
    return {spec.module_id: spec.repository_variable for spec in load_lock()}


def _repository_slug(module_id: str, default_repository: str) -> str:
    owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "").strip()
    variable = _repository_variables().get(module_id, "")
    configured = os.environ.get(variable, "").strip() if variable else ""
    if configured:
        return configured
    # A fully-qualified repository in modules.lock.json is the canonical default.
    # This makes installer/update discovery independent of the owner of the
    # LifePlanner repository while still allowing CI overrides via env vars.
    if "/" in default_repository:
        return default_repository
    if owner:
        return f"{owner}/{default_repository}"
    raise RuntimeError(
        f"GitHub-Repository für {module_id} fehlt. Setze {variable or 'eine Repository-Variable'} "
        "oder GITHUB_REPOSITORY_OWNER."
    )


def _write_installer_sources(installer_source: Path) -> None:
    lock = json.loads((ROOT / "dependencies" / "modules.lock.json").read_text(encoding="utf-8"))
    modules = []
    for item in lock.get("modules", []):
        module_id = str(item["id"])
        version_pattern = r"(?P<version>[0-9][0-9A-Za-z._-]*)"
        safe_id = "".join(char if char.isalnum() or char in "-_" else "_" for char in module_id)
        modules.append(
            {
                "id": module_id,
                "name": str(item["name"]),
                "repository": _repository_slug(module_id, str(item["default_repository"])),
                "asset_pattern": rf"{safe_id}_{version_pattern}_Windows_x86_64\.lpmodule",
                "description": str(item.get("description", "")),
                "requires_host": ">=0.5.0",
            }
        )
    payload = {
        "schema": "lifeplanner.installer-sources.v1",
        "generated_for": APP_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "modules": modules,
    }
    (installer_source / "installer-module-sources.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _materialize_module_public_key(source: ResolvedModuleSource, *, signing: ReleaseSigning) -> None:
    if signing.unsigned:
        print(f"WARNUNG: {source.spec.name}: kein Public-Key im ausdrücklichen --allow-unsigned-Modus.")
        return
    helper = source.path / "tools" / "materialize_update_public_key.py"
    if helper.is_file():
        child_env = dict(os.environ)
        child_env.setdefault("UPDATE_SIGNING_PUBLIC_KEY_B64", signing.public_key_b64)
        run(sys.executable, str(helper), cwd=source.path, env=child_env)


def _write_source_provenance(sources: dict[str, ResolvedModuleSource]) -> None:
    payload = {
        "schema": "lifeplanner.build-provenance.v1",
        "lifeplanner_version": APP_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "modules": [sources[module_id].provenance() for module_id in sorted(sources)],
    }
    path = RELEASE / "module-source-provenance.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build(
    *,
    module_sources: dict[str, Path] | None = None,
    allow_unsigned: bool = False,
) -> None:
    if not sys.platform.startswith("win"):
        raise SystemExit("Der Windows-Release muss auf Windows oder GitHub Actions windows-latest gebaut werden.")

    signing = resolve_release_signing(allow_unsigned=allow_unsigned)
    explicit = {key: value for key, value in (module_sources or {}).items() if value is not None}
    try:
        sources = resolve_module_sources(
            explicit=explicit,
            require_all=True,
            require_clean_git=os.environ.get("CI", "").lower() == "true",
        )
    except ModuleSourceError as exc:
        raise SystemExit(str(exc)) from exc

    shutil.rmtree(DIST, ignore_errors=True)
    shutil.rmtree(BUILD, ignore_errors=True)
    shutil.rmtree(RELEASE, ignore_errors=True)
    RELEASE.mkdir(parents=True)

    ordered = [sources[spec.module_id] for spec in load_lock()]
    for resolved in ordered:
        _materialize_module_public_key(resolved, signing=signing)
    for resolved in ordered:
        run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", resolved.spec.build_spec, cwd=resolved.path)
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "LifePlanner.spec", cwd=ROOT)
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "LifePlannerUpdater.spec", cwd=ROOT)
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "LifePlannerInstallerBootstrap.spec", cwd=ROOT)

    shell = DIST / "LifePlanner"
    helper = DIST / "LifePlannerUpdater.exe"
    if not helper.is_file():
        raise RuntimeError(f"Update-Helfer fehlt nach Build: {helper}")
    shutil.copy2(helper, shell / helper.name)

    modules = shell / "modules"
    for resolved in ordered:
        module_id = resolved.spec.module_id
        target = modules / module_id
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(resolved.path / "module.json", target / "module.json")
        built_dir = resolved.path / resolved.spec.dist_directory
        if not built_dir.is_dir():
            raise RuntimeError(f"{resolved.spec.name}: Buildausgabe fehlt: {built_dir}")
        shutil.copytree(built_dir, target / resolved.spec.runtime_directory, dirs_exist_ok=True)

    installer_source = RELEASE / "LifePlanner_Installer_Source"
    portable = RELEASE / "LifePlanner_Portable"
    shutil.copytree(shell, installer_source)
    # The per-user Windows installation lives in a writable LocalAppData program
    # directory, so keep all LifePlanner state below that one installation root.
    (installer_source / "portable.flag").write_text("single-root\n", encoding="ascii")
    shutil.rmtree(installer_source / "modules", ignore_errors=True)
    (installer_source / "modules").mkdir(parents=True, exist_ok=True)
    _write_installer_sources(installer_source)
    bootstrap = DIST / "LifePlannerInstallerBootstrap.exe"
    if not bootstrap.is_file():
        raise RuntimeError(f"Installer-Bootstrap fehlt nach Build: {bootstrap}")
    shutil.copy2(bootstrap, RELEASE / bootstrap.name)
    shutil.copytree(shell, portable)
    (portable / "portable.flag").write_text("portable\n", encoding="ascii")
    shutil.make_archive(str(RELEASE / f"LifePlanner_{APP_VERSION}_Windows_Portable"), "zip", RELEASE, portable.name)
    _build_update_assets(shell, signing=signing)
    _write_source_provenance(sources)
    print(f"Portable ZIP: {RELEASE / f'LifePlanner_{APP_VERSION}_Windows_Portable.zip'}")
    print(f"Installer-Dateien: {installer_source}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Baut LifePlanner aus drei getrennten Git-Repositories."
    )
    for spec in load_lock():
        parser.add_argument(f"--{spec.module_id}-source", type=Path)
    parser.add_argument(
        "--allow-unsigned",
        action="store_true",
        help="Baut den bewussten ersten Release ohne Paket- und Manifest-Signaturen.",
    )
    args = parser.parse_args()
    build(
        module_sources={
            spec.module_id: getattr(args, f"{spec.module_id}_source", None) for spec in load_lock()
        },
        allow_unsigned=args.allow_unsigned,
    )
