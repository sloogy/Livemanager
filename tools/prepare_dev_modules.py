from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

from module_sources import ModuleSourceError, ROOT, resolve_module_sources

MODULES_DIR = ROOT / "modules"


def _same_target(link: Path, source: Path) -> bool:
    try:
        return link.resolve() == source.resolve()
    except OSError:
        return False


def _remove_existing(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _create_windows_junction(target: Path, source: Path) -> bool:
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(target), str(source)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return completed.returncode == 0


def materialize(target: Path, source: Path, *, mode: str) -> str:
    if target.exists() or target.is_symlink():
        if _same_target(target, source):
            return "bereits verknüpft"
        _remove_existing(target)

    if mode in {"auto", "link"}:
        try:
            target.symlink_to(source, target_is_directory=True)
            return "Symlink"
        except OSError:
            if os.name == "nt" and _create_windows_junction(target, source):
                return "Windows-Junction"
            if mode == "link":
                raise ModuleSourceError(f"Verknüpfung für {target.name} konnte nicht erstellt werden.")

    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns(".git", "build", "dist", "release", "__pycache__", ".pytest_cache"),
    )
    return "ignorierte Entwicklungskopie"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bindet separate Modul-Repositories lokal ein, ohne sie im LifePlanner-Git zu versionieren."
    )
    parser.add_argument("--budgetmanager-source", type=Path)
    parser.add_argument("--fpm-source", type=Path)
    parser.add_argument("--mode", choices=("auto", "link", "copy"), default="auto")
    parser.add_argument("--clean", action="store_true", help="Entfernt nur die lokalen Moduleinbindungen.")
    parser.add_argument("--best-effort", action="store_true", help="Bindet nur auffindbare Repositories ein und startet auch ohne Module.")
    args = parser.parse_args()

    MODULES_DIR.mkdir(parents=True, exist_ok=True)
    if args.clean:
        for module_id in ("budgetmanager", "fpm"):
            target = MODULES_DIR / module_id
            if target.exists() or target.is_symlink():
                _remove_existing(target)
                print(f"Entfernt: {target}")
        return 0

    explicit = {
        key: value
        for key, value in {
            "budgetmanager": args.budgetmanager_source,
            "fpm": args.fpm_source,
        }.items()
        if value is not None
    }
    try:
        sources = resolve_module_sources(explicit=explicit, require_all=not args.best_effort)
    except ModuleSourceError as exc:
        parser.error(str(exc))

    if not sources:
        print("Keine externen Modul-Repositories gefunden; LifePlanner startet nur mit dem Core.")
        return 0

    for module_id, resolved in sources.items():
        target = MODULES_DIR / module_id
        kind = materialize(target, resolved.path, mode=args.mode)
        print(f"{resolved.spec.name}: {kind} -> {resolved.path}")
    print("Die Einbindungen werden durch .gitignore vollständig vom LifePlanner-Repository ausgeschlossen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
