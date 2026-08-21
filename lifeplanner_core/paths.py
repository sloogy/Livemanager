from __future__ import annotations

import os
import re
import sys
from pathlib import Path

_PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_TRUE = {"1", "true", "yes", "on"}


def app_dir() -> Path:
    """Return the directory containing the source tree or frozen executable."""
    override = os.environ.get("LIFEPLANNER_APP_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def is_portable() -> bool:
    raw = os.environ.get("LIFEPLANNER_PORTABLE", "").strip().lower()
    return raw in _TRUE or (app_dir() / "portable.flag").is_file()


def data_root() -> Path:
    """Resolve the writable LifePlanner data root on Windows and Linux."""
    override = os.environ.get("LIFEPLANNER_DATA_DIR", "").strip()
    if override:
        base = Path(override).expanduser()
    elif is_portable() or not getattr(sys, "frozen", False):
        # Source trees and portable builds are intentionally single-root.
        # This prevents stale LifePlanner state in ~/.local/share, ~/.config,
        # AppData and other OS-specific locations while developing/unpacking.
        base = app_dir() / "data"
    elif sys.platform.startswith("win"):
        local = os.environ.get("LOCALAPPDATA", "").strip()
        base = Path(local) / "LifePlanner" if local else Path.home() / "AppData/Local/LifePlanner"
    else:
        xdg = os.environ.get("XDG_DATA_HOME", "").strip()
        base = Path(xdg) / "lifeplanner" if xdg else Path.home() / ".local/share/lifeplanner"
    base.mkdir(parents=True, exist_ok=True)
    return base.resolve()


def config_dir() -> Path:
    path = data_root() / "config"
    path.mkdir(parents=True, exist_ok=True)
    return path


def profiles_dir() -> Path:
    path = data_root() / "profiles"
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_profile_id(profile_id: str) -> str:
    value = str(profile_id or "").strip()
    if not _PROFILE_RE.fullmatch(value):
        raise ValueError("Ungültige Profil-ID. Erlaubt sind Buchstaben, Zahlen, Punkt, Minus und Unterstrich.")
    return value


def profile_dir(profile_id: str) -> Path:
    """Der Profilordner - Einstellungen, Brückendateien, Moduldaten.

    Er wird auf 0700 gesetzt, sobald er entsteht. Mit dem Standard-umask
    angelegt wäre er auf typischen Linux-Systemen 0755: Jedes lokale Konto
    könnte hineinsehen, und in der Brücke stehen Buchungen und Sparziele.
    Unterordner erben die Rechte nicht, sind aber nur über diesen erreichbar.
    """
    path = profiles_dir() / validate_profile_id(profile_id)
    neu = not path.exists()
    path.mkdir(parents=True, exist_ok=True)
    if neu:
        from .file_permissions import secure_dir

        secure_dir(path)
    return path


def module_data_dir(profile_id: str, module_id: str) -> Path:
    if not _PROFILE_RE.fullmatch(module_id):
        raise ValueError(f"Ungültige Modul-ID: {module_id!r}")
    path = profile_dir(profile_id) / "modules" / module_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def bridge_dir(profile_id: str) -> Path:
    path = profile_dir(profile_id) / "bridge"
    path.mkdir(parents=True, exist_ok=True)
    return path


def events_dir(profile_id: str) -> Path:
    path = profile_dir(profile_id) / "events"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir(profile_id: str | None = None) -> Path:
    path = (profile_dir(profile_id) if profile_id else data_root()) / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def backups_dir(profile_id: str) -> Path:
    path = profile_dir(profile_id) / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def modules_dir() -> Path:
    return app_dir() / "modules"
