from __future__ import annotations

import logging
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
from .settings import SettingsStore
from .theme import THEME_ENV_FILE, THEME_ENV_NAME, ThemeCatalog, publish_theme
from .updater.io import ensure_executable

_log = logging.getLogger(__name__)


# Ab dieser Groesse wird das Log eines Moduls beiseitegelegt, und so viele
# alte Staende bleiben liegen. Ein RotatingFileHandler hilft hier nicht: Der
# Modulprozess schreibt selbst in den Dateideskriptor, den wir ihm geben, und
# weiss nichts von Python-Logging. Also wird beim Start gerollt.
MAX_MODULLOG_BYTES = 1_500_000
MODULLOG_STAENDE = 5


def _rotiere_modullog(pfad: Path) -> None:
    """Legt ein zu grosses Modul-Log beiseite, bevor weiter angehaengt wird.

    Ohne das wuchs die Datei bei jedem Start weiter - ein Modul, das im
    Sekundentakt etwas ausgibt, fuellt sonst unbemerkt die Platte.
    """
    try:
        if not pfad.is_file() or pfad.stat().st_size < MAX_MODULLOG_BYTES:
            return
    except OSError:
        return
    try:
        # Von hinten nach vorne durchschieben: .4 -> .5, .3 -> .4, ...
        aeltester = pfad.with_name(f"{pfad.name}.{MODULLOG_STAENDE}")
        if aeltester.exists():
            aeltester.unlink()
        for nummer in range(MODULLOG_STAENDE - 1, 0, -1):
            quelle = pfad.with_name(f"{pfad.name}.{nummer}")
            if quelle.exists():
                quelle.replace(pfad.with_name(f"{pfad.name}.{nummer + 1}"))
        pfad.replace(pfad.with_name(f"{pfad.name}.1"))
    except OSError:
        # Ein nicht rotierbares Log darf den Modulstart nicht verhindern.
        pass


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
    def __init__(
        self,
        settings: SettingsStore | None = None,
        theme_catalog: ThemeCatalog | None = None,
    ):
        self._running: dict[str, RunningModule] = {}
        self._settings = settings
        self._theme_catalog = theme_catalog
        # Der Host kennt die Systempalette, dieser Modul hier nicht; er setzt
        # das Flag, damit "system" auch im Modul hell oder dunkel bedeutet.
        self.prefers_dark = False

    def build_command(self, manifest: ModuleManifest) -> list[str]:
        exe_rel = manifest.executable_relative()
        executable = (manifest.module_dir / exe_rel).resolve() if exe_rel else None
        # Ein installiertes Modulpaket bringt nur die gebaute Programmdatei mit,
        # kein source_entry. Ob der Host selbst eingefroren ist, sagt darüber
        # nichts aus: aus der Quelle gestarteter Host plus Binärmodul ist der
        # Normalfall im Portable-/Source-Betrieb.
        if executable is not None and executable.is_file():
            if os.name != "nt" and not os.access(executable, os.X_OK):
                # An older installation may predate the execute-bit fix.
                try:
                    ensure_executable(executable)
                except OSError as exc:
                    raise ModuleLaunchError(
                        f"Modulprogramm ist nicht ausführbar: {executable} ({exc})"
                    ) from exc
            return [str(executable)]
        if getattr(sys, "frozen", False) and executable is not None:
            raise ModuleLaunchError(f"Modulprogramm fehlt: {executable}")
        source = (manifest.module_dir / manifest.source_entry).resolve()
        if not source.is_file():
            if executable is not None:
                raise ModuleLaunchError(
                    f"Moduleinstieg fehlt: weder {executable} noch {source}"
                )
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
        self._apply_theme_environment(env, manifest.module_id, profile_id)
        return env

    def _apply_theme_environment(
        self, env: dict[str, str], module_id: str, profile_id: str
    ) -> None:
        """Reicht das zentral gewählte Designprofil an den Modulprozess weiter."""
        if self._settings is None or self._theme_catalog is None:
            return
        wanted = self._settings.theme_for(module_id)
        profile = self._theme_catalog.resolve(wanted, dark_hint=self.prefers_dark)
        try:
            path = publish_theme(profile_id, module_id, profile)
        except OSError:
            # Ein nicht schreibbarer Profilordner darf den Modulstart nicht
            # verhindern; das Modul bleibt dann bei seinem eigenen Design.
            return
        env[THEME_ENV_NAME] = profile.name
        env[THEME_ENV_FILE] = str(path)

    def start(self, manifest: ModuleManifest, profile_id: str) -> RunningModule:
        current = self._running.get(manifest.module_id)
        if current and current.is_running:
            return current
        command = self.build_command(manifest)
        env = self.build_environment(manifest, profile_id)
        log_path = logs_dir(profile_id) / f"{manifest.module_id}.log"
        _rotiere_modullog(log_path)
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
        except Exception as fehler:
            # Lifecycle-Telemetrie ist lokal und darf den Modulstart nie
            # blockieren - aber schweigen darf sie nicht. Blieb sie stumm,
            # fehlten die Ereignisse spurlos, und niemand konnte sagen warum.
            _log.warning(
                "Lebenszyklus-Ereignis '%s' fuer %s nicht veroeffentlicht: %s",
                event_type, manifest.module_id, fehler,
            )

    @staticmethod
    def _close_log(running: RunningModule) -> None:
        try:
            running.log_handle.close()
        except OSError as fehler:
            # Nicht weiterreichen: das Modul ist ohnehin beendet. Aber ein
            # Dateideskriptor, der sich nicht schliessen laesst, bleibt offen.
            _log.warning(
                "Log von %s liess sich nicht schliessen: %s",
                running.manifest.module_id, fehler,
            )
