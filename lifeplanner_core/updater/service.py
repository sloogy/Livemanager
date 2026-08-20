from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from .. import APP_VERSION
from ..manifest import ModuleManifest
from ..paths import app_dir, data_root
from ..plugin_loader import PluginLoadResult
from .io import (
    UpdateIOError,
    download_asset,
    load_verified_manifest,
    secure_extract_zip,
    tree_sha256,
)
from .manifest import ComponentStatus, UpdateComponent, UpdateManifest, compare_manifest


class UpdateServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class UpdateCheckResult:
    manifest: UpdateManifest
    statuses: tuple[ComponentStatus, ...]

    @property
    def available(self) -> tuple[ComponentStatus, ...]:
        return tuple(status for status in self.statuses if status.update_available and status.compatible)


@dataclass(frozen=True)
class StagedComponent:
    component_id: str
    name: str
    version: str
    kind: str
    payload_dir: Path
    tree_sha256: str


class UpdateService:
    def __init__(self, load_result: PluginLoadResult):
        self.load_result = load_result
        self.update_root = data_root() / "updates"
        for name in ("cache", "staging", "plans", "runtime", "rollback"):
            (self.update_root / name).mkdir(parents=True, exist_ok=True)

    def installed_versions(self) -> dict[str, str]:
        versions = {"lifeplanner.core": APP_VERSION}
        versions.update({module.module_id: module.version for module in self.load_result.modules})
        return versions

    def check(self, manifest_url: str) -> UpdateCheckResult:
        url = str(manifest_url or "").strip()
        if not url:
            raise UpdateServiceError("Bitte zuerst die URL des zentralen Update-Manifests eintragen.")
        try:
            manifest, _ = load_verified_manifest(url)
            statuses = compare_manifest(manifest, self.installed_versions(), host_version=APP_VERSION)
        except Exception as exc:
            if isinstance(exc, UpdateServiceError):
                raise
            raise UpdateServiceError(str(exc)) from exc
        return UpdateCheckResult(manifest=manifest, statuses=statuses)

    def stage(self, manifest: UpdateManifest, component_ids: Iterable[str]) -> tuple[StagedComponent, ...]:
        selected = list(dict.fromkeys(str(value) for value in component_ids))
        if not selected:
            raise UpdateServiceError("Keine Update-Komponente ausgewählt.")
        selected_host = APP_VERSION
        if "lifeplanner.core" in selected:
            core = manifest.components.get("lifeplanner.core")
            if core is not None:
                selected_host = core.version
        for component_id in selected:
            component = manifest.components.get(component_id)
            if component is not None and component.requires_host and Version(selected_host) not in SpecifierSet(component.requires_host):
                raise UpdateServiceError(
                    f"{component.name} benötigt LifePlanner {component.requires_host}. "
                    "Bitte das passende Core-Update mit auswählen."
                )
        staged: list[StagedComponent] = []
        for component_id in selected:
            component = manifest.components.get(component_id)
            if component is None:
                raise UpdateServiceError(f"Komponente fehlt im Manifest: {component_id}")
            asset = component.asset_for_current_platform()
            if asset is None:
                raise UpdateServiceError(f"Kein passendes Asset für {component.name}.")
            archive = self.update_root / "cache" / f"{component_id}-{component.version}-{asset.sha256[:12]}.zip"
            try:
                if not archive.is_file() or archive.stat().st_size != asset.size:
                    download_asset(asset, archive)
                elif self._sha256(archive) != asset.sha256:
                    archive.unlink(missing_ok=True)
                    download_asset(asset, archive)
                stage_dir = self.update_root / "staging" / component_id / component.version
                secure_extract_zip(archive, stage_dir)
                payload = self._validate_component_archive(stage_dir, component)
            except (OSError, UpdateIOError, ValueError) as exc:
                raise UpdateServiceError(f"{component.name} konnte nicht vorbereitet werden: {exc}") from exc
            staged.append(
                StagedComponent(
                    component_id=component.component_id,
                    name=component.name,
                    version=component.version,
                    kind=component.kind,
                    payload_dir=payload,
                    tree_sha256=tree_sha256(payload),
                )
            )
        return tuple(staged)

    @staticmethod
    def _sha256(path: Path) -> str:
        from .io import sha256_file

        return sha256_file(path)

    @staticmethod
    def _validate_component_archive(stage_dir: Path, component: UpdateComponent) -> Path:
        metadata_path = stage_dir / "component.json"
        payload = stage_dir / "payload"
        if not metadata_path.is_file() or not payload.is_dir():
            raise ValueError("Komponentenarchiv benötigt component.json und payload/")
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Ungültige component.json: {exc}") from exc
        expected = {
            "schema": "lifeplanner.component.v1",
            "id": component.component_id,
            "version": component.version,
            "kind": component.kind,
        }
        for key, value in expected.items():
            if str(metadata.get(key, "")) != value:
                raise ValueError(f"component.json stimmt bei {key} nicht überein")
        if not any(payload.iterdir()):
            raise ValueError("Komponenten-Payload ist leer")
        if component.kind == "core":
            forbidden = {
                "modules",
                "data",
                "profiles",
                "updates",
                ".venv",
                "portable.flag",
                "installation.json",
            }
            hit = sorted(path.name for path in payload.iterdir() if path.name in forbidden)
            if hit:
                raise ValueError(f"Core-Asset enthält geschützte Pfade: {', '.join(hit)}")
        else:
            manifest_path = payload / "module.json"
            if not manifest_path.is_file():
                raise ValueError("Modul-Asset enthält kein module.json")
            module_manifest = ModuleManifest.load(manifest_path)
            if module_manifest.module_id != component.component_id:
                raise ValueError("Modul-ID im Payload stimmt nicht")
            if Version(module_manifest.version) != Version(component.version):
                raise ValueError("Modulversion im Payload stimmt nicht")
        return payload.resolve()

    def write_plan(self, staged: Iterable[StagedComponent], *, parent_pid: int) -> Path:
        staged_list = list(staged)
        if not staged_list:
            raise UpdateServiceError("Keine vorbereiteten Komponenten vorhanden.")
        operations: list[dict] = []
        for component in staged_list:
            target_rel = "." if component.kind == "core" else f"modules/{component.component_id}"
            operations.append(
                {
                    "action": "replace",
                    "component_id": component.component_id,
                    "name": component.name,
                    "version": component.version,
                    "kind": component.kind,
                    "payload_dir": str(component.payload_dir),
                    "tree_sha256": component.tree_sha256,
                    "target_rel": target_rel,
                }
            )
        return self._write_operations_plan(operations, parent_pid=parent_pid)

    def write_remove_plan(self, module_ids: Iterable[str], *, parent_pid: int) -> Path:
        selected = list(dict.fromkeys(str(value).strip() for value in module_ids if str(value).strip()))
        if not selected:
            raise UpdateServiceError("Kein Modul zur Deinstallation ausgewählt.")
        installed = {module.module_id: module for module in self.load_result.modules}
        operations: list[dict] = []
        for module_id in selected:
            module = installed.get(module_id)
            if module is None:
                raise UpdateServiceError(f"Modul ist nicht installiert: {module_id}")
            operations.append(
                {
                    "action": "remove",
                    "component_id": module.module_id,
                    "name": module.name,
                    "version": module.version,
                    "kind": "module",
                    "target_rel": f"modules/{module.module_id}",
                }
            )
        return self._write_operations_plan(operations, parent_pid=parent_pid)

    def _write_operations_plan(self, operations: list[dict], *, parent_pid: int) -> Path:
        app_root = app_dir().resolve()
        restart_command = self._restart_command(app_root)
        plan = {
            "schema": "lifeplanner.update-plan.v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "app_root": str(app_root),
            "update_root": str(self.update_root.resolve()),
            "wait_pids": [int(parent_pid)],
            "restart_command": restart_command,
            "backup_profiles": True,
            "operations": operations,
        }
        path = self.update_root / "plans" / f"plan-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)
        return path

    @staticmethod
    def _restart_command(app_root: Path) -> list[str]:
        if getattr(sys, "frozen", False):
            exe = app_root / ("LifePlanner.exe" if sys.platform.startswith("win") else "LifePlanner")
            return [str(exe)]
        return [sys.executable, str(app_root / "main.py")]

    def launch_helper(self, plan_path: Path) -> None:
        app_root = app_dir().resolve()
        if getattr(sys, "frozen", False):
            helper = app_root / ("LifePlannerUpdater.exe" if sys.platform.startswith("win") else "LifePlannerUpdater")
            if not helper.is_file():
                raise UpdateServiceError(f"Externer Update-Helfer fehlt: {helper}")
            runtime_helper = self.update_root / "runtime" / f"LifePlannerUpdater-{uuid.uuid4().hex}{helper.suffix}"
            shutil.copy2(helper, runtime_helper)
            command = [str(runtime_helper), "--plan", str(plan_path)]
        else:
            helper_script = app_root / "update_helper.py"
            if not helper_script.is_file():
                raise UpdateServiceError(f"Update-Helfer fehlt: {helper_script}")
            command = [sys.executable, str(helper_script), "--plan", str(plan_path)]
        kwargs: dict = {
            "cwd": str(self.update_root),
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": True,
        }
        if sys.platform.startswith("win"):
            kwargs["creationflags"] = (
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                | getattr(subprocess, "DETACHED_PROCESS", 0)
            )
        else:
            kwargs["start_new_session"] = True
        try:
            subprocess.Popen(command, **kwargs)
        except OSError as exc:
            raise UpdateServiceError(f"Update-Helfer konnte nicht gestartet werden: {exc}") from exc

    def read_last_result(self) -> dict:
        path = self.update_root / "last_result.json"
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}
