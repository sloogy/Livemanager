from __future__ import annotations

import ctypes
import subprocess
import sys
from pathlib import Path

_TITLE = "LifePlanner"


def _message_box(message: str, *, error: bool = False) -> None:
    flags = 0x10 if error else 0x40  # MB_ICONERROR / MB_ICONINFORMATION
    try:
        ctypes.windll.user32.MessageBoxW(None, message, _TITLE, flags)
    except Exception:
        print(message, file=sys.stderr if error else sys.stdout)


def _core_executable(app_root: Path) -> Path:
    return app_root / "LifePlannerCore.exe"


def main() -> int:
    app_root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    core = _core_executable(app_root)
    if not core.is_file():
        _message_box(
            "LifePlanner wurde nicht vollständig entpackt.\n\n"
            "Bitte starte LifePlanner nicht direkt aus einer ZIP-Datei. "
            "Nutze den Windows-Setup oder entpacke das komplette Portable-Paket "
            "zuerst in einen normalen Ordner und starte danach LifePlanner.exe.",
            error=True,
        )
        return 2

    command = [str(core), *sys.argv[1:]]
    try:
        wait = any(arg in {"--diagnostics", "--diagnostics-file", "--list-modules"} for arg in sys.argv[1:])
        if wait:
            return int(subprocess.run(command, cwd=app_root, check=False).returncode)
        subprocess.Popen(
            command,
            cwd=app_root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        return 0
    except OSError as exc:
        _message_box(f"LifePlanner konnte nicht gestartet werden.\n\n{exc}", error=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
