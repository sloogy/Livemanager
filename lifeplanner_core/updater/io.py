from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

from .manifest import UpdateAsset, UpdateManifest, UpdateManifestError, parse_manifest
from .signing import UpdateSignatureError, verify_manifest_signature

MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_COMPONENT_BYTES = 1024 * 1024 * 1024
MAX_EXTRACTED_BYTES = 2 * 1024 * 1024 * 1024
MAX_ZIP_ENTRIES = 100_000


class UpdateIOError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _allow_local() -> bool:
    return os.environ.get("LIFEPLANNER_ALLOW_LOCAL_UPDATES", "").strip().lower() in {"1", "true", "yes", "on"}


def _allow_unsigned() -> bool:
    return os.environ.get("LIFEPLANNER_ALLOW_UNSIGNED_UPDATES", "").strip().lower() in {"1", "true", "yes", "on"}


def _local_path(url_or_path: str) -> Path | None:
    parsed = urlparse(url_or_path)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))
    # A single-letter "scheme" is never a real URL scheme (RFC 3986 schemes
    # are effectively always >= 2 chars); urlparse() misreads a Windows
    # drive letter like "C:\..." as scheme "c", which otherwise makes every
    # local Windows path look like a remote URL.
    if not parsed.scheme or len(parsed.scheme) == 1:
        return Path(url_or_path).expanduser()
    return None


def read_url_bytes(url: str, *, max_bytes: int, timeout: int = 15) -> bytes:
    local = _local_path(url)
    if local is not None:
        if not _allow_local():
            raise UpdateIOError("Lokale Update-Dateien sind nur im expliziten Entwicklungsmodus erlaubt")
        try:
            data = local.read_bytes()
        except OSError as exc:
            raise UpdateIOError(f"Lokale Datei konnte nicht gelesen werden: {local}: {exc}") from exc
        if len(data) > max_bytes:
            raise UpdateIOError("Update-Datei überschreitet die erlaubte Größe")
        return data
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise UpdateIOError("Remote-Updates müssen über HTTPS geladen werden")
    try:
        response = requests.get(url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise UpdateIOError(f"Download fehlgeschlagen: {exc}") from exc
    final = urlparse(response.url)
    if final.scheme.lower() != "https":
        raise UpdateIOError("Unsichere Weiterleitung beim Update-Download")
    data = response.content
    if len(data) > max_bytes:
        raise UpdateIOError("Update-Datei überschreitet die erlaubte Größe")
    return data


def load_verified_manifest(manifest_url: str) -> tuple[UpdateManifest, bytes]:
    manifest_bytes = read_url_bytes(manifest_url, max_bytes=MAX_MANIFEST_BYTES)
    local = _local_path(manifest_url)
    signature_url = str(local) + ".sig" if local is not None else manifest_url + ".sig"
    if _allow_unsigned() and local is not None:
        signature_path = Path(signature_url)
        if signature_path.is_file():
            verify_manifest_signature(manifest_bytes, signature_path.read_bytes())
    else:
        try:
            signature = read_url_bytes(signature_url, max_bytes=4096)
            verify_manifest_signature(manifest_bytes, signature)
        except UpdateSignatureError:
            raise
        except Exception as exc:
            raise UpdateIOError(f"Manifest-Signatur konnte nicht geprüft werden: {exc}") from exc
    try:
        raw = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateManifestError(f"Update-Manifest ist kein gültiges UTF-8-JSON: {exc}") from exc
    return parse_manifest(raw), manifest_bytes


def download_asset(asset: UpdateAsset, destination: Path, *, timeout: int = 60) -> Path:
    if asset.size > MAX_COMPONENT_BYTES:
        raise UpdateIOError("Komponenten-Asset überschreitet die maximale Größe")
    destination.parent.mkdir(parents=True, exist_ok=True)
    local = _local_path(asset.url)
    fd, temp_name = tempfile.mkstemp(prefix=".download-", suffix=".part", dir=destination.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        if local is not None:
            if not _allow_local():
                raise UpdateIOError("Lokale Update-Dateien sind nicht erlaubt")
            shutil.copy2(local, temp)
        else:
            parsed = urlparse(asset.url)
            if parsed.scheme.lower() != "https" or not parsed.hostname:
                raise UpdateIOError("Komponenten-Downloads müssen HTTPS verwenden")
            with requests.get(asset.url, timeout=timeout, stream=True, allow_redirects=True) as response:
                response.raise_for_status()
                if urlparse(response.url).scheme.lower() != "https":
                    raise UpdateIOError("Unsichere Weiterleitung beim Komponenten-Download")
                total = 0
                with temp.open("wb") as handle:
                    for chunk in response.iter_content(1024 * 1024):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > MAX_COMPONENT_BYTES or total > asset.size + 1024:
                            raise UpdateIOError("Komponenten-Download ist größer als im Manifest angegeben")
                        handle.write(chunk)
        actual_size = temp.stat().st_size
        if actual_size != asset.size:
            raise UpdateIOError(f"Falsche Asset-Größe: erwartet {asset.size}, erhalten {actual_size}")
        actual_hash = sha256_file(temp)
        if actual_hash.lower() != asset.sha256.lower():
            raise UpdateIOError("SHA-256-Prüfung des Komponenten-Downloads fehlgeschlagen")
        os.replace(temp, destination)
        return destination
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def _zip_member_is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_ISLNK(mode)


def _zip_member_is_executable(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return bool(stat.S_IMODE(mode) & 0o111)


def ensure_executable(target: Path) -> None:
    """Grant execute permission to a module runtime.

    Mirrors the read bits into execute instead of applying an archived mode
    directly: the result still respects the umask, and setuid/setgid/sticky
    bits are never introduced.
    """
    if os.name == "nt":
        return
    current = stat.S_IMODE(target.stat().st_mode)
    target.chmod(current | ((current & 0o444) >> 2))


def secure_extract_zip(archive_path: Path, destination: Path) -> None:
    shutil.rmtree(destination, ignore_errors=True)
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    total = 0
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                raise UpdateIOError("Update-Archiv enthält zu viele Einträge")
            for info in infos:
                raw_name = info.filename.replace("\\", "/")
                if not raw_name or raw_name.startswith("/") or ":" in raw_name.split("/")[0]:
                    raise UpdateIOError(f"Unsicherer Pfad im Update-Archiv: {info.filename!r}")
                parts = Path(raw_name).parts
                if ".." in parts:
                    raise UpdateIOError(f"Pfad-Traversal im Update-Archiv: {info.filename!r}")
                if _zip_member_is_symlink(info):
                    raise UpdateIOError(f"Symbolische Links sind im Update-Archiv nicht erlaubt: {info.filename!r}")
                total += max(0, int(info.file_size))
                if total > MAX_EXTRACTED_BYTES:
                    raise UpdateIOError("Entpackte Update-Daten überschreiten die maximale Größe")
                target = (destination / Path(*parts)).resolve()
                try:
                    target.relative_to(root)
                except ValueError as exc:
                    raise UpdateIOError(f"Unsicherer Zielpfad: {info.filename!r}") from exc
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info, "r") as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                if _zip_member_is_executable(info):
                    ensure_executable(target)
    except zipfile.BadZipFile as exc:
        shutil.rmtree(destination, ignore_errors=True)
        raise UpdateIOError(f"Ungültiges ZIP-Archiv: {exc}") from exc
