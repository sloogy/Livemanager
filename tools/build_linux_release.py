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

from tools.module_sources import ModuleSourceError, ResolvedModuleSource, resolve_module_sources
from tools.release_signing import ReleaseSigning, resolve_release_signing

DIST = ROOT / "dist"
BUILD = ROOT / "build"
RELEASE = ROOT / "release-linux"
APP_VERSION = "0.5.0"
PLATFORM_KEY = "linux-x86_64"
PLATFORM_LABEL = "Linux_x86_64"


def run(*args: str, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(args))
    subprocess.run(args, cwd=cwd, check=True, env=env)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_component(*, payload: Path, component_id: str, name: str, version: str,
                      kind: str, output: Path, requires_host: str = "",
                      description: str = "", private_key_b64: str) -> Path:
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
        platforms=(PLATFORM_KEY,),
        private_key_b64=private_key_b64,
    )


def materialize_module_public_key(source: ResolvedModuleSource, *, signing: ReleaseSigning) -> None:
    if signing.unsigned:
        print(f"WARNUNG: {source.spec.name}: kein Public-Key im ausdrücklichen --allow-unsigned-Modus.")
        return
    helper = source.path / "tools" / "materialize_update_public_key.py"
    if helper.is_file():
        child_env = dict(os.environ)
        child_env.setdefault("UPDATE_SIGNING_PUBLIC_KEY_B64", signing.public_key_b64)
        run(sys.executable, str(helper), cwd=source.path, env=child_env)


def build_update_assets(shell: Path, *, signing: ReleaseSigning) -> None:
    update_dir = RELEASE / "update-assets"
    update_dir.mkdir(parents=True, exist_ok=True)
    core_payload = RELEASE / ".core-payload"
    shutil.rmtree(core_payload, ignore_errors=True)
    core_payload.mkdir(parents=True)
    for item in shell.iterdir():
        if item.name in {"modules", "portable.flag", "installation.json"}:
            continue
        target = core_payload / item.name
        shutil.copytree(item, target) if item.is_dir() else shutil.copy2(item, target)

    entries: list[tuple[str, str, str, str, Path, str, str, str]] = [(
        "lifeplanner.core", "LifePlanner Core", APP_VERSION, "core", core_payload,
        f"LifePlanner_Core_{APP_VERSION}_{PLATFORM_LABEL}.zip", "", "LifePlanner Plattform-Core",
    )]
    for module_path in sorted(path for path in (shell / "modules").iterdir()
                              if path.is_dir() and (path / "module.json").is_file()):
        info = json.loads((module_path / "module.json").read_text(encoding="utf-8"))
        module_id = str(info["id"])
        safe_id = "".join(char if char.isalnum() or char in "-_" else "_" for char in module_id)
        entries.append((
            module_id, str(info["name"]), str(info["version"]), "module", module_path,
            f"{safe_id}_{info['version']}_{PLATFORM_LABEL}.lpmodule", ">=0.5.0",
            str(info.get("description", "")),
        ))

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
    for component_id, name, version, kind, payload, filename, requires_host, description in entries:
        output = package_component(
            payload=payload, component_id=component_id, name=name, version=version,
            kind=kind, output=update_dir / filename, requires_host=requires_host,
            description=description, private_key_b64=signing.private_key_b64,
        )
        manifest_components[component_id] = {
            "id": component_id, "name": name, "version": version, "kind": kind,
            "requires_host": requires_host, "description": description,
            "assets": {PLATFORM_KEY: {
                "url": f"{base_url}/{filename}", "sha256": sha256(output),
                "size": output.stat().st_size, "type": "component-zip",
            }},
        }

    manifest = {
        "schema": "lifeplanner.update.v1", "channel": "stable",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "components": manifest_components,
    }
    manifest_path = update_dir / "lifeplanner-latest-linux.json"
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    manifest_path.write_bytes(manifest_bytes)
    if signing.private_key_b64:
        from lifeplanner_core.updater.signing import sign_manifest

        (update_dir / "lifeplanner-latest-linux.json.sig").write_bytes(
            sign_manifest(manifest_bytes, signing.private_key_b64)
        )
    else:
        print("WARNUNG: --allow-unsigned aktiv; Pakete und Update-Manifest bleiben unsigniert.")
    shutil.rmtree(core_payload, ignore_errors=True)


