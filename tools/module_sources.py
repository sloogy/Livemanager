from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "dependencies" / "modules.lock.json"
LOCAL_CONFIG_PATH = ROOT / "dependencies" / "module-sources.local.json"


class ModuleSourceError(RuntimeError):
    """Raised when an external module source cannot be resolved or validated."""


@dataclass(frozen=True)
class ModuleSourceSpec:
    module_id: str
    name: str
    version: str
    description: str
    source_environment: str
    default_sibling: str
    build_spec: str
    dist_directory: str
    runtime_directory: str
    repository_variable: str
    default_repository: str
    ref_variable: str
    default_ref: str


@dataclass(frozen=True)
class ResolvedModuleSource:
    spec: ModuleSourceSpec
    path: Path
    git_commit: str = ""
    git_ref: str = ""
    git_dirty: bool = False

    def provenance(self) -> dict[str, object]:
        return {
            "id": self.spec.module_id,
            "name": self.spec.name,
            "version": self.spec.version,
            "source_path": str(self.path),
            "git_commit": self.git_commit,
            "git_ref": self.git_ref,
            "git_dirty": self.git_dirty,
        }


def load_lock(path: Path = LOCK_PATH) -> tuple[ModuleSourceSpec, ...]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModuleSourceError(f"Modul-Lockdatei kann nicht gelesen werden: {path}: {exc}") from exc
    if raw.get("schema") != "lifeplanner.module-sources.v1":
        raise ModuleSourceError(f"Unbekanntes Lockdatei-Schema: {raw.get('schema')!r}")
    modules = raw.get("modules")
    if not isinstance(modules, list) or not modules:
        raise ModuleSourceError("Die Modul-Lockdatei enthält keine Module.")

    result: list[ModuleSourceSpec] = []
    seen: set[str] = set()
    for item in modules:
        if not isinstance(item, dict):
            raise ModuleSourceError("Ungültiger Moduleintrag in der Lockdatei.")
        module_id = str(item.get("id", "")).strip()
        if not module_id or module_id in seen:
            raise ModuleSourceError(f"Ungültige oder doppelte Modul-ID: {module_id!r}")
        seen.add(module_id)
        result.append(
            ModuleSourceSpec(
                module_id=module_id,
                name=str(item.get("name", module_id)).strip(),
                description=str(item.get("description", "")).strip(),
                version=str(item.get("version", "")).strip(),
                source_environment=str(item.get("source_environment", "")).strip(),
                default_sibling=str(item.get("default_sibling", "")).strip(),
                build_spec=str(item.get("build_spec", "")).strip(),
                dist_directory=str(item.get("dist_directory", "")).strip(),
                runtime_directory=str(item.get("runtime_directory", "")).strip(),
                repository_variable=str(item.get("repository_variable", "")).strip(),
                default_repository=str(item.get("default_repository", "")).strip(),
                ref_variable=str(item.get("ref_variable", "")).strip(),
                default_ref=str(item.get("default_ref", "")).strip(),
            )
        )
    return tuple(result)


def load_local_mapping(path: Path | None = None) -> dict[str, str]:
    config_path = path or Path(
        os.environ.get("LIFEPLANNER_MODULE_SOURCES_FILE", str(LOCAL_CONFIG_PATH))
    ).expanduser()
    if not config_path.is_file():
        return {}
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModuleSourceError(f"Lokale Modulquellen-Konfiguration ist ungültig: {config_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ModuleSourceError(f"Lokale Modulquellen-Konfiguration muss ein JSON-Objekt sein: {config_path}")
    return {str(key): str(value) for key, value in raw.items()}


def _git(path: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return completed.stdout.strip()


def _git_metadata(path: Path) -> tuple[str, str, bool]:
    commit = _git(path, "rev-parse", "HEAD")
    ref = _git(path, "describe", "--tags", "--exact-match") or _git(path, "rev-parse", "--abbrev-ref", "HEAD")
    dirty = bool(_git(path, "status", "--porcelain")) if commit else False
    return commit, ref, dirty


def validate_module_source(spec: ModuleSourceSpec, path: Path, *, require_clean_git: bool = False) -> ResolvedModuleSource:
    source = path.expanduser().resolve()
    if not source.is_dir():
        raise ModuleSourceError(f"Quelle für {spec.name} fehlt: {source}")
    manifest_path = source / "module.json"
    if not manifest_path.is_file():
        raise ModuleSourceError(f"{spec.name}: module.json fehlt in {source}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModuleSourceError(f"{spec.name}: module.json ist ungültig: {exc}") from exc
    actual_id = str(manifest.get("id", "")).strip()
    actual_version = str(manifest.get("version", "")).strip()
    if actual_id != spec.module_id:
        raise ModuleSourceError(
            f"Falsche Modulquelle: erwartet {spec.module_id!r}, gefunden {actual_id!r} in {source}"
        )
    if actual_version != spec.version:
        raise ModuleSourceError(
            f"{spec.name}: Version {actual_version!r} passt nicht zur Lockdatei {spec.version!r}."
        )
    if spec.build_spec and not (source / spec.build_spec).is_file():
        raise ModuleSourceError(f"{spec.name}: Build-Spec fehlt: {source / spec.build_spec}")

    commit, ref, dirty = _git_metadata(source)
    if require_clean_git and commit and dirty:
        raise ModuleSourceError(f"{spec.name}: Git-Arbeitsbaum enthält uncommittete Änderungen: {source}")
    return ResolvedModuleSource(spec=spec, path=source, git_commit=commit, git_ref=ref, git_dirty=dirty)


def resolve_module_sources(
    *,
    explicit: Mapping[str, str | Path] | None = None,
    require_all: bool = True,
    require_clean_git: bool = False,
    root: Path = ROOT,
) -> dict[str, ResolvedModuleSource]:
    explicit = explicit or {}
    local_mapping = load_local_mapping()
    resolved: dict[str, ResolvedModuleSource] = {}
    errors: list[str] = []
    for spec in load_lock():
        candidate: str | Path | None = explicit.get(spec.module_id)
        if not candidate and spec.source_environment:
            candidate = os.environ.get(spec.source_environment, "").strip()
        if not candidate:
            candidate = local_mapping.get(spec.module_id, "").strip()
        if not candidate and spec.default_sibling:
            candidate = root / spec.default_sibling
        if not candidate:
            errors.append(f"Keine Quelle für {spec.name} konfiguriert.")
            continue
        try:
            resolved[spec.module_id] = validate_module_source(
                spec,
                Path(candidate),
                require_clean_git=require_clean_git,
            )
        except ModuleSourceError as exc:
            errors.append(str(exc))
    if errors and require_all:
        guidance = (
            "\nKonfiguriere die Quellen über LIFEPLANNER_BUDGETMANAGER_SOURCE / "
            "LIFEPLANNER_FPM_SOURCE oder dependencies/module-sources.local.json."
        )
        raise ModuleSourceError("\n".join(errors) + guidance)
    return resolved
