from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .manifest import ManifestError, ModuleManifest
from .paths import modules_dir


@dataclass(frozen=True)
class PluginLoadResult:
    modules: tuple[ModuleManifest, ...]
    errors: tuple[str, ...]


def discover_modules(base: Path | None = None) -> PluginLoadResult:
    root = base or modules_dir()
    modules: list[ModuleManifest] = []
    errors: list[str] = []
    seen: set[str] = set()
    if not root.is_dir():
        return PluginLoadResult((), (f"Modulordner fehlt: {root}",))
    for manifest_path in sorted(root.glob("*/module.json")):
        try:
            manifest = ModuleManifest.load(manifest_path)
            if manifest.module_id in seen:
                raise ManifestError(f"Doppelte Modul-ID: {manifest.module_id}")
            seen.add(manifest.module_id)
            modules.append(manifest)
        except ManifestError as exc:
            errors.append(str(exc))
    return PluginLoadResult(tuple(modules), tuple(errors))