def write_source_provenance(sources: dict[str, ResolvedModuleSource]) -> None:
    payload = {
        "schema": "lifeplanner.build-provenance.v1",
        "lifeplanner_version": APP_VERSION,
        "platform": PLATFORM_KEY,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "modules": [sources[module_id].provenance() for module_id in sorted(sources)],
    }
    (RELEASE / "module-source-provenance-linux.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def build(
    *,
    budgetmanager_source: Path | None = None,
    fpm_source: Path | None = None,
    allow_unsigned: bool = False,
) -> None:
    if not sys.platform.startswith("linux"):
        raise SystemExit("Der Linux-Release muss auf Linux/GitHub Actions ubuntu-latest gebaut werden.")
    signing = resolve_release_signing(allow_unsigned=allow_unsigned)
    explicit = {key: value for key, value in {
        "budgetmanager": budgetmanager_source, "fpm": fpm_source,
    }.items() if value is not None}
    try:
        sources = resolve_module_sources(
            explicit=explicit, require_all=True,
            require_clean_git=os.environ.get("CI", "").lower() == "true",
        )
    except ModuleSourceError as exc:
        raise SystemExit(str(exc)) from exc

    for path in (DIST, BUILD, RELEASE):
        shutil.rmtree(path, ignore_errors=True)
    RELEASE.mkdir(parents=True)
    budgetmanager, fpm = sources["budgetmanager"], sources["fpm"]
    materialize_module_public_key(budgetmanager, signing=signing)
    materialize_module_public_key(fpm, signing=signing)
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", budgetmanager.spec.build_spec, cwd=budgetmanager.path)
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", fpm.spec.build_spec, cwd=fpm.path)
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "LifePlanner.spec", cwd=ROOT)
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "LifePlannerUpdater.spec", cwd=ROOT)

    shell = DIST / "LifePlanner"
    helper = DIST / "LifePlannerUpdater"
    if not shell.is_dir() or not helper.is_file():
        raise RuntimeError("LifePlanner- oder Updater-Buildausgabe fehlt.")
    shutil.copy2(helper, shell / helper.name)
    modules = shell / "modules"
    for resolved in (budgetmanager, fpm):
        target = modules / resolved.spec.module_id
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(resolved.path / "module.json", target / "module.json")
        built_dir = resolved.path / resolved.spec.dist_directory
        if not built_dir.is_dir():
            raise RuntimeError(f"{resolved.spec.name}: Buildausgabe fehlt: {built_dir}")
        shutil.copytree(built_dir, target / resolved.spec.runtime_directory, dirs_exist_ok=True)

    portable = RELEASE / "LifePlanner_Portable"
    shutil.copytree(shell, portable)
    (portable / "portable.flag").write_text("portable\n", encoding="ascii")
    base = RELEASE / f"LifePlanner_{APP_VERSION}_Linux_x86_64_Portable"
    shutil.make_archive(str(base), "gztar", RELEASE, portable.name)
    shutil.make_archive(str(base), "zip", RELEASE, portable.name)
    build_update_assets(shell, signing=signing)
    write_source_provenance(sources)
    print(f"Linux Portable: {base}.tar.gz")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Baut den Fedora/Linux-LifePlanner aus drei getrennten Git-Repositories.")
    parser.add_argument("--budgetmanager-source", type=Path)
    parser.add_argument("--fpm-source", type=Path)
    parser.add_argument(
        "--allow-unsigned",
        action="store_true",
        help="Baut den bewussten ersten Release ohne Paket- und Manifest-Signaturen.",
    )
    args = parser.parse_args()
    build(
        budgetmanager_source=args.budgetmanager_source,
        fpm_source=args.fpm_source,
        allow_unsigned=args.allow_unsigned,
    )
