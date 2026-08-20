from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from . import APP_VERSION
from .event_bus import FileEventBus, LifePlannerEvent
from .manifest import ModuleManifest
from .paths import bridge_dir, logs_dir, module_data_dir, profile_dir
from .updater.io import ensure_executable


class ModuleLaunchError(RuntimeError):
    pass


@dataclass
class RunningModule:
    manifest: ModuleManifest
    process: subprocess.Popen
    log_handle: object
    command: tuple[str, ...]

    @property
    def is_running(self) -> bool:
        return self.process.poll() is None


class ModuleProcessManager:
    def __init__(self):
        self._running: dict[str, RunningModule] = {}

    def build_command(self, manifest: ModuleManifest) -> list[str]:
        exe_rel = manifest.executable_relative()
        if getattr(sys, "frozen", False) and exe_rel:
            executable = (manifest.module_dir / exe_rel).resolve()
            if not executable.is_file():
                raise ModuleLaunchError(f"Modulprogramm fehlt: {executable}")
            if os.name != "nt" and not os.access(executable, os.X_OK):
                # An older installation may predate the execute-bit fix.
                try:
                    ensure_executable(executable)
                except OSError as exc:
                    raise ModuleLaunchError(
                        f"Modulprogramm ist nicht ausführbar: {executable} ({exc})"
                    ) from exc
            return [str(executable)]
        source = (manifest.module_dir / manifest.source_entry).resolve()
        if not source.is_file():
            raise ModuleLaunchError(f"Moduleinstieg fehlt: {source}")
        return [sys.executable, str(source)]

    def build_environment(
        self,
        manifest: ModuleManifest,
        profile_id: str,
        base_env: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        env = dict(base_env or os.environ)
        context = {
            "profile_id": profile_id,
            "profile_dir": str(profile_dir(profile_id)),
            "module_data_dir": str(module_data_dir(profile_id, manifest.module_id)),
            "bridge_dir": str(bridge_dir(profile_id)),
            "host_version": APP_VERSION,
        }
        for key, template in manifest.environment.items():
            env[key] = template.format(**context)
        env.setdefault("LIFEPLANNER_PROFILE_ID", profile_id)
        env.setdefault("LIFEPLANNER_MODULE_DATA_DIR", context["module_data_dir"])
        env.setdefault("LIFEPLANNER_BRIDGE_DIR", context["bridge_dir"])
        env.setdefault("LIFEPLANNER_HOST_VERSION", APP_VERSION)
        env.setdefault("LIFEPLANNER_CENTRAL_UPDATER", "1")
        return env

    def start(self, manifest: ModuleManifest, profile_id: str) -> RunningModule:
        current = self._running.get(manifest.module_id)
        if current and current.is_running:
            return current
        command = self.build_command(manifest)
        env = self.build_environment(manifest, profile_id)
        log_path = logs_dir(profile_id) / f"{manifest.module_id}.log"
        log_handle = log_path.open("a", encoding="utf-8", buffering=1)
        kwargs: dict = {
            "cwd": str(manifest.module_dir),
            "env": env,
            "stdout": log_handle,
            "stderr": subprocess.STDOUT,
            "stdin": subprocess.DEVNULL,
            "shell": False,
        }
        if sys.platform.startswith("win"):
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            kwargs["start_new_session"] = True
        try:
            process = subprocess.Popen(command, **kwargs)
        except Exception as exc:
            log_handle.close()
            raise ModuleLaunchError(f"{manifest.name} konnte nicht gestartet werden: {exc}") from exc
        running = RunningModule(manifest, process, log_handle, tuple(command))
        self._running[manifest.module_id] = running
        self._publish_lifecycle(
            profile_id,
            "module.started",
            manifest,
            {"pid": process.pid},
        )
        return running

    def get(self, module_id: str) -> RunningModule | None:
        running = self._running.get(module_id)
        if running and not running.is_running:
            self._close_log(running)
        return running

    def stop(self, module_id: str, timeout: float = 5.0, profile_id: str | None = None) -> bool:
        running = self._running.get(module_id)
        if not running:
            return True
        process = running.process
        if process.poll() is None:
            try:
                if sys.platform.startswith("win"):
                    process.terminate()
                else:
                    os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                if sys.platform.startswith("win"):
                    process.kill()
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=2)
            except ProcessLookupError:
                pass
        self._close_log(running)
        self._running.pop(module_id, None)
        if profile_id:
            self._publish_lifecycle(
                profile_id,
                "module.stopped",
                running.manifest,
                {"exit_code": process.poll()},
            )
        return process.poll() is not None

    def stop_all(self, profile_id: str | None = None) -> None:
        for module_id in list(self._running):
            self.stop(module_id, profile_id=profile_id)

    @staticmethod
    def _publish_lifecycle(
        profile_id: str,
        event_type: str,
        manifest: ModuleManifest,
        payload: dict,
    ) -> None:
        try:
            event = LifePlannerEvent.create(
                event_type,
                "lifeplanner.core",
                profile_id,
                {"module_id": manifest.module_id, "version": manifest.version, **payload},
            )
            FileEventBus(profile_id).publish(event)
        except Exception:
            # Lifecycle-Telemetrie ist lokal und darf den Modulstart nie blockieren.
            pass

    @staticmethod
    def _close_log(running: RunningModule) -> None:
        try:
            running.log_handle.close()
        except Exception:
            pass
