from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROTECTED_CORE_NAMES = {
    "modules",
    "data",
    "profiles",
    "updates",
    ".venv",
    "portable.flag",
    "installation.json",
}


class ApplyPlanError(RuntimeError):
    pass


def tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda p: p.as_posix()):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(rel).to_bytes(4, "big"))
        digest.update(rel)
        digest.update(path.stat().st_size.to_bytes(8, "big"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ApplyPlanError(f"Unsicherer Zielpfad im Update-Plan: {relative!r}") from exc
    return candidate


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform.startswith("win"):
        import ctypes

        SYNCHRONIZE = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, int(pid))
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_for_processes(pids: list[int], timeout: float = 90.0) -> None:
    deadline = time.monotonic() + timeout
    remaining = {int(pid) for pid in pids if int(pid) > 0 and int(pid) != os.getpid()}
    while remaining and time.monotonic() < deadline:
        remaining = {pid for pid in remaining if _pid_alive(pid)}
        if remaining:
            time.sleep(0.25)
    if remaining:
        raise ApplyPlanError(f"Laufende Prozesse blockieren das Update: {sorted(remaining)}")




def _replace_path(source: Path, target: Path, *, retries: int = 30) -> None:
    last_error: OSError | None = None
    for attempt in range(retries):
        try:
            os.replace(source, target)
            return
        except OSError as exc:
            last_error = exc
            if attempt + 1 >= retries:
                break
            time.sleep(min(1.0, 0.1 + attempt * 0.05))
    raise ApplyPlanError(f"Datei konnte nicht ersetzt werden: {source} -> {target}: {last_error}")

def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def _backup_profiles(update_root: Path, app_root: Path) -> list[str]:
    data_root = update_root.parent
    profiles = data_root / "profiles"
    if not profiles.is_dir():
        return []
    backup_dir = update_root / "rollback" / datetime.now().strftime("%Y%m%d-%H%M%S") / "profiles"
    backup_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for profile in sorted(path for path in profiles.iterdir() if path.is_dir()):
        target = backup_dir / f"{profile.name}.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(profile.rglob("*")):
                if path.is_file() and "backups" not in path.relative_to(profile).parts:
                    archive.write(path, Path("profile") / path.relative_to(profile))
            archive.writestr(
                "backup_manifest.json",
                json.dumps(
                    {
                        "schema": "lifeplanner.preupdate-backup.v1",
                        "profile_id": profile.name,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "app_root": str(app_root),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        with zipfile.ZipFile(target, "r") as archive:
            bad = archive.testzip()
            if bad:
                raise ApplyPlanError(f"Vorab-Backup beschädigt: {target} / {bad}")
        created.append(str(target))
    return created


def _backup_program_component(operation: dict[str, Any], target: Path, backup_root: Path, app_root: Path) -> Path:
    component_id = str(operation["component_id"])
    target_zip = backup_root / f"{component_id}.zip"
    target_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        if operation["kind"] == "module":
            if target.exists():
                for path in sorted(target.rglob("*")):
                    if path.is_file():
                        archive.write(path, Path("payload") / path.relative_to(target))
        else:
            payload = Path(operation["payload_dir"])
            for source in sorted(payload.iterdir(), key=lambda p: p.name):
                current = app_root / source.name
                if current.is_file():
                    archive.write(current, Path("payload") / current.name)
                elif current.is_dir():
                    for path in sorted(current.rglob("*")):
                        if path.is_file():
                            archive.write(path, Path("payload") / current.name / path.relative_to(current))
        archive.writestr("operation.json", json.dumps(operation, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(target_zip, "r") as archive:
        bad = archive.testzip()
        if bad:
            raise ApplyPlanError(f"Programm-Rollback beschädigt: {target_zip} / {bad}")
    return target_zip


def _copy_payload_to_same_volume(payload: Path, incoming: Path) -> None:
    if incoming.exists():
        shutil.rmtree(incoming)
    shutil.copytree(payload, incoming)


def _remove_path(path: Path, *, retries: int = 30) -> None:
    last_error: OSError | None = None
    for attempt in range(retries):
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
            return
        except OSError as exc:
            last_error = exc
            if attempt + 1 >= retries:
                break
            time.sleep(min(1.0, 0.1 + attempt * 0.05))
    raise ApplyPlanError(f"Pfad konnte nicht entfernt werden: {path}: {last_error}")


def apply_plan(plan_path: Path) -> dict[str, Any]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("schema") != "lifeplanner.update-plan.v1":
        raise ApplyPlanError("Unbekanntes Update-Plan-Schema")
    app_root = Path(str(plan.get("app_root", ""))).resolve()
    update_root = Path(str(plan.get("update_root", ""))).resolve()
    if not app_root.is_dir() or not update_root.is_dir():
        raise ApplyPlanError("App- oder Update-Ordner fehlt")
    operations = plan.get("operations")
    if not isinstance(operations, list) or not operations:
        raise ApplyPlanError("Update-Plan enthält keine Operationen")

    wait_for_processes([int(pid) for pid in plan.get("wait_pids", [])])
    profile_backups = _backup_profiles(update_root, app_root) if plan.get("backup_profiles", True) else []

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    tx_root = app_root / f".__lifeplanner_update_{stamp}_{os.getpid()}"
    incoming_root = tx_root / "incoming"
    old_root = tx_root / "old"
    rollback_root = update_root / "rollback" / stamp / "program"
    incoming_root.mkdir(parents=True, exist_ok=True)
    old_root.mkdir(parents=True, exist_ok=True)
    changed: list[dict[str, Any]] = []
    program_backups: list[str] = []

    try:
        for index, operation in enumerate(operations):
            if not isinstance(operation, dict):
                raise ApplyPlanError("Ungültige Operation im Update-Plan")
            component_id = str(operation.get("component_id", ""))
            kind = str(operation.get("kind", ""))
            action = str(operation.get("action", "replace")).strip().lower() or "replace"
            if kind not in {"core", "module"} or action not in {"replace", "remove"}:
                raise ApplyPlanError(f"Ungültige Operation für {component_id}")
            if action == "remove" and kind != "module":
                raise ApplyPlanError("Nur Module dürfen deinstalliert werden")

            payload: Path | None = None
            if action == "replace":
                payload = Path(str(operation.get("payload_dir", ""))).resolve()
                if not payload.is_dir():
                    raise ApplyPlanError(f"Payload fehlt für {component_id}")
                try:
                    payload.relative_to(update_root)
                except ValueError as exc:
                    raise ApplyPlanError(f"Payload liegt außerhalb des Update-Ordners: {component_id}") from exc
                expected_hash = str(operation.get("tree_sha256", "")).lower()
                if tree_sha256(payload).lower() != expected_hash:
                    raise ApplyPlanError(f"Staging-Prüfung fehlgeschlagen: {component_id}")

            target = _safe_relative(app_root, str(operation.get("target_rel", "")))
            if kind == "core" and target != app_root:
                raise ApplyPlanError("Core-Update muss auf den App-Root zielen")
            if kind == "module" and target.parent != (app_root / "modules").resolve():
                raise ApplyPlanError("Modul-Update zielt nicht auf modules/<id>")
            if action == "remove" and not target.is_dir():
                raise ApplyPlanError(f"Zu deinstallierendes Modul fehlt: {component_id}")
            program_backups.append(str(_backup_program_component(operation, target, rollback_root, app_root)))

            op_incoming = incoming_root / f"{index}-{component_id}"
            op_old = old_root / f"{index}-{component_id}"
            if action == "remove":
                _replace_path(target, op_old)
                changed.append({"kind": "module", "action": "remove", "target": target, "old": op_old, "existed": True})
            elif kind == "module":
                assert payload is not None
                _copy_payload_to_same_volume(payload, op_incoming)
                existed = target.exists()
                if existed:
                    _replace_path(target, op_old)
                # Eine Core-Installation ohne Module bringt kein modules/ mit.
                # Ohne diesen Ordner scheitert os.replace mit ENOENT und das
                # erste Modul liesse sich nie installieren.
                target.parent.mkdir(parents=True, exist_ok=True)
                _replace_path(op_incoming, target)
                changed.append({"kind": "module", "action": "replace", "target": target, "old": op_old, "existed": existed})
            else:
                assert payload is not None
                names = [path.name for path in payload.iterdir()]
                forbidden = sorted(set(names) & PROTECTED_CORE_NAMES)
                if forbidden:
                    raise ApplyPlanError(f"Core-Payload enthält geschützte Pfade: {', '.join(forbidden)}")
                _copy_payload_to_same_volume(payload, op_incoming)
                core_changes: list[dict[str, Any]] = []
                op_old.mkdir(parents=True, exist_ok=True)
                try:
                    for name in names:
                        current = app_root / name
                        existed = current.exists() or current.is_symlink()
                        if existed:
                            _replace_path(current, op_old / name)
                        _replace_path(op_incoming / name, current)
                        core_changes.append({"target": current, "old": op_old / name, "existed": existed})
                except Exception:
                    for item in reversed(core_changes):
                        _remove_path(item["target"])
                        if item["existed"] and item["old"].exists():
                            _replace_path(item["old"], item["target"])
                    raise
                changed.append({"kind": "core", "items": core_changes})

        result = {
            "schema": "lifeplanner.update-result.v1",
            "success": True,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "components": [
                {
                    "id": str(op.get("component_id")),
                    "version": str(op.get("version")),
                    "action": str(op.get("action", "replace")),
                }
                for op in operations
            ],
            "profile_backups": profile_backups,
            "program_backups": program_backups,
        }
        _write_json_atomic(update_root / "last_result.json", result)
        shutil.rmtree(tx_root, ignore_errors=True)
        return result
    except Exception as exc:
        rollback_errors: list[str] = []
        for change in reversed(changed):
            try:
                if change["kind"] == "module":
                    _remove_path(change["target"])
                    if change["existed"] and Path(change["old"]).exists():
                        _replace_path(Path(change["old"]), Path(change["target"]))
                else:
                    for item in reversed(change["items"]):
                        _remove_path(item["target"])
                        if item["existed"] and Path(item["old"]).exists():
                            _replace_path(item["old"], item["target"])
            except Exception as rollback_exc:
                rollback_errors.append(str(rollback_exc))
        result = {
            "schema": "lifeplanner.update-result.v1",
            "success": False,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "rollback_errors": rollback_errors,
            "profile_backups": profile_backups,
            "program_backups": program_backups,
        }
        _write_json_atomic(update_root / "last_result.json", result)
        raise


def restart(command: list[str]) -> None:
    if not command or os.environ.get("LIFEPLANNER_UPDATER_NO_RESTART"):
        return
    kwargs: dict[str, Any] = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(command, cwd=str(Path(command[0]).resolve().parent), **kwargs)
