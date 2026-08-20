from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from . import APP_VERSION
from .paths import backups_dir, profile_dir


class BackupError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_profile_backup(profile_id: str) -> Path:
    source = profile_dir(profile_id)
    target_dir = backups_dir(profile_id)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = target_dir / f"lifeplanner-{profile_id}-{stamp}.zip"
    fd, temp_name = tempfile.mkstemp(prefix=".backup-", suffix=".zip", dir=target_dir)
    os.close(fd)
    temp = Path(temp_name)
    file_count = 0
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(source.rglob("*")):
                if not path.is_file() or target_dir in path.parents:
                    continue
                rel = path.relative_to(source)
                archive.write(path, Path("profile") / rel)
                file_count += 1
            manifest = {
                "schema": "lifeplanner.backup.v1",
                "host_version": APP_VERSION,
                "profile_id": profile_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "file_count": file_count,
            }
            archive.writestr("backup_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        os.replace(temp, target)
        checksum = _sha256(target)
        target.with_suffix(target.suffix + ".sha256").write_text(f"{checksum}  {target.name}\n", encoding="ascii")
        verify_backup(target)
        return target
    except Exception as exc:
        temp.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise BackupError(f"Backup fehlgeschlagen: {exc}") from exc


def verify_backup(path: Path) -> dict:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            bad = archive.testzip()
            if bad:
                raise BackupError(f"Beschädigter Eintrag: {bad}")
            manifest = json.loads(archive.read("backup_manifest.json").decode("utf-8"))
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
        raise BackupError(f"Ungültiges LifePlanner-Backup: {exc}") from exc
    if manifest.get("schema") != "lifeplanner.backup.v1":
        raise BackupError("Unbekanntes Backup-Schema")
    return manifest
