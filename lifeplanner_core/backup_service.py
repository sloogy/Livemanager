from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from . import APP_VERSION
from .paths import backups_dir, profile_dir
from .zeitmarke import dateimarke


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
    stamp = dateimarke()
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
                "created_at": datetime.now(UTC).isoformat(),
                "file_count": file_count,
            }
            archive.writestr("backup_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        os.replace(temp, target)
        checksum = _sha256(target)
        pruefsumme = target.with_suffix(target.suffix + ".sha256")
        pruefsumme.write_text(f"{checksum}  {target.name}\n", encoding="ascii")
        verify_backup(target)
        # Das Archiv enthält den ganzen Profilordner - Einstellungen, Brücke,
        # Moduldaten. Also dieselben Rechte wie der Ordner selbst.
        from .file_permissions import secure_file

        secure_file(target)
        secure_file(pruefsumme)
        _alte_sicherungen_entfernen(target_dir, profile_id)
        return target
    except Exception as exc:
        temp.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise BackupError(f"Backup fehlgeschlagen: {exc}") from exc


# Wie viele Sicherungen je Profil aufgehoben werden. Jede enthält den
# vollständigen Profilordner; ohne Grenze füllt sich die Platte still.
SICHERUNGEN_AUFBEWAHREN = 20


def _alte_sicherungen_entfernen(target_dir: Path, profile_id: str) -> None:
    """Behält die jüngsten Sicherungen dieses Profils, entfernt ältere.

    Nur die selbst erzeugten: Der Name trägt Profil und Zeitstempel, und was
    jemand von Hand dort abgelegt hat, passt nicht auf dieses Muster.
    """
    vorhanden = sorted(
        target_dir.glob(f"lifeplanner-{profile_id}-*.zip"),
        key=lambda p: p.name,
        reverse=True,
    )
    for veraltet in vorhanden[SICHERUNGEN_AUFBEWAHREN:]:
        for datei in (veraltet, veraltet.with_suffix(veraltet.suffix + ".sha256")):
            try:
                datei.unlink(missing_ok=True)
            except OSError:
                # Eine nicht löschbare Altsicherung darf das Sichern nicht
                # scheitern lassen - die neue liegt bereits.
                return


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
